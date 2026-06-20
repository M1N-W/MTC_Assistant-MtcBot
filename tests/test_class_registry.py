import unittest

from mtc_assistant.class_context import (
    get_active_term_metadata,
    get_class_registry_entry,
    parse_class_registry_entry,
)


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

    def collection(self, name):
        return FakeCollection(self.db, f"{self.path}/{name}")


class FakeCollection:
    def __init__(self, db, path):
        self.db = db
        self.path = path

    def document(self, doc_id):
        return FakeDocRef(self.db, f"{self.path}/{doc_id}")


class FakeDb:
    def __init__(self):
        self.store = {}

    def collection(self, name):
        return FakeCollection(self, name)


class ClassRegistryTest(unittest.TestCase):
    def test_academic_year_2569_three_class_grade_matrix(self):
        cases = {
            "mtc11": ("MTC11", "m6"),
            "mtc12": ("MTC12", "m5"),
            "mtc13": ("MTC13", "m4"),
        }

        for class_id, (display_name, grade_level) in cases.items():
            with self.subTest(class_id=class_id):
                entry = parse_class_registry_entry(class_id, {
                    "display_name": display_name,
                    "status": "active",
                    "grade_level": grade_level,
                })
                self.assertEqual(display_name, entry.display_name)
                self.assertEqual(grade_level, entry.grade_level)

    def test_parse_class_registry_entry(self):
        entry = parse_class_registry_entry("mtc13", {
            "display_name": "MTC13",
            "status": "active",
            "active_term_id": "2569-t1",
            "grade_level": "m4",
            "room_label": "ม.4/2",
        })

        self.assertEqual("mtc13", entry.class_id)
        self.assertEqual("2569-t1", entry.active_term_id)
        self.assertEqual("ม.4/2", entry.room_label)

    def test_invalid_registry_entry_returns_none(self):
        self.assertIsNone(parse_class_registry_entry("../mtc13", {"display_name": "MTC13", "status": "active"}))
        self.assertIsNone(parse_class_registry_entry("mtc13", {"display_name": "MTC13"}))
        self.assertIsNone(parse_class_registry_entry("mtc13", {
            "display_name": "MTC13",
            "status": "active",
            "active_term_id": "../bad",
        }))

    def test_reads_registry_and_active_term_metadata(self):
        db = FakeDb()
        db.store["system/class_registry/mtc13/main"] = {
            "display_name": "MTC13",
            "status": "active",
            "active_term_id": "2569-t1",
            "grade_level": "m4",
            "room_label": "ม.4/2",
        }
        db.store["classes/mtc13/terms/2569-t1/metadata/main"] = {
            "display_name": "Term 1",
            "status": "active",
        }

        registry = get_class_registry_entry(db, "mtc13")
        term = get_active_term_metadata(db, "mtc13")

        self.assertEqual("MTC13", registry.display_name)
        self.assertEqual("2569-t1", term.term_id)
        self.assertEqual("Term 1", term.display_name)


if __name__ == "__main__":
    unittest.main()

