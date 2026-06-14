"""Domain models and validation for Flask-owned dashboard authentication."""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, replace
from typing import Any, Iterable

from werkzeug.security import check_password_hash, generate_password_hash

from mtc_assistant.invite_codes import is_valid_class_id


USERNAME_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{1,30}[a-z0-9])$")
RESERVED_USERNAMES = frozenset({"root", "system", "api", "anonymous", "support"})
ROLES = frozenset({"student", "teacher", "class_admin", "super_admin"})
ACCOUNT_STATUSES = frozenset({"active", "disabled"})


class InvalidUsernameError(ValueError):
    pass


class InvalidPasswordError(ValueError):
    pass


class InvalidAccountError(ValueError):
    pass


class DuplicateUsernameError(RuntimeError):
    pass


class CorruptAccountError(RuntimeError):
    pass


class AccountConflictError(RuntimeError):
    pass


def normalize_username(value: Any) -> str:
    if not isinstance(value, str):
        raise InvalidUsernameError("username must be a string")
    trimmed = value.strip()
    if not trimmed or not trimmed.isascii():
        raise InvalidUsernameError("username must contain ASCII characters only")
    normalized = trimmed.lower()
    if not USERNAME_PATTERN.fullmatch(normalized):
        raise InvalidUsernameError("username format is invalid")
    if normalized in RESERVED_USERNAMES:
        raise InvalidUsernameError("username is reserved")
    return normalized


def validate_password(password: Any, normalized_username: str) -> str:
    if not isinstance(password, str) or not 12 <= len(password) <= 128:
        raise InvalidPasswordError("password must contain 12 to 128 characters")
    if password.lower() == normalized_username:
        raise InvalidPasswordError("password must not equal username")
    return password


def hash_password(password: Any, normalized_username: str) -> str:
    return generate_password_hash(validate_password(password, normalized_username))


def verify_password(password_hash: str, password: Any) -> bool:
    if not isinstance(password_hash, str) or not isinstance(password, str):
        return False
    try:
        return check_password_hash(password_hash, password)
    except (ValueError, TypeError):
        return False


def normalize_class_ids(role: str, class_ids: Iterable[str]) -> tuple[str, ...]:
    if role not in ROLES:
        raise InvalidAccountError("role is invalid")
    if isinstance(class_ids, (str, bytes)) or class_ids is None:
        raise InvalidAccountError("class assignments must be a collection")
    normalized = tuple(sorted(set(class_ids)))
    if any(not isinstance(value, str) or not is_valid_class_id(value) for value in normalized):
        raise InvalidAccountError("class assignment is invalid")
    count = len(normalized)
    if role == "student" and count > 1:
        raise InvalidAccountError("student may have at most one class")
    if role == "teacher" and count < 1:
        raise InvalidAccountError("teacher requires at least one class")
    if role == "class_admin" and count != 1:
        raise InvalidAccountError("class_admin requires exactly one class")
    if role == "super_admin" and count:
        raise InvalidAccountError("super_admin uses global scope")
    return normalized


@dataclass(frozen=True)
class Account:
    account_id: str
    username: str
    password_hash: str
    role: str
    status: str
    class_ids: tuple[str, ...]
    display_name: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    created_by: str | None
    password_changed_at: datetime.datetime
    session_version: int = 1

    @classmethod
    def create(
        cls,
        account_id: str,
        username: str,
        password_hash: str,
        role: str,
        class_ids: Iterable[str],
        *,
        display_name: str | None = None,
        status: str = "active",
        now: datetime.datetime | None = None,
        created_by: str | None = None,
    ) -> "Account":
        normalized_username = normalize_username(username)
        if status not in ACCOUNT_STATUSES:
            raise InvalidAccountError("account status is invalid")
        if not isinstance(account_id, str) or not account_id:
            raise InvalidAccountError("account_id is required")
        if not isinstance(password_hash, str) or not password_hash:
            raise InvalidAccountError("password_hash is required")
        timestamp = now or datetime.datetime.now(datetime.timezone.utc)
        return cls(
            account_id=account_id,
            username=normalized_username,
            password_hash=password_hash,
            role=role,
            status=status,
            class_ids=normalize_class_ids(role, class_ids),
            display_name=display_name.strip() if isinstance(display_name, str) and display_name.strip() else None,
            created_at=timestamp,
            updated_at=timestamp,
            created_by=created_by,
            password_changed_at=timestamp,
        )

    @property
    def active(self) -> bool:
        return self.status == "active"

    def safe_summary(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "username": self.username,
            "display_name": self.display_name,
            "role": self.role,
            "status": self.status,
            "class_ids": list(self.class_ids),
        }

    def with_security_change(
        self,
        *,
        now: datetime.datetime,
        status: str | None = None,
        role: str | None = None,
        class_ids: Iterable[str] | None = None,
        password_hash: str | None = None,
    ) -> "Account":
        next_role = self.role if role is None else role
        if next_role not in ROLES:
            raise InvalidAccountError("role is invalid")
        next_classes = self.class_ids if class_ids is None else normalize_class_ids(next_role, class_ids)
        next_status = self.status if status is None else status
        if next_status not in ACCOUNT_STATUSES:
            raise InvalidAccountError("account status is invalid")
        if password_hash is not None and (
            not isinstance(password_hash, str) or not password_hash
        ):
            raise InvalidAccountError("password_hash is required")
        return replace(
            self,
            role=next_role,
            status=next_status,
            class_ids=tuple(next_classes),
            password_hash=(
                self.password_hash if password_hash is None else password_hash
            ),
            password_changed_at=now if password_hash is not None else self.password_changed_at,
            session_version=self.session_version + 1,
            updated_at=now,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Account":
        username = normalize_username(data["username"])
        role = data["role"]
        status = data["status"]
        class_ids = normalize_class_ids(role, data.get("class_ids", []))
        if status not in ACCOUNT_STATUSES:
            raise InvalidAccountError("account status is invalid")
        session_version = int(data.get("session_version", 1))
        if session_version < 1:
            raise InvalidAccountError("session_version is invalid")
        return cls(
            account_id=data["account_id"],
            username=username,
            password_hash=data["password_hash"],
            role=role,
            status=status,
            class_ids=class_ids,
            display_name=data.get("display_name"),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            created_by=data.get("created_by"),
            password_changed_at=data["password_changed_at"],
            session_version=session_version,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "username": self.username,
            "password_hash": self.password_hash,
            "role": self.role,
            "status": self.status,
            "class_ids": list(self.class_ids),
            "display_name": self.display_name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "created_by": self.created_by,
            "password_changed_at": self.password_changed_at,
            "session_version": self.session_version,
        }
