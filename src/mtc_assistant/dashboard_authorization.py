"""Central capability registry and class-scope evaluation."""

from __future__ import annotations

from mtc_assistant.dashboard_auth_models import Account


AUTH_SESSION_READ_SELF = "auth.session.read_self"
AUTH_SESSION_REVOKE_SELF = "auth.session.revoke_self"
ACCOUNTS_MANAGE = "accounts.manage"
ASSIGNMENTS_MANAGE = "assignments.manage"
AUTH_SESSIONS_REVOKE_ALL = "auth.sessions.revoke_all"

CAPABILITY_REGISTRY = frozenset(
    {
        AUTH_SESSION_READ_SELF,
        AUTH_SESSION_REVOKE_SELF,
        ACCOUNTS_MANAGE,
        ASSIGNMENTS_MANAGE,
        AUTH_SESSIONS_REVOKE_ALL,
    }
)

ROLE_CAPABILITIES = {
    "student": frozenset({AUTH_SESSION_READ_SELF, AUTH_SESSION_REVOKE_SELF}),
    "teacher": frozenset({AUTH_SESSION_READ_SELF, AUTH_SESSION_REVOKE_SELF}),
    "class_admin": frozenset({AUTH_SESSION_READ_SELF, AUTH_SESSION_REVOKE_SELF}),
    "super_admin": CAPABILITY_REGISTRY,
}


def capabilities_for(account: Account) -> set[str]:
    if not account.active:
        return set()
    return set(ROLE_CAPABILITIES.get(account.role, frozenset()))


def authorize(account: Account, capability: str, class_id: str | None = None) -> bool:
    if capability not in CAPABILITY_REGISTRY or capability not in capabilities_for(account):
        return False
    if class_id is None or account.role == "super_admin":
        return True
    return class_id in account.class_ids
