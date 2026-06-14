import datetime
import unittest
from unittest.mock import patch

from mtc_assistant.dashboard_auth_models import (
    Account,
    AccountConflictError,
    CorruptAccountError,
    DuplicateUsernameError,
    hash_password,
    verify_password,
)
from mtc_assistant.dashboard_auth_service import (
    AuthenticationFailed,
    AuthorizationDenied,
    DashboardAuthService,
    SessionInvalid,
)


UTC = datetime.timezone.utc


class MemoryRepository:
    def __init__(self):
        self.accounts = {}
        self.usernames = {}
        self.sessions = {}
        self.throttles = {}
        self.audits = []
        self.read_count = 0

    def get_account_id_by_username_digest(self, digest):
        return self.usernames.get(digest)

    def get_account(self, account_id):
        self.read_count += 1
        return self.accounts.get(account_id)

    def create_account(self, account, username_digest, audit):
        if username_digest in self.usernames:
            raise DuplicateUsernameError("duplicate username")
        self.accounts[account.account_id] = account
        self.usernames[username_digest] = account.account_id
        self.audits.append(audit)

    def update_account(self, account, expected_previous_version, audit):
        current = self.accounts.get(account.account_id)
        if (
            current is None
            or current.session_version != expected_previous_version
            or account.session_version != expected_previous_version + 1
        ):
            raise AccountConflictError("account version conflict")
        self.accounts[account.account_id] = account
        self.audits.append(audit)

    def get_session(self, token_digest):
        self.read_count += 1
        return self.sessions.get(token_digest)

    def put_session(self, token_digest, session):
        self.sessions[token_digest] = session

    def revoke_session(self, token_digest, revoked_at):
        session = self.sessions.get(token_digest)
        if not session or session.get("revoked_at") is not None:
            return False
        session["revoked_at"] = revoked_at
        return True

    def get_throttle(self, username_digest):
        return self.throttles.get(username_digest)

    def put_throttle(self, username_digest, state):
        self.throttles[username_digest] = state

    def record_login_failure(self, username_digest, now):
        current = self.throttles.get(username_digest, {})
        window_started = current.get("window_started_at", now)
        if now - window_started >= datetime.timedelta(minutes=15):
            window_started = now
            failed_count = 0
        else:
            failed_count = current.get("failed_count", 0)
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
        self.throttles[username_digest] = state
        return state

    def clear_throttle(self, username_digest):
        self.throttles.pop(username_digest, None)

    def write_audit(self, audit):
        self.audits.append(audit)


class DashboardAuthServiceTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime.datetime(2026, 6, 14, 4, 0, tzinfo=UTC)
        self.repo = MemoryRepository()
        self.service = DashboardAuthService(self.repo, clock=lambda: self.now)
        self.admin = Account.create(
            "admin-1",
            "admin.one",
            hash_password("admin horse battery staple", "admin.one"),
            "super_admin",
            [],
            now=self.now,
        )
        self.repo.accounts[self.admin.account_id] = self.admin
        self.account = self.service.create_account(
            actor_account_id=self.admin.account_id,
            username="Teacher.One",
            password="correct horse battery staple",
            role="teacher",
            class_ids=["mtc13"],
            display_name="Teacher One",
        )

    def test_unknown_and_invalid_usernames_do_not_create_throttle_documents(self):
        initial_audits = len(self.repo.audits)
        initial_accounts = dict(self.repo.accounts)
        initial_usernames = dict(self.repo.usernames)
        initial_sessions = dict(self.repo.sessions)
        for username in ("unknown.user", "ชื่อผู้ใช้"):
            with self.subTest(username=username):
                with self.assertRaises(AuthenticationFailed):
                    self.service.login(username, "incorrect password")
        self.assertEqual({}, self.repo.throttles)
        self.assertEqual(initial_audits, len(self.repo.audits))
        self.assertEqual(initial_accounts, self.repo.accounts)
        self.assertEqual(initial_usernames, self.repo.usernames)
        self.assertEqual(initial_sessions, self.repo.sessions)
        self.assertEqual(
            2,
            self.service.audit_state.snapshot()["unknown_login_failures"],
        )

    def test_unknown_login_log_is_redacted(self):
        username = "missing.sensitive"
        password = "sensitive password value"
        with self.assertLogs(
            "mtc_assistant.dashboard_auth_service", level="WARNING"
        ) as captured:
            with self.assertRaises(AuthenticationFailed):
                self.service.login(username, password, request_id="request-1")
        output = "\n".join(captured.output)
        self.assertNotIn(username, output)
        self.assertNotIn(password, output)
        self.assertIn("request-1", output)

    def test_real_account_throttles_after_five_failures_and_success_clears_state(self):
        for _ in range(5):
            with self.assertRaises(AuthenticationFailed):
                self.service.login("teacher.one", "incorrect password")
        with self.assertRaises(AuthenticationFailed):
            self.service.login("teacher.one", "correct horse battery staple")
        self.now += datetime.timedelta(minutes=16)
        result = self.service.login("teacher.one", "correct horse battery staple")
        self.assertNotIn(next(iter(self.repo.usernames)), self.repo.throttles)
        self.assertIn("session_token", result)

    def test_each_login_path_verifies_exactly_one_password_hash(self):
        digest = next(iter(self.repo.usernames))
        scenarios = []

        scenarios.append(
            ("invalid", lambda: self.service.login("ชื่อผู้ใช้", "incorrect password"))
        )
        scenarios.append(
            ("unknown", lambda: self.service.login("missing.user", "incorrect password"))
        )

        self.repo.throttles[digest] = {
            "blocked_until": self.now + datetime.timedelta(minutes=1)
        }
        scenarios.append(
            ("blocked", lambda: self.service.login("teacher.one", "incorrect password"))
        )

        def valid_login():
            self.repo.throttles.pop(digest, None)
            return self.service.login(
                "teacher.one", "correct horse battery staple"
            )

        scenarios.append(("valid", valid_login))

        original_get_account = self.repo.get_account

        def corrupt_login():
            def corrupt(account_id):
                if account_id == self.account.account_id:
                    raise CorruptAccountError("corrupt")
                return original_get_account(account_id)

            self.repo.get_account = corrupt
            try:
                return self.service.login(
                    "teacher.one", "incorrect password"
                )
            finally:
                self.repo.get_account = original_get_account

        scenarios.append(("corrupt", corrupt_login))

        for name, attempt in scenarios:
            with self.subTest(name=name):
                with patch(
                    "mtc_assistant.dashboard_auth_service.verify_password",
                    wraps=verify_password,
                ) as password_check:
                    if name == "valid":
                        attempt()
                    else:
                        with self.assertRaises(AuthenticationFailed):
                            attempt()
                    self.assertEqual(1, password_check.call_count)

    def test_disabled_account_uses_generic_authentication_failure(self):
        self.service.set_account_status(
            self.admin.account_id, self.account.account_id, "disabled"
        )
        with self.assertRaises(AuthenticationFailed):
            self.service.login(
                "teacher.one", "correct horse battery staple"
            )

    def test_orphan_username_reservation_creates_no_durable_failure_records(self):
        account_id = self.repo.usernames[next(iter(self.repo.usernames))]
        self.repo.accounts.pop(account_id)
        initial_audits = len(self.repo.audits)
        with self.assertRaises(AuthenticationFailed):
            self.service.login(
                "teacher.one", "correct horse battery staple"
            )
        self.assertEqual({}, self.repo.throttles)
        self.assertEqual(initial_audits, len(self.repo.audits))

    def test_session_token_is_not_stored_and_resolution_uses_two_reads(self):
        result = self.service.login("teacher.one", "correct horse battery staple")
        raw_token = result["session_token"]
        self.assertEqual(43, len(raw_token))
        self.assertTrue(raw_token.isascii())
        self.assertNotIn(raw_token, str(self.repo.sessions))
        self.assertNotIn(token_digest := next(iter(self.repo.sessions)), str(result))
        self.assertEqual("login_success", self.repo.audits[-1].event_type)
        self.repo.read_count = 0
        principal = self.service.resolve_session(raw_token)
        self.assertEqual("t" if False else self.account.account_id, principal.account.account_id)
        self.assertEqual(2, self.repo.read_count)

    def test_revoke_one_and_revoke_all(self):
        first = self.service.login("teacher.one", "correct horse battery staple")
        self.service.logout(first["session_token"])
        self.assertEqual(
            self.account.account_id, self.repo.audits[-1].actor_account_id
        )
        audit_count = len(self.repo.audits)
        self.service.logout(first["session_token"])
        self.assertEqual(audit_count, len(self.repo.audits))
        with self.assertRaises(SessionInvalid):
            self.service.resolve_session(first["session_token"])

        second = self.service.login("teacher.one", "correct horse battery staple")
        self.service.revoke_all_sessions(self.admin.account_id, self.account.account_id)
        with self.assertRaises(SessionInvalid):
            self.service.resolve_session(second["session_token"])

    def test_best_effort_audit_results_match_denial_and_expiry_semantics(self):
        with self.assertRaises(AuthenticationFailed):
            self.service.login("teacher.one", "incorrect password")
        self.assertEqual("failure", self.repo.audits[-1].result)

        with self.assertRaises(AuthorizationDenied):
            self.service.reset_password(
                self.account.account_id,
                self.account.account_id,
                "another horse battery staple",
            )
        self.assertEqual("denied", self.repo.audits[-1].result)

        session = self.service.login(
            "teacher.one", "correct horse battery staple"
        )
        self.now += datetime.timedelta(hours=13)
        with self.assertRaises(SessionInvalid):
            self.service.resolve_session(session["session_token"])
        self.assertEqual("expired", self.repo.audits[-1].result)

    def test_stale_service_mutation_does_not_overwrite_or_audit(self):
        stale_account = self.repo.accounts[self.account.account_id]
        first = stale_account.with_security_change(
            now=self.now + datetime.timedelta(minutes=1),
            status="disabled",
        )
        self.repo.accounts[self.account.account_id] = first
        audit_count = len(self.repo.audits)

        with patch.object(
            self.service,
            "_require_actor_capability",
            return_value=self.admin,
        ), patch.object(
            self.service, "_require_account", return_value=stale_account
        ):
            with self.assertRaises(AccountConflictError):
                self.service.reset_password(
                    self.admin.account_id,
                    self.account.account_id,
                    "different horse battery staple",
                )

        self.assertEqual(first, self.repo.accounts[self.account.account_id])
        self.assertEqual(audit_count, len(self.repo.audits))

    def test_password_reset_revokes_existing_sessions(self):
        session = self.service.login("teacher.one", "correct horse battery staple")
        self.service.reset_password(
            self.admin.account_id,
            self.account.account_id,
            "different horse battery staple",
        )
        with self.assertRaises(SessionInvalid):
            self.service.resolve_session(session["session_token"])
        with self.assertRaises(AuthenticationFailed):
            self.service.login("teacher.one", "correct horse battery staple")
        self.service.login("teacher.one", "different horse battery staple")

    def test_every_privileged_security_change_revokes_existing_sessions(self):
        operations = (
            lambda: self.service.change_role(
                self.admin.account_id,
                self.account.account_id,
                "teacher",
                ["mtc12"],
            ),
            lambda: self.service.replace_assignments(
                self.admin.account_id,
                self.account.account_id,
                ["mtc13"],
            ),
            lambda: self.service.revoke_all_sessions(
                self.admin.account_id, self.account.account_id
            ),
        )
        for operation in operations:
            with self.subTest(operation=operation):
                session = self.service.login(
                    "teacher.one", "correct horse battery staple"
                )
                before = self.repo.accounts[
                    self.account.account_id
                ].session_version
                operation()
                after = self.repo.accounts[
                    self.account.account_id
                ].session_version
                self.assertEqual(before + 1, after)
                with self.assertRaises(SessionInvalid):
                    self.service.resolve_session(session["session_token"])

    def test_disable_then_enable_does_not_reactivate_old_session(self):
        session = self.service.login(
            "teacher.one", "correct horse battery staple"
        )
        original_version = self.repo.accounts[
            self.account.account_id
        ].session_version
        self.service.set_account_status(
            self.admin.account_id, self.account.account_id, "disabled"
        )
        self.service.set_account_status(
            self.admin.account_id, self.account.account_id, "active"
        )
        self.assertEqual(
            original_version + 2,
            self.repo.accounts[self.account.account_id].session_version,
        )
        with self.assertRaises(SessionInvalid):
            self.service.resolve_session(session["session_token"])

    def test_expired_disabled_and_version_mismatched_sessions_fail(self):
        expired = self.service.login("teacher.one", "correct horse battery staple")
        self.now += datetime.timedelta(hours=13)
        with self.assertRaises(SessionInvalid):
            self.service.resolve_session(expired["session_token"])

        self.now -= datetime.timedelta(hours=13)
        disabled = self.service.login("teacher.one", "correct horse battery staple")
        self.service.set_account_status(
            self.admin.account_id, self.account.account_id, "disabled"
        )
        with self.assertRaises(SessionInvalid):
            self.service.resolve_session(disabled["session_token"])

    def test_malformed_and_unknown_sessions_fail(self):
        for token in ("", "short", "!" * 43, "x" * 43):
            with self.subTest(token=token):
                self.repo.read_count = 0
                with self.assertRaises(SessionInvalid):
                    self.service.resolve_session(token)
                expected_reads = 0 if token != "x" * 43 else 1
                self.assertEqual(expected_reads, self.repo.read_count)

    def test_unknown_logout_does_not_create_durable_audit(self):
        initial_audits = len(self.repo.audits)
        self.service.logout("x" * 43)
        self.assertEqual(initial_audits, len(self.repo.audits))

    def test_best_effort_audit_failure_does_not_block_logout(self):
        session = self.service.login("teacher.one", "correct horse battery staple")

        def fail_audit(audit):
            raise RuntimeError("audit unavailable")

        self.repo.write_audit = fail_audit
        with self.assertLogs(
            "mtc_assistant.dashboard_auth_service", level="ERROR"
        ) as captured:
            self.service.logout(session["session_token"])
        self.assertNotIn(
            session["session_token"], "\n".join(captured.output)
        )
        self.assertFalse(self.service.audit_state.snapshot()["security_audit"])
        self.assertEqual(
            1,
            self.service.audit_state.snapshot()["security_audit_write_failures"],
        )

    def test_login_success_survives_audit_failure_and_degrades_only_audit(self):
        self.repo.write_audit = lambda audit: (_ for _ in ()).throw(
            RuntimeError("audit unavailable")
        )
        result = self.service.login(
            "teacher.one", "correct horse battery staple"
        )
        self.assertIn("session_token", result)
        self.assertFalse(
            self.service.audit_state.snapshot()["security_audit"]
        )

    def test_existing_account_login_failure_survives_audit_failure(self):
        self.repo.write_audit = lambda audit: (_ for _ in ()).throw(
            RuntimeError("audit unavailable")
        )
        with self.assertRaises(AuthenticationFailed):
            self.service.login("teacher.one", "wrong password")
        self.assertEqual(1, len(self.repo.throttles))
        self.assertFalse(
            self.service.audit_state.snapshot()["security_audit"]
        )

    def test_non_super_admin_cannot_manage_accounts(self):
        with self.assertRaises(AuthorizationDenied):
            self.service.create_account(
                self.account.account_id,
                "second.teacher",
                "another horse battery staple",
                "teacher",
                ["mtc13"],
            )
        with self.assertRaises(AuthorizationDenied):
            self.service.reset_password(
                self.account.account_id,
                self.account.account_id,
                "another horse battery staple",
            )

    def test_corrupt_account_state_is_generic_login_failure(self):
        original = self.repo.get_account

        def corrupt(account_id):
            if account_id == self.account.account_id:
                raise CorruptAccountError("corrupt")
            return original(account_id)

        self.repo.get_account = corrupt
        with self.assertRaises(AuthenticationFailed):
            self.service.login("teacher.one", "correct horse battery staple")

    def test_expired_session_audit_failure_does_not_change_denial(self):
        session = self.service.login(
            "teacher.one", "correct horse battery staple"
        )
        self.now += datetime.timedelta(hours=13)
        self.repo.write_audit = lambda audit: (_ for _ in ()).throw(
            RuntimeError("audit unavailable")
        )
        with self.assertRaises(SessionInvalid):
            self.service.resolve_session(session["session_token"])
        self.assertFalse(
            self.service.audit_state.snapshot()["security_audit"]
        )

    def test_authorization_denial_audit_failure_does_not_grant_access(self):
        self.repo.write_audit = lambda audit: (_ for _ in ()).throw(
            RuntimeError("audit unavailable")
        )
        with self.assertRaises(AuthorizationDenied):
            self.service.reset_password(
                self.account.account_id,
                self.account.account_id,
                "another horse battery staple",
            )
        self.assertFalse(
            self.service.audit_state.snapshot()["security_audit"]
        )

    def test_audit_payloads_never_contain_session_material(self):
        result = self.service.login(
            "teacher.one", "correct horse battery staple"
        )
        raw_token = result["session_token"]
        token_digest = next(iter(self.repo.sessions))
        for audit in self.repo.audits:
            serialized = str(audit.to_dict())
            self.assertNotIn(raw_token, serialized)
            self.assertNotIn(token_digest, serialized)

    def test_unrelated_repository_failure_is_not_reported_as_duplicate(self):
        original = self.repo.create_account

        def fail(*args):
            raise RuntimeError("firestore unavailable")

        self.repo.create_account = fail
        with self.assertRaises(RuntimeError):
            self.service.create_account(
                self.admin.account_id,
                "second.teacher",
                "another horse battery staple",
                "teacher",
                ["mtc13"],
            )
        self.repo.create_account = original


if __name__ == "__main__":
    unittest.main()
