"""Account, password, session, throttle, and audit services."""

from __future__ import annotations

import datetime
import hashlib
import logging
import re
import secrets
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from mtc_assistant.dashboard_auth_models import (
    Account,
    CorruptAccountError,
    DuplicateUsernameError,
    InvalidUsernameError,
    hash_password,
    normalize_username,
    verify_password,
)
from mtc_assistant.dashboard_authorization import (
    ACCOUNTS_MANAGE,
    ASSIGNMENTS_MANAGE,
    AUTH_SESSIONS_REVOKE_ALL,
    authorize,
    capabilities_for,
)
from mtc_assistant.dashboard_security_audit import (
    SecurityAuditEvent,
    SecurityAuditOperationalState,
)


logger = logging.getLogger(__name__)
SESSION_LIFETIME = datetime.timedelta(hours=12)
SESSION_PURGE_DELAY = datetime.timedelta(days=30)
SESSION_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
DUMMY_PASSWORD_HASH = hash_password(
    "dummy password verification only", "dummy.account"
)


class AuthenticationFailed(RuntimeError):
    pass


class SessionInvalid(RuntimeError):
    pass


class AccountNotFound(RuntimeError):
    pass


class AuthorizationDenied(RuntimeError):
    pass


class DuplicateUsername(RuntimeError):
    pass


class DashboardAuthRepository(Protocol):
    def get_account_id_by_username_digest(self, digest: str) -> str | None: ...
    def get_account(self, account_id: str) -> Account | None: ...
    def create_account(self, account: Account, username_digest: str, audit: SecurityAuditEvent) -> None: ...
    def update_account(
        self,
        account: Account,
        expected_previous_version: int,
        audit: SecurityAuditEvent,
    ) -> None: ...
    def get_session(self, token_digest: str) -> dict[str, Any] | None: ...
    def put_session(self, token_digest: str, session: dict[str, Any]) -> None: ...
    def revoke_session(self, token_digest: str, revoked_at: datetime.datetime) -> bool: ...
    def get_throttle(self, username_digest: str) -> dict[str, Any] | None: ...
    def put_throttle(self, username_digest: str, state: dict[str, Any]) -> None: ...
    def record_login_failure(self, username_digest: str, now: datetime.datetime) -> dict[str, Any]: ...
    def clear_throttle(self, username_digest: str) -> None: ...
    def write_audit(self, audit: SecurityAuditEvent) -> None: ...


@dataclass(frozen=True)
class ResolvedSession:
    account: Account
    expires_at: datetime.datetime

    def safe_principal(self) -> dict[str, Any]:
        result = self.account.safe_summary()
        result.pop("status", None)
        result["capabilities"] = sorted(capabilities_for(self.account))
        result["session_expires_at"] = self.expires_at.isoformat()
        return result


class DashboardAuthService:
    def __init__(
        self,
        repository: DashboardAuthRepository,
        *,
        clock: Callable[[], datetime.datetime] | None = None,
        audit_state: SecurityAuditOperationalState | None = None,
    ) -> None:
        self.repository = repository
        self.clock = clock or (lambda: datetime.datetime.now(datetime.timezone.utc))
        self.audit_state = audit_state or SecurityAuditOperationalState()

    def create_account(
        self,
        actor_account_id: str,
        username: str,
        password: str,
        role: str,
        class_ids: list[str],
        *,
        display_name: str | None = None,
    ) -> Account:
        self._require_actor_capability(actor_account_id, ACCOUNTS_MANAGE)
        normalized = normalize_username(username)
        now = self.clock()
        account = Account.create(
            uuid.uuid4().hex,
            normalized,
            hash_password(password, normalized),
            role,
            class_ids,
            display_name=display_name,
            now=now,
            created_by=actor_account_id,
        )
        audit = SecurityAuditEvent.create(
            "account_created",
            now,
            actor_account_id=actor_account_id,
            target_account_id=account.account_id,
        )
        try:
            self.repository.create_account(account, _digest(normalized), audit)
        except DuplicateUsernameError as exc:
            raise DuplicateUsername("username already exists") from exc
        return account

    def login(self, username: Any, password: Any, *, request_id: str = "") -> dict[str, Any]:
        now = self.clock()
        try:
            normalized = normalize_username(username)
        except InvalidUsernameError:
            verify_password(DUMMY_PASSWORD_HASH, password)
            self._record_unknown_login_failure(request_id)
            raise AuthenticationFailed("invalid credentials")

        username_digest = _digest(normalized)
        account_id = self.repository.get_account_id_by_username_digest(username_digest)
        if not account_id:
            verify_password(DUMMY_PASSWORD_HASH, password)
            self._record_unknown_login_failure(request_id)
            raise AuthenticationFailed("invalid credentials")

        try:
            account = self.repository.get_account(account_id)
        except CorruptAccountError:
            verify_password(DUMMY_PASSWORD_HASH, password)
            self.repository.record_login_failure(username_digest, now)
            self._best_effort_audit(
                "login_failure",
                now,
                result="failure",
                target_account_id=account_id,
                request_id=request_id,
            )
            raise AuthenticationFailed("invalid credentials")
        if not account:
            verify_password(DUMMY_PASSWORD_HASH, password)
            self._record_unknown_login_failure(request_id)
            raise AuthenticationFailed("invalid credentials")

        throttle = self.repository.get_throttle(username_digest)
        if throttle and _as_utc(throttle.get("blocked_until")) > now:
            verify_password(DUMMY_PASSWORD_HASH, password)
            self._best_effort_audit(
                "login_failure",
                now,
                result="failure",
                target_account_id=account_id,
                request_id=request_id,
            )
            raise AuthenticationFailed("invalid credentials")

        password_valid = verify_password(account.password_hash, password)
        if not account.active or not password_valid:
            self.repository.record_login_failure(username_digest, now)
            self._best_effort_audit(
                "login_failure",
                now,
                result="failure",
                target_account_id=account_id,
                request_id=request_id,
            )
            raise AuthenticationFailed("invalid credentials")

        self.repository.clear_throttle(username_digest)
        token = secrets.token_urlsafe(32)
        expires_at = now + SESSION_LIFETIME
        self.repository.put_session(
            _digest(token),
            {
                "account_id": account.account_id,
                "issued_at": now,
                "expires_at": expires_at,
                "purge_after": expires_at + SESSION_PURGE_DELAY,
                "revoked_at": None,
                "session_version": account.session_version,
                "creation_source": "dashboard_login",
            },
        )
        self._best_effort_audit(
            "login_success",
            now,
            result="success",
            target_account_id=account.account_id,
            request_id=request_id,
        )
        resolved = ResolvedSession(account, expires_at)
        return {
            "session_token": token,
            "expires_at": expires_at.isoformat(),
            "principal": resolved.safe_principal(),
        }

    def resolve_session(self, token: Any) -> ResolvedSession:
        if not _valid_session_token(token):
            raise SessionInvalid("dashboard session is invalid")
        now = self.clock()
        session = self.repository.get_session(_digest(token))
        if not session:
            raise SessionInvalid("dashboard session is invalid")
        expires_at = _as_utc(session.get("expires_at"))
        if session.get("revoked_at") is not None or expires_at <= now:
            if expires_at <= now:
                self._best_effort_audit(
                    "session_expired",
                    now,
                    result="expired",
                    target_account_id=str(session.get("account_id", "")) or None,
                )
            raise SessionInvalid("dashboard session is invalid")
        try:
            account = self.repository.get_account(
                str(session.get("account_id", ""))
            )
        except CorruptAccountError as exc:
            raise SessionInvalid("dashboard session is invalid") from exc
        if (
            not account
            or not account.active
            or int(session.get("session_version", -1)) != account.session_version
        ):
            raise SessionInvalid("dashboard session is invalid")
        return ResolvedSession(account, expires_at)

    def logout(self, token: Any, *, request_id: str = "") -> None:
        if not _valid_session_token(token):
            raise SessionInvalid("dashboard session is invalid")
        now = self.clock()
        actor_account_id = None
        try:
            actor_account_id = self.resolve_session(token).account.account_id
        except SessionInvalid:
            pass
        revoked = self.repository.revoke_session(_digest(token), now)
        if revoked and actor_account_id:
            self._best_effort_audit(
                "logout",
                now,
                result="success",
                actor_account_id=actor_account_id,
                request_id=request_id,
            )

    def revoke_all_sessions(self, actor_account_id: str, target_account_id: str) -> Account:
        self._require_actor_capability(
            actor_account_id, AUTH_SESSIONS_REVOKE_ALL
        )
        account = self._require_account(target_account_id)
        updated = account.with_security_change(now=self.clock())
        self.repository.update_account(
            updated,
            account.session_version,
            SecurityAuditEvent.create(
                "sessions_revoked_all",
                self.clock(),
                actor_account_id=actor_account_id,
                target_account_id=target_account_id,
            ),
        )
        return updated

    def reset_password(
        self, actor_account_id: str, target_account_id: str, password: str
    ) -> Account:
        self._require_actor_capability(actor_account_id, ACCOUNTS_MANAGE)
        account = self._require_account(target_account_id)
        updated = account.with_security_change(
            now=self.clock(),
            password_hash=hash_password(password, account.username),
        )
        self.repository.update_account(
            updated,
            account.session_version,
            SecurityAuditEvent.create(
                "password_reset",
                self.clock(),
                actor_account_id=actor_account_id,
                target_account_id=target_account_id,
            ),
        )
        return updated

    def set_account_status(
        self, actor_account_id: str, target_account_id: str, status: str
    ) -> Account:
        self._require_actor_capability(actor_account_id, ACCOUNTS_MANAGE)
        account = self._require_account(target_account_id)
        updated = account.with_security_change(now=self.clock(), status=status)
        event_type = "account_enabled" if status == "active" else "account_disabled"
        self.repository.update_account(
            updated,
            account.session_version,
            SecurityAuditEvent.create(
                event_type,
                self.clock(),
                actor_account_id=actor_account_id,
                target_account_id=target_account_id,
            ),
        )
        return updated

    def change_role(
        self,
        actor_account_id: str,
        target_account_id: str,
        role: str,
        class_ids: list[str],
    ) -> Account:
        self._require_actor_capability(actor_account_id, ACCOUNTS_MANAGE)
        account = self._require_account(target_account_id)
        updated = account.with_security_change(
            now=self.clock(), role=role, class_ids=class_ids
        )
        self.repository.update_account(
            updated,
            account.session_version,
            SecurityAuditEvent.create(
                "role_changed",
                self.clock(),
                actor_account_id=actor_account_id,
                target_account_id=target_account_id,
            ),
        )
        return updated

    def replace_assignments(
        self, actor_account_id: str, target_account_id: str, class_ids: list[str]
    ) -> Account:
        self._require_actor_capability(actor_account_id, ASSIGNMENTS_MANAGE)
        account = self._require_account(target_account_id)
        updated = account.with_security_change(now=self.clock(), class_ids=class_ids)
        self.repository.update_account(
            updated,
            account.session_version,
            SecurityAuditEvent.create(
                "assignments_changed",
                self.clock(),
                actor_account_id=actor_account_id,
                target_account_id=target_account_id,
            ),
        )
        return updated

    def safe_account_summary(self, account_id: str) -> dict[str, Any]:
        return self._require_account(account_id).safe_summary()

    def _require_account(self, account_id: str) -> Account:
        account = self.repository.get_account(account_id)
        if not account:
            raise AccountNotFound("account was not found")
        return account

    def _require_actor_capability(
        self, actor_account_id: str, capability: str
    ) -> Account:
        actor = self._require_account(actor_account_id)
        if not authorize(actor, capability):
            self._best_effort_audit(
                "authorization_denied",
                self.clock(),
                result="denied",
                actor_account_id=actor.account_id,
                target_account_id=actor.account_id,
            )
            raise AuthorizationDenied("account is not authorized")
        return actor

    def _record_unknown_login_failure(self, request_id: str) -> None:
        self.audit_state.record_unknown_login_failure()
        logger.warning(
            "Dashboard login rejected for unresolved identity request_id=%s",
            request_id,
        )

    def _best_effort_audit(
        self,
        event_type: str,
        now: datetime.datetime,
        *,
        result: str,
        actor_account_id: str | None = None,
        target_account_id: str | None = None,
        request_id: str = "",
    ) -> None:
        try:
            self.repository.write_audit(
                SecurityAuditEvent.create(
                    event_type,
                    now,
                    result=result,
                    actor_account_id=actor_account_id,
                    target_account_id=target_account_id,
                    request_id=request_id,
                )
            )
            self.audit_state.record_success()
        except Exception:
            self.audit_state.record_failure()
            logger.error(
                "Security audit write failed event_type=%s request_id=%s",
                event_type,
                request_id,
            )


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _valid_session_token(value: Any) -> bool:
    return isinstance(value, str) and bool(SESSION_TOKEN_PATTERN.fullmatch(value))


def _as_utc(value: Any) -> datetime.datetime:
    if isinstance(value, datetime.datetime):
        return value if value.tzinfo else value.replace(tzinfo=datetime.timezone.utc)
    return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
