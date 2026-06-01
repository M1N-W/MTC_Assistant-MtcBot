import unittest

from mtc_assistant import features
from mtc_assistant.class_context import ClassContext
from mtc_assistant.command_router import handle_standard_command
from mtc_assistant.config import Bio_LINK, Physic_LINK, SCHOOL_LINK, WORKSHEET_LINK
from mtc_assistant.links_service import (
    ABSENCE_FORM_URL,
    GRADE_URL,
    SCHOOL_URL,
    WORKSHEET_URL,
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


def collect_uris(value):
    uris = []
    if isinstance(value, dict):
        action = value.get("action")
        if isinstance(action, dict) and action.get("type") == "uri":
            uris.append(action.get("uri"))
        for child in value.values():
            uris.extend(collect_uris(child))
    elif isinstance(value, list):
        for child in value:
            uris.extend(collect_uris(child))
    return uris


class LinksCommandTest(unittest.TestCase):
    def setUp(self):
        self.original_db = features.db
        self.db = FakeDb()
        self.db.store["system/class_registry/mtc13/main"] = {
            "display_name": "MTC13",
            "status": "active",
            "active_term_id": "2569-t1",
        }
        self.db.store["classes/mtc13/terms/2569-t1/config/links"] = {
            WORKSHEET_URL: "https://example.com/worksheet",
            SCHOOL_URL: "https://example.com/school",
            GRADE_URL: "https://example.com/grade",
            ABSENCE_FORM_URL: "https://example.com/absence",
        }
        features.db = self.db
        self.context = ClassContext("mtc13", "user-a")

    def tearDown(self):
        features.db = self.original_db

    def test_link_text_commands_use_class_aware_values(self):
        cases = {
            "งาน": "https://example.com/worksheet",
            "การบ้าน": "https://example.com/worksheet",
            "ใบงาน": "https://example.com/worksheet",
            "เว็บโรงเรียน": "https://example.com/school",
            "เกรด": "https://example.com/grade",
            "ลา": "https://example.com/absence",
        }

        for command, expected_url in cases.items():
            with self.subTest(command=command):
                message = handle_standard_command(command, command, self.context)

                self.assertIn(expected_url, message.text)

    def test_links_menu_uses_class_aware_values(self):
        message = handle_standard_command("ลิงก์", "ลิงก์", self.context)

        uris = collect_uris(message.contents.to_dict())

        self.assertIn("https://example.com/school", uris)
        self.assertIn("https://example.com/grade", uris)
        self.assertIn("https://example.com/absence", uris)
        self.assertNotIn(Bio_LINK, uris)
        self.assertNotIn(Physic_LINK, uris)

    def test_no_context_commands_keep_mtc12_fallback(self):
        worksheet_message = handle_standard_command("งาน", "งาน")
        school_message = handle_standard_command("เว็บโรงเรียน", "เว็บโรงเรียน")
        bio_message = handle_standard_command("ชีวะ", "ชีวะ")
        physic_message = handle_standard_command("ฟิสิกส์", "ฟิสิกส์")

        self.assertIn(WORKSHEET_LINK, worksheet_message.text)
        self.assertIn(SCHOOL_LINK, school_message.text)
        self.assertIn(Bio_LINK, bio_message.text)
        self.assertIn(Physic_LINK, physic_message.text)

    def test_explicit_mtc12_context_keeps_legacy_solution_links(self):
        context = ClassContext("mtc12", "user-a")

        bio_message = handle_standard_command("ชีวะ", "ชีวะ", context)
        physic_message = handle_standard_command("ฟิสิกส์", "ฟิสิกส์", context)

        self.assertIn(Bio_LINK, bio_message.text)
        self.assertIn(Physic_LINK, physic_message.text)

    def test_explicit_mtc12_links_menu_keeps_solution_uri_buttons(self):
        context = ClassContext("mtc12", "user-a")

        message = handle_standard_command("ลิงก์", "ลิงก์", context)
        uris = collect_uris(message.contents.to_dict())

        self.assertIn(Bio_LINK, uris)
        self.assertIn(Physic_LINK, uris)

    def test_non_legacy_solution_commands_do_not_return_mtc12_links(self):
        bio_message = handle_standard_command("ชีวะ", "ชีวะ", self.context)
        physic_message = handle_standard_command("ฟิสิกส์", "ฟิสิกส์", self.context)

        self.assertIn("ยังไม่ได้ตั้งค่า", bio_message.text)
        self.assertIn("ยังไม่ได้ตั้งค่า", physic_message.text)
        self.assertNotIn(Bio_LINK, bio_message.text)
        self.assertNotIn(Physic_LINK, physic_message.text)


if __name__ == "__main__":
    unittest.main()
