import datetime
import unittest

from mtc_assistant.dashboard_auth_models import (
    Account,
    AccountConflictError,
    CorruptAccountError,
    DuplicateUsernameError,
)
from mtc_assistant.dashboard_auth_repository import FirestoreDashboardAuthRepository
from mtc_assistant.dashboard_security_audit import SecurityAuditEvent


UTC = datetime.timezone.utc


class FakeSnapshot:
    def __init__(self, data=None):
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return dict(self._data or {})


class FakeDoc:
    def __init__(self, db, path):
        self.db = db
        self.path = path

    def collection(self, name):
        return FakeCollection(self.db, f"{self.path}/{name}")

    def get(self, transaction=None):
        return FakeSnapshot(self.db.documents.get(self.path))

    def set(self, data, merge=False):
        current = self.db.documents.get(self.path, {}) if merge else {}
        self.db.documents[self.path] = {**current, **data}

    def delete(self):
        self.db.documents.pop(self.path, None)


class FakeCollection:
    def __init__(self, db, path):
        self.db = db
        self.path = path

    def document(self, doc_id):
        return FakeDoc(self.db, f"{self.path}/{doc_id}")


class FakeTransaction:
    def __init__(self, db):
        self.db = db
        self.writes = []

    def get(self, doc):
        if self.writes:
            raise AssertionError("transaction read occurred after a write")
        return doc.get()

    def set(self, doc, data, merge=False):
        self.writes.append((doc, data, merge))

    def commit(self):
        if self.db.fail_commit:
            raise RuntimeError("transaction commit failed")
        for doc, data, merge in self.writes:
            doc.set(data, merge=merge)


class FakeDb:
    project = "fake-project"

    def __init__(self):
        self.documents = {}
        self.last_transaction = None
        self.fail_commit = False

    def collection(self, name):
        return FakeCollection(self, name)

    def transaction(self):
        self.last_transaction = FakeTransaction(self)
        return self.last_transaction


class DashboardAuthRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.db = FakeDb()
        self.repo = FirestoreDashboardAuthRepository(lambda: self.db)
        self.now = datetime.datetime(2026, 6, 14, tzinfo=UTC)
        self.account = Account.create(
            "account-1", "valid.user", "password-hash", "super_admin", [], now=self.now
        )
        self.audit = SecurityAuditEvent.create(
            "account_created", self.now, target_account_id="account-1"
        )

    def test_create_account_writes_account_reservation_and_audit_atomically(self):
        self.repo.create_account(self.account, "username-digest", self.audit)
        reservation = self.db.documents[
            "system/dashboard_auth/usernames/username-digest"
        ]
        self.assertEqual(
            "account-1",
            reservation["account_id"],
        )
        self.assertEqual(
            {"account_id", "created_at"},
            set(reservation),
        )
        self.assertIn(
            "system/dashboard_security/audit_events/" + self.audit.event_id,
            self.db.documents,
        )

    def test_duplicate_username_rolls_back(self):
        self.db.documents["system/dashboard_auth/usernames/username-digest"] = {
            "account_id": "existing"
        }
        with self.assertRaises(DuplicateUsernameError):
            self.repo.create_account(self.account, "username-digest", self.audit)
        self.assertNotIn(
            "system/dashboard_auth/accounts/account-1", self.db.documents
        )

    def test_malformed_account_role_is_rejected(self):
        data = self.account.to_dict()
        data["role"] = "unknown"
        self.db.documents[
            "system/dashboard_auth/accounts/account-1"
        ] = data
        with self.assertRaises(CorruptAccountError):
            self.repo.get_account("account-1")

    def test_session_path_uses_token_digest_as_document_id(self):
        self.repo.put_session("token-digest", {"account_id": "account-1"})
        self.assertIn(
            "system/dashboard_auth/sessions/token-digest", self.db.documents
        )
        self.assertNotIn("raw-token", str(self.db.documents))

    def test_revoke_session_is_storage_idempotent(self):
        path = "system/dashboard_auth/sessions/token-digest"
        self.db.documents[path] = {
            "account_id": "account-1",
            "revoked_at": None,
        }
        first_revoked_at = self.now
        self.assertTrue(
            self.repo.revoke_session("token-digest", first_revoked_at)
        )
        write_count = len(self.db.last_transaction.writes)
        self.assertFalse(
            self.repo.revoke_session(
                "token-digest", self.now + datetime.timedelta(minutes=1)
            )
        )
        self.assertEqual(first_revoked_at, self.db.documents[path]["revoked_at"])
        self.assertEqual(0, len(self.db.last_transaction.writes))
        self.assertEqual(1, write_count)

    def test_revoke_missing_session_performs_no_write(self):
        self.assertFalse(self.repo.revoke_session("missing", self.now))
        self.assertEqual([], self.db.last_transaction.writes)

    def test_record_login_failure_uses_transaction_and_sets_bounded_state(self):
        state = self.repo.record_login_failure("username-digest", self.now)
        self.assertEqual(1, state["failed_count"])
        self.assertIsNotNone(self.db.last_transaction)
        self.assertEqual(
            1,
            self.db.documents[
                "system/dashboard_auth/login_throttles/username-digest"
            ]["failed_count"],
        )

    def test_bootstrap_writes_guard_reservation_account_and_audit_atomically(self):
        self.repo.bootstrap_super_admin(
            self.account, "username-digest", self.audit
        )
        expected_paths = {
            "system/dashboard_auth/guards/super_admin_bootstrap",
            "system/dashboard_auth/usernames/username-digest",
            "system/dashboard_auth/accounts/account-1",
            "system/dashboard_security/audit_events/" + self.audit.event_id,
        }
        self.assertTrue(expected_paths.issubset(self.db.documents))
        reservation = self.db.documents[
            "system/dashboard_auth/usernames/username-digest"
        ]
        self.assertEqual({"account_id", "created_at"}, set(reservation))

    def test_account_creation_commit_failure_leaves_no_partial_writes(self):
        self.db.fail_commit = True
        with self.assertRaises(RuntimeError):
            self.repo.create_account(
                self.account, "username-digest", self.audit
            )
        self.assertEqual({}, self.db.documents)

    def test_bootstrap_commit_failure_leaves_no_partial_writes(self):
        self.db.fail_commit = True
        with self.assertRaises(RuntimeError):
            self.repo.bootstrap_super_admin(
                self.account, "username-digest", self.audit
            )
        self.assertEqual({}, self.db.documents)

    def test_existing_bootstrap_guard_leaves_storage_unchanged(self):
        guard_path = "system/dashboard_auth/guards/super_admin_bootstrap"
        self.db.documents[guard_path] = {"account_id": "existing"}
        before = dict(self.db.documents)
        with self.assertRaises(ValueError):
            self.repo.bootstrap_super_admin(
                self.account, "username-digest", self.audit
            )
        self.assertEqual(before, self.db.documents)

    def test_account_update_commit_failure_preserves_account_and_audit(self):
        account_path = "system/dashboard_auth/accounts/account-1"
        self.db.documents[account_path] = self.account.to_dict()
        before = dict(self.db.documents)
        self.db.fail_commit = True
        changed = self.account.with_security_change(
            now=self.now + datetime.timedelta(minutes=1),
            status="disabled",
        )
        with self.assertRaises(RuntimeError):
            self.repo.update_account(
                changed, self.account.session_version, self.audit
            )
        self.assertEqual(before, self.db.documents)

    def test_stale_account_update_changes_nothing_and_writes_no_audit(self):
        account_path = "system/dashboard_auth/accounts/account-1"
        self.db.documents[account_path] = self.account.to_dict()
        first = self.account.with_security_change(
            now=self.now + datetime.timedelta(minutes=1),
            status="disabled",
        )
        first_audit = SecurityAuditEvent.create(
            "account_disabled", first.updated_at, target_account_id="account-1"
        )
        self.repo.update_account(
            first, self.account.session_version, first_audit
        )
        after_first = dict(self.db.documents)

        stale = self.account.with_security_change(
            now=self.now + datetime.timedelta(minutes=2),
            password_hash="replacement-hash",
        )
        stale_audit = SecurityAuditEvent.create(
            "password_reset", stale.updated_at, target_account_id="account-1"
        )
        with self.assertRaises(AccountConflictError):
            self.repo.update_account(
                stale, self.account.session_version, stale_audit
            )

        self.assertEqual(after_first, self.db.documents)
        self.assertNotIn(
            "system/dashboard_security/audit_events/" + stale_audit.event_id,
            self.db.documents,
        )

    def test_account_update_rejects_missing_or_invalid_stored_version(self):
        changed = self.account.with_security_change(
            now=self.now + datetime.timedelta(minutes=1),
            status="disabled",
        )
        account_path = "system/dashboard_auth/accounts/account-1"
        for stored in (
            None,
            {"session_version": "not-an-int"},
            {"session_version": self.account.session_version},
        ):
            with self.subTest(stored=stored):
                self.db.documents.clear()
                if stored is not None:
                    self.db.documents[account_path] = stored
                with self.assertRaises(AccountConflictError):
                    self.repo.update_account(
                        changed, self.account.session_version, self.audit
                    )
                self.assertNotIn(
                    "system/dashboard_security/audit_events/"
                    + self.audit.event_id,
                    self.db.documents,
                )


if __name__ == "__main__":
    unittest.main()
