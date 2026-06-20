import datetime
import unittest
from unittest.mock import patch

from mtc_assistant.config import LOCAL_TZ
from mtc_assistant.invite_codes import (
    is_join_command,
    join_class_with_invite,
    normalize_invite_code,
    parse_join_code,
)


class FakeDocSnapshot:
    def __init__(self, doc):
        self._doc = doc
        self.exists = doc.exists
        self.id = doc.doc_id

    def to_dict(self):
        return dict(self._doc.data)


class FakeDocRef:
    def __init__(self, db, path, doc_id):
        self.db = db
        self.path = path
        self.doc_id = doc_id

    @property
    def exists(self):
        return self.path in self.db.store

    @property
    def data(self):
        return self.db.store.get(self.path, {})

    def get(self):
        return FakeDocSnapshot(self)

    def set(self, data, merge=False):
        if merge:
            current = dict(self.db.store.get(self.path, {}))
            current.update(data)
            self.db.store[self.path] = current
        else:
            self.db.store[self.path] = dict(data)

    def update(self, data):
        current = dict(self.db.store.get(self.path, {}))
        for key, value in data.items():
            if hasattr(value, "operand"):
                current[key] = int(current.get(key, 0) or 0) + int(value.operand)
            elif hasattr(value, "amount"):
                current[key] = int(current.get(key, 0) or 0) + int(value.amount)
            elif hasattr(value, "_value"):
                current[key] = int(current.get(key, 0) or 0) + int(value._value)
            else:
                current[key] = value
        self.db.store[self.path] = current

    def collection(self, name):
        return FakeCollection(self.db, f"{self.path}/{name}")


class FakeCollection:
    def __init__(self, db, path):
        self.db = db
        self.path = path

    def document(self, doc_id):
        return FakeDocRef(self.db, f"{self.path}/{doc_id}", doc_id)


class FakeDb:
    def __init__(self):
        self.store = {}

    def collection(self, name):
        return FakeCollection(self, name)


class InviteCodesTest(unittest.TestCase):
    def setUp(self):
        self.db = FakeDb()

    def seed_invite(self, code="ABC123", **overrides):
        payload = {
            "class_id": "mtc13",
            "label": "MTC13",
            "status": "active",
            "expires_at": None,
            "max_uses": None,
            "used_count": 0,
            "created_by": "admin",
            "created_at": "2026-05-31T00:00:00+07:00",
        }
        payload.update(overrides)
        self.db.store[f"class_invites/{code}"] = payload

    def test_join_code_parsing_normalizes_code(self):
        self.assertEqual("ABC123", normalize_invite_code("  abc123 "))
        self.assertEqual("ABC123", parse_join_code("JOIN abc123"))
        self.assertEqual("ABC123", parse_join_code("เข้าห้อง  abc123  "))
        self.assertTrue(is_join_command("JOIN @@"))
        self.assertIsNone(parse_join_code("JOIN    "))

    def test_rejects_invalid_invite_code_format_before_firestore_path(self):
        result = join_class_with_invite(self.db, "user-a", "JOIN ../../bad")

        self.assertFalse(result.success)
        self.assertEqual({}, self.db.store)

    def test_rejects_disabled_expired_and_full_invites(self):
        self.seed_invite(status="disabled")
        self.assertFalse(join_class_with_invite(self.db, "user-a", "JOIN ABC123").success)

        self.seed_invite(expires_at=datetime.datetime(2026, 1, 1, tzinfo=LOCAL_TZ))
        self.assertFalse(join_class_with_invite(self.db, "user-a", "JOIN ABC123").success)

        self.seed_invite(expires_at=None, max_uses=1, used_count=1)
        self.assertFalse(join_class_with_invite(self.db, "user-a", "JOIN ABC123").success)

    def test_rejects_malformed_invite_usage_limits(self):
        self.seed_invite(used_count="bad")
        self.assertFalse(join_class_with_invite(self.db, "user-a", "JOIN ABC123").success)

        self.seed_invite(used_count=0, max_uses="bad")
        self.assertFalse(join_class_with_invite(self.db, "user-a", "JOIN ABC123").success)

    def test_rejects_invalid_class_id_format(self):
        self.seed_invite(class_id="../mtc13")

        result = join_class_with_invite(self.db, "user-a", "JOIN ABC123")

        self.assertFalse(result.success)
        self.assertNotIn("users/user-a", self.db.store)
        self.assertNotIn("classes/../mtc13/users/user-a", self.db.store)

    def test_successful_join_writes_user_docs_and_increments_once(self):
        self.seed_invite(max_uses=1, used_count=0)

        first = join_class_with_invite(self.db, "user-a", "JOIN abc123", "Mawin")
        second = join_class_with_invite(self.db, "user-a", "เข้าห้อง ABC123", "Mawin")

        self.assertTrue(first.success)
        self.assertTrue(second.success)
        self.assertEqual(1, self.db.store["class_invites/ABC123"]["used_count"])
        self.assertEqual("mtc13", self.db.store["users/user-a"]["active_class_id"])
        self.assertEqual(["mtc13"], self.db.store["users/user-a"]["class_ids"])
        self.assertEqual("unverified", self.db.store["users/user-a"]["identity_status"])
        self.assertEqual("user-a", self.db.store["classes/mtc13/users/user-a"]["user_id"])
        self.assertEqual("unverified", self.db.store["classes/mtc13/users/user-a"]["verification_status"])

    def test_transaction_path_is_used_when_available(self):
        class TransactionalDb(FakeDb):
            def transaction(self):
                return object()

        db = TransactionalDb()
        db.store["class_invites/ABC123"] = {
            "class_id": "mtc13",
            "label": "MTC13",
            "status": "active",
            "expires_at": None,
            "max_uses": None,
            "used_count": 0,
        }

        with patch("mtc_assistant.invite_codes._join_class_with_invite_transaction") as mocked:
            mocked.return_value.success = True
            result = join_class_with_invite(db, "user-a", "JOIN ABC123")

        self.assertTrue(result.success)
        self.assertTrue(mocked.called)

    def test_exception_log_redacts_invite_code(self):
        class BrokenDb:
            def collection(self, _name):
                raise RuntimeError("boom")

        with self.assertLogs("mtc_assistant", level="ERROR") as logs:
            join_class_with_invite(BrokenDb(), "user-a", "JOIN SECRET123")

        joined_logs = "\n".join(logs.output)
        self.assertNotIn("SECRET123", joined_logs)
        self.assertIn("redacted code", joined_logs)


if __name__ == "__main__":
    unittest.main()
