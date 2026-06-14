"""Security audit records and process-local operational visibility."""

from __future__ import annotations

import datetime
import threading
import uuid
from dataclasses import dataclass
from typing import Any


AUDIT_EVENT_RESULTS = {
    "login_success": "success",
    "logout": "success",
    "account_created": "success",
    "account_enabled": "success",
    "account_disabled": "success",
    "password_reset": "success",
    "role_changed": "success",
    "assignments_changed": "success",
    "sessions_revoked_all": "success",
    "super_admin_bootstrap": "success",
    "login_failure": "failure",
    "authorization_denied": "denied",
    "session_expired": "expired",
}


@dataclass(frozen=True)
class SecurityAuditEvent:
    event_id: str
    event_type: str
    actor_account_id: str | None
    target_account_id: str | None
    timestamp: datetime.datetime
    result: str
    request_id: str
    retain_until: datetime.datetime

    @classmethod
    def create(
        cls,
        event_type: str,
        timestamp: datetime.datetime,
        *,
        actor_account_id: str | None = None,
        target_account_id: str | None = None,
        result: str | None = None,
        request_id: str = "",
    ) -> "SecurityAuditEvent":
        expected_result = AUDIT_EVENT_RESULTS.get(event_type)
        resolved_result = expected_result if result is None else result
        if not resolved_result:
            raise ValueError("audit result is required")
        if expected_result is not None and resolved_result != expected_result:
            raise ValueError("audit result does not match event semantics")
        return cls(
            event_id=uuid.uuid4().hex,
            event_type=event_type,
            actor_account_id=actor_account_id,
            target_account_id=target_account_id,
            timestamp=timestamp,
            result=resolved_result,
            request_id=request_id,
            retain_until=timestamp + datetime.timedelta(days=365),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "actor_account_id": self.actor_account_id,
            "target_account_id": self.target_account_id,
            "timestamp": self.timestamp,
            "result": self.result,
            "request_id": self.request_id,
            "retain_until": self.retain_until,
        }


class SecurityAuditOperationalState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._failures = 0
        self._unknown_login_failures = 0
        self._healthy = True

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            self._healthy = False

    def record_success(self) -> None:
        with self._lock:
            self._healthy = True

    def record_unknown_login_failure(self) -> None:
        with self._lock:
            self._unknown_login_failures = min(
                self._unknown_login_failures + 1, (1 << 63) - 1
            )

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "security_audit_write_failures": self._failures,
                "unknown_login_failures": self._unknown_login_failures,
                "security_audit": self._healthy,
            }
