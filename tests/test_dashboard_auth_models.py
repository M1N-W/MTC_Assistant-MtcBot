import unittest

from mtc_assistant.dashboard_auth_models import (
    Account,
    InvalidAccountError,
    InvalidPasswordError,
    InvalidUsernameError,
    hash_password,
    normalize_username,
    verify_password,
)
from mtc_assistant.dashboard_authorization import (
    ACCOUNTS_MANAGE,
    AUTH_SESSION_READ_SELF,
    authorize,
    capabilities_for,
)
from mtc_assistant.dashboard_security_audit import SecurityAuditEvent


class DashboardAuthModelsTest(unittest.TestCase):
    def test_username_normalizes_ascii_case_only(self):
        self.assertEqual("teacher.one", normalize_username("  Teacher.One  "))

    def test_username_rejects_unicode_and_invalid_shape(self):
        for value in ("Ｔeacher", "ครูหนึ่ง", ".teacher", "teacher_", "a", "user name", "a@b"):
            with self.subTest(value=value):
                with self.assertRaises(InvalidUsernameError):
                    normalize_username(value)

    def test_username_rejects_reserved_names(self):
        for value in ("root", "SYSTEM", "api", "anonymous", "support"):
            with self.subTest(value=value):
                with self.assertRaises(InvalidUsernameError):
                    normalize_username(value)

    def test_password_hashing_and_validation(self):
        encoded = hash_password("correct horse battery staple", "teacher.one")
        self.assertNotEqual("correct horse battery staple", encoded)
        self.assertTrue(verify_password(encoded, "correct horse battery staple"))
        self.assertFalse(verify_password(encoded, "wrong password"))
        with self.assertRaises(InvalidPasswordError):
            hash_password("too-short", "teacher.one")
        with self.assertRaises(InvalidPasswordError):
            hash_password("teacher.one", "teacher.one")

    def test_role_assignment_invariants(self):
        Account.create("s1", "student.one", "hash", "student", [])
        Account.create("s2", "student.two", "hash", "student", ["mtc13"])
        Account.create("t1", "teacher.one", "hash", "teacher", ["mtc12", "mtc13"])
        Account.create("c1", "class.one", "hash", "class_admin", ["mtc13"])
        Account.create("a1", "admin.one", "hash", "super_admin", [])
        teacher = Account.create(
            "t2", "teacher.two", "hash", "teacher", ["mtc13", "mtc13"]
        )
        self.assertEqual(("mtc13",), teacher.class_ids)

        invalid = [
            ("teacher", []),
            ("class_admin", []),
            ("class_admin", ["mtc12", "mtc13"]),
            ("student", ["mtc12", "mtc13"]),
            ("super_admin", ["mtc13"]),
            ("unknown", []),
            ("teacher", ["bad id"]),
        ]
        for role, class_ids in invalid:
            with self.subTest(role=role, class_ids=class_ids):
                with self.assertRaises(InvalidAccountError):
                    Account.create("x", "valid.user", "hash", role, class_ids)

    def test_security_change_rejects_explicit_empty_values(self):
        account = Account.create(
            "t1", "teacher.one", "hash", "teacher", ["mtc13"]
        )
        for kwargs in (
            {"role": ""},
            {"status": ""},
            {"password_hash": ""},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(InvalidAccountError):
                    account.with_security_change(now=account.updated_at, **kwargs)
                self.assertEqual(1, account.session_version)

    def test_security_change_none_values_leave_fields_unchanged(self):
        account = Account.create(
            "t1", "teacher.one", "hash", "teacher", ["mtc13"]
        )
        changed = account.with_security_change(
            now=account.updated_at,
            role=None,
            status=None,
            password_hash=None,
        )
        self.assertEqual(account.role, changed.role)
        self.assertEqual(account.status, changed.status)
        self.assertEqual(account.password_hash, changed.password_hash)
        self.assertEqual(2, changed.session_version)

    def test_audit_event_results_follow_event_semantics(self):
        expected = {
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
        for event_type, result in expected.items():
            with self.subTest(event_type=event_type):
                event = SecurityAuditEvent.create(
                    event_type, Account.create(
                        "a1", "admin.one", "hash", "super_admin", []
                    ).created_at
                )
                self.assertEqual(result, event.to_dict()["result"])

    def test_audit_event_rejects_invalid_result(self):
        account = Account.create(
            "a1", "admin.one", "hash", "super_admin", []
        )
        for result in ("success", ""):
            with self.subTest(result=result):
                with self.assertRaises(ValueError):
                    SecurityAuditEvent.create(
                        "login_failure", account.created_at, result=result
                    )

    def test_safe_summary_excludes_security_fields(self):
        account = Account.create(
            "t1", "teacher.one", "secret-hash", "teacher", ["mtc13"], display_name="ครูหนึ่ง"
        )
        summary = account.safe_summary()
        self.assertNotIn("password_hash", summary)
        self.assertNotIn("session_version", summary)
        self.assertEqual(["mtc13"], summary["class_ids"])

    def test_foundation_capabilities_and_scope(self):
        teacher = Account.create("t1", "teacher.one", "hash", "teacher", ["mtc13"])
        class_admin = Account.create(
            "c1", "class.one", "hash", "class_admin", ["mtc13"]
        )
        admin = Account.create("a1", "admin.one", "hash", "super_admin", [])
        self.assertEqual({AUTH_SESSION_READ_SELF, "auth.session.revoke_self"}, capabilities_for(teacher))
        self.assertIn(ACCOUNTS_MANAGE, capabilities_for(admin))
        self.assertTrue(authorize(teacher, AUTH_SESSION_READ_SELF, "mtc13"))
        self.assertFalse(authorize(teacher, AUTH_SESSION_READ_SELF, "mtc12"))
        self.assertTrue(
            authorize(class_admin, AUTH_SESSION_READ_SELF, "mtc13")
        )
        self.assertFalse(
            authorize(class_admin, AUTH_SESSION_READ_SELF, "mtc12")
        )
        self.assertTrue(authorize(admin, AUTH_SESSION_READ_SELF, "mtc99"))
        self.assertFalse(authorize(teacher, "unknown.capability", "mtc13"))
        disabled = teacher.with_security_change(
            now=teacher.updated_at, status="disabled"
        )
        self.assertEqual(set(), capabilities_for(disabled))
        self.assertFalse(authorize(disabled, AUTH_SESSION_READ_SELF, "mtc13"))


if __name__ == "__main__":
    unittest.main()
