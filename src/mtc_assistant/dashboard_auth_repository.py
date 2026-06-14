"""Firestore persistence for dashboard authentication."""

from __future__ import annotations

import datetime
from typing import Any, Callable

from mtc_assistant.dashboard_auth_models import (
    Account,
    AccountConflictError,
    CorruptAccountError,
    DuplicateUsernameError,
)
from mtc_assistant.dashboard_security_audit import SecurityAuditEvent


DbProvider = Callable[[], Any]


class FirestoreDashboardAuthRepository:
    def __init__(self, get_db: DbProvider) -> None:
        self.get_db = get_db

    def get_account_id_by_username_digest(self, digest: str) -> str | None:
        snapshot = self._doc(f"system/dashboard_auth/usernames/{digest}").get()
        if not getattr(snapshot, "exists", False):
            return None
        data = snapshot.to_dict() or {}
        account_id = data.get("account_id")
        return account_id if isinstance(account_id, str) and account_id else None

    def get_account(self, account_id: str) -> Account | None:
        snapshot = self._doc(f"system/dashboard_auth/accounts/{account_id}").get()
        if not getattr(snapshot, "exists", False):
            return None
        data = snapshot.to_dict()
        if not isinstance(data, dict):
            raise CorruptAccountError("account document is malformed")
        try:
            return Account.from_dict(data)
        except (KeyError, TypeError, ValueError) as exc:
            raise CorruptAccountError("account document is malformed") from exc

    def create_account(
        self,
        account: Account,
        username_digest: str,
        audit: SecurityAuditEvent,
    ) -> None:
        db = self._db()
        transaction = db.transaction()
        reservation = self._doc(
            f"system/dashboard_auth/usernames/{username_digest}", db=db
        )
        if getattr(reservation.get(transaction=transaction), "exists", False):
            raise DuplicateUsernameError("username already exists")
        transaction.set(
            self._doc(
                f"system/dashboard_auth/accounts/{account.account_id}", db=db
            ),
            account.to_dict(),
        )
        transaction.set(
            reservation,
            {
                "account_id": account.account_id,
                "created_at": account.created_at,
            },
        )
        transaction.set(
            self._doc(
                f"system/dashboard_security/audit_events/{audit.event_id}", db=db
            ),
            audit.to_dict(),
        )
        transaction.commit()

    def update_account(
        self,
        account: Account,
        expected_previous_version: int,
        audit: SecurityAuditEvent,
    ) -> None:
        db = self._db()
        transaction = db.transaction()
        account_reference = self._doc(
            f"system/dashboard_auth/accounts/{account.account_id}", db=db
        )
        snapshot = transaction.get(account_reference)
        stored = snapshot.to_dict() if getattr(snapshot, "exists", False) else None
        try:
            stored_account = Account.from_dict(stored)
        except (KeyError, TypeError, ValueError):
            raise AccountConflictError("account state is unavailable")
        stored_version = stored_account.session_version
        if (
            not isinstance(expected_previous_version, int)
            or isinstance(expected_previous_version, bool)
            or stored_account.account_id != account.account_id
            or stored_version != expected_previous_version
            or account.session_version != expected_previous_version + 1
        ):
            raise AccountConflictError("account version conflict")
        transaction.set(
            account_reference,
            account.to_dict(),
        )
        transaction.set(
            self._doc(
                f"system/dashboard_security/audit_events/{audit.event_id}", db=db
            ),
            audit.to_dict(),
        )
        transaction.commit()

    def bootstrap_super_admin(
        self,
        account: Account,
        username_digest: str,
        audit: SecurityAuditEvent,
    ) -> None:
        db = self._db()
        transaction = db.transaction()
        guard = self._doc(
            "system/dashboard_auth/guards/super_admin_bootstrap", db=db
        )
        reservation = self._doc(
            f"system/dashboard_auth/usernames/{username_digest}", db=db
        )
        if getattr(guard.get(transaction=transaction), "exists", False):
            raise ValueError("super admin bootstrap already completed")
        if getattr(reservation.get(transaction=transaction), "exists", False):
            raise ValueError("username already exists")
        transaction.set(
            guard,
            {
                "account_id": account.account_id,
                "created_at": account.created_at,
            },
        )
        transaction.set(
            reservation,
            {
                "account_id": account.account_id,
                "created_at": account.created_at,
            },
        )
        transaction.set(
            self._doc(
                f"system/dashboard_auth/accounts/{account.account_id}", db=db
            ),
            account.to_dict(),
        )
        transaction.set(
            self._doc(
                f"system/dashboard_security/audit_events/{audit.event_id}", db=db
            ),
            audit.to_dict(),
        )
        transaction.commit()

    def get_session(self, token_digest: str) -> dict[str, Any] | None:
        snapshot = self._doc(
            f"system/dashboard_auth/sessions/{token_digest}"
        ).get()
        if not getattr(snapshot, "exists", False):
            return None
        data = snapshot.to_dict()
        return data if isinstance(data, dict) else None

    def put_session(self, token_digest: str, session: dict[str, Any]) -> None:
        self._doc(f"system/dashboard_auth/sessions/{token_digest}").set(session)

    def revoke_session(
        self, token_digest: str, revoked_at: datetime.datetime
    ) -> bool:
        db = self._db()
        transaction = db.transaction()
        reference = self._doc(
            f"system/dashboard_auth/sessions/{token_digest}", db=db
        )
        snapshot = transaction.get(reference)
        if not getattr(snapshot, "exists", False):
            return False
        data = snapshot.to_dict()
        if not isinstance(data, dict) or data.get("revoked_at") is not None:
            return False
        transaction.set(reference, {"revoked_at": revoked_at}, merge=True)
        transaction.commit()
        return True

    def get_throttle(self, username_digest: str) -> dict[str, Any] | None:
        snapshot = self._doc(
            f"system/dashboard_auth/login_throttles/{username_digest}"
        ).get()
        if not getattr(snapshot, "exists", False):
            return None
        data = snapshot.to_dict()
        return data if isinstance(data, dict) else None

    def put_throttle(
        self, username_digest: str, state: dict[str, Any]
    ) -> None:
        self._doc(
            f"system/dashboard_auth/login_throttles/{username_digest}"
        ).set(state)

    def record_login_failure(
        self, username_digest: str, now: datetime.datetime
    ) -> dict[str, Any]:
        db = self._db()
        transaction = db.transaction()
        reference = self._doc(
            f"system/dashboard_auth/login_throttles/{username_digest}", db=db
        )
        snapshot = reference.get(transaction=transaction)
        current = snapshot.to_dict() if getattr(snapshot, "exists", False) else {}
        current = current if isinstance(current, dict) else {}
        window_started = _as_utc(current.get("window_started_at"))
        if (
            window_started > now
            or now - window_started >= datetime.timedelta(minutes=15)
        ):
            window_started = now
            failed_count = 0
        else:
            failed_count = int(current.get("failed_count", 0))
        failed_count += 1
        blocked_until = (
            now + datetime.timedelta(minutes=15)
            if failed_count >= 5
            else now
        )
        state = {
            "window_started_at": window_started,
            "failed_count": failed_count,
            "blocked_until": blocked_until,
            "purge_after": blocked_until + datetime.timedelta(days=1),
        }
        transaction.set(reference, state)
        transaction.commit()
        return state

    def clear_throttle(self, username_digest: str) -> None:
        self._doc(
            f"system/dashboard_auth/login_throttles/{username_digest}"
        ).delete()

    def write_audit(self, audit: SecurityAuditEvent) -> None:
        self._doc(
            f"system/dashboard_security/audit_events/{audit.event_id}"
        ).set(audit.to_dict())

    def project_id(self) -> str:
        project = getattr(self._db(), "project", "")
        if not isinstance(project, str) or not project:
            raise RuntimeError("Firebase project ID is unavailable")
        return project

    def _db(self) -> Any:
        db = self.get_db()
        if db is None:
            raise RuntimeError("Firebase is unavailable")
        return db

    def _doc(self, path: str, *, db: Any = None) -> Any:
        client = db or self._db()
        parts = path.split("/")
        if len(parts) % 2:
            raise ValueError("Firestore document path must end with a document")
        reference = client.collection(parts[0]).document(parts[1])
        for index in range(2, len(parts), 2):
            reference = reference.collection(parts[index]).document(
                parts[index + 1]
            )
        return reference


def _as_utc(value: Any) -> datetime.datetime:
    if isinstance(value, datetime.datetime):
        return value if value.tzinfo else value.replace(tzinfo=datetime.timezone.utc)
    return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
