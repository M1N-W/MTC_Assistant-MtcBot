import unittest

from mtc_assistant.class_context import ClassContext
from mtc_assistant.config import ABSENCE_LINK, GRADE_LINK, SCHOOL_LINK, WORKSHEET_LINK
from mtc_assistant.links_service import (
    ABSENCE_FORM_URL,
    GRADE_URL,
    SCHOOL_URL,
    WORKSHEET_URL,
    get_links_config,
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
        if self.db.raise_on_get:
            raise RuntimeError("boom")
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
        self.raise_on_get = False

    def collection(self, name):
        return FakeCollection(self, name)


class LinksServiceTest(unittest.TestCase):
    def test_no_db_or_context_returns_fallback(self):
        self.assertEqual(WORKSHEET_LINK, get_links_config()[WORKSHEET_URL])
        self.assertEqual(SCHOOL_LINK, get_links_config(FakeDb())[SCHOOL_URL])

    def test_non_legacy_context_without_db_does_not_return_worksheet_fallback(self):
        links = get_links_config(None, ClassContext("mtc13", "user-a"))

        self.assertEqual(SCHOOL_LINK, links[SCHOOL_URL])
        self.assertEqual(GRADE_LINK, links[GRADE_URL])
        self.assertEqual(ABSENCE_LINK, links[ABSENCE_FORM_URL])
        self.assertNotIn(WORKSHEET_URL, links)

    def test_missing_registry_or_links_doc_returns_fallback(self):
        db = FakeDb()
        context = ClassContext("mtc13", "user-a")

        links = get_links_config(db, context)
        self.assertEqual(SCHOOL_LINK, links[SCHOOL_URL])
        self.assertNotIn(WORKSHEET_URL, links)

        db.store["system/class_registry/mtc13/main"] = {
            "display_name": "MTC13",
            "status": "active",
            "active_term_id": "2569-t1",
        }

        links = get_links_config(db, context)
        self.assertEqual(SCHOOL_LINK, links[SCHOOL_URL])
        self.assertNotIn(WORKSHEET_URL, links)

    def test_firestore_values_override_fallback(self):
        db = FakeDb()
        db.store["system/class_registry/mtc13/main"] = {
            "display_name": "MTC13",
            "status": "active",
            "active_term_id": "2569-t1",
        }
        db.store["classes/mtc13/terms/2569-t1/config/links"] = {
            WORKSHEET_URL: "https://example.com/worksheets",
            SCHOOL_URL: "https://example.com/school",
        }

        links = get_links_config(db, ClassContext("mtc13", "user-a"))

        self.assertEqual("https://example.com/worksheets", links[WORKSHEET_URL])
        self.assertEqual("https://example.com/school", links[SCHOOL_URL])
        self.assertEqual(GRADE_LINK, links[GRADE_URL])

    def test_invalid_firestore_values_do_not_erase_fallback(self):
        db = FakeDb()
        db.store["system/class_registry/mtc13/main"] = {
            "display_name": "MTC13",
            "status": "active",
            "active_term_id": "2569-t1",
        }
        db.store["classes/mtc13/terms/2569-t1/config/links"] = {
            WORKSHEET_URL: "   ",
            SCHOOL_URL: None,
            GRADE_URL: "https://example.com/grades",
        }

        links = get_links_config(db, ClassContext("mtc13", "user-a"))

        self.assertNotIn(WORKSHEET_URL, links)
        self.assertEqual(SCHOOL_LINK, links[SCHOOL_URL])
        self.assertEqual("https://example.com/grades", links[GRADE_URL])

    def test_firestore_errors_return_fallback(self):
        db = FakeDb()
        db.raise_on_get = True

        links = get_links_config(db, ClassContext("mtc13", "user-a"))

        self.assertEqual(SCHOOL_LINK, links[SCHOOL_URL])
        self.assertNotIn(WORKSHEET_URL, links)


if __name__ == "__main__":
    unittest.main()
