import unittest

from mtc_assistant.class_context import resolve_line_class_context


class FakeDocSnapshot:
    def __init__(self, exists, data=None):
        self.exists = exists
        self._data = data or {}

    def to_dict(self):
        return dict(self._data)


class FakeDocRef:
    def __init__(self, db, path):
        self.db = db
        self.path = path

    def get(self):
        if self.path in self.db.store:
            return FakeDocSnapshot(True, self.db.store[self.path])
        return FakeDocSnapshot(False)


class FakeCollection:
    def __init__(self, db, name):
        self.db = db
        self.name = name

    def document(self, doc_id):
        return FakeDocRef(self.db, f"{self.name}/{doc_id}")


class FakeDb:
    def __init__(self):
        self.store = {}

    def collection(self, name):
        return FakeCollection(self, name)


class ClassContextTest(unittest.TestCase):
    def test_unknown_user_requires_joining(self):
        self.assertIsNone(resolve_line_class_context(FakeDb(), "user-a"))

    def test_existing_root_user_falls_back_to_mtc12(self):
        db = FakeDb()
        db.store["users/user-a"] = {"user_id": "user-a", "is_active": True}

        context = resolve_line_class_context(db, "user-a")

        self.assertEqual("mtc12", context.class_id)
        self.assertTrue(context.is_legacy_fallback)

    def test_active_class_id_is_used(self):
        db = FakeDb()
        db.store["users/user-a"] = {"user_id": "user-a", "active_class_id": "mtc13"}

        context = resolve_line_class_context(db, "user-a")

        self.assertEqual("mtc13", context.class_id)
        self.assertFalse(context.is_legacy_fallback)

    def test_invalid_active_class_id_is_rejected(self):
        db = FakeDb()
        db.store["users/user-a"] = {"user_id": "user-a", "active_class_id": "../mtc13"}

        self.assertIsNone(resolve_line_class_context(db, "user-a"))


if __name__ == "__main__":
    unittest.main()
