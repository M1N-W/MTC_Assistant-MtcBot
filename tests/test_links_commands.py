import unittest

from mtc_assistant import features
from mtc_assistant.class_context import ClassContext
from mtc_assistant.command_router import handle_standard_command
from mtc_assistant.config import Bio_LINK, LINE_SAFE_TRUNCATE, Physic_LINK, SCHOOL_LINK, WORKSHEET_LINK
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

    def stream(self):
        prefix = f"{self.path}/"
        docs = []
        for path, data in self.db.store.items():
            if path.startswith(prefix) and "/" not in path[len(prefix) :]:
                docs.append(FakeDocSnapshot(True, data))
        return docs


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


def add_resource(db, resource_id, data, class_id="mtc13", term_id="2569-t1"):
    db.store[f"classes/{class_id}/terms/{term_id}/resources/{resource_id}"] = data


def valid_resource(title, url, **overrides):
    data = {
        "section": "textbook_solutions",
        "type": "solution_manual",
        "subject_id": "biology",
        "subject_label": "Biology",
        "title": title,
        "url": url,
        "status": "active",
        "sort_order": 10,
    }
    data.update(overrides)
    return data


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

    def test_legacy_fallback_context_keeps_legacy_solution_links(self):
        context = ClassContext("mtc12", "user-a", is_legacy_fallback=True)

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

    def test_mtc13_biology_command_uses_learning_resource(self):
        add_resource(
            self.db,
            "bio-main",
            valid_resource("Biology MTC13 Book", "https://example.com/mtc13-bio"),
        )

        message = handle_standard_command("ชีวะ", "ชีวะ", self.context)

        self.assertIn("Biology MTC13 Book", message.text)
        self.assertIn("https://example.com/mtc13-bio", message.text)
        self.assertNotIn(Bio_LINK, message.text)

    def test_mtc13_physics_command_uses_learning_resource(self):
        add_resource(
            self.db,
            "physics-main",
            valid_resource(
                "Physics MTC13 Book",
                "https://example.com/mtc13-physics",
                subject_id="physics",
                subject_label="Physics",
            ),
        )

        message = handle_standard_command("ฟิสิกส์", "ฟิสิกส์", self.context)

        self.assertIn("Physics MTC13 Book", message.text)
        self.assertIn("https://example.com/mtc13-physics", message.text)
        self.assertNotIn(Physic_LINK, message.text)

    def test_mtc13_multiple_biology_resources_return_sorted_text_list(self):
        add_resource(
            self.db,
            "z-bio",
            valid_resource("Z Biology", "https://example.com/z-bio", sort_order=2),
        )
        add_resource(
            self.db,
            "b-bio",
            valid_resource("B Biology", "https://example.com/b-bio", sort_order=1),
        )
        add_resource(
            self.db,
            "a-bio",
            valid_resource("A Biology", "https://example.com/a-bio", sort_order=1),
        )

        message = handle_standard_command("ชีวะ", "ชีวะ", self.context)

        self.assertLess(message.text.index("A Biology"), message.text.index("B Biology"))
        self.assertLess(message.text.index("B Biology"), message.text.index("Z Biology"))
        self.assertIn("https://example.com/a-bio", message.text)
        self.assertIn("https://example.com/b-bio", message.text)
        self.assertIn("https://example.com/z-bio", message.text)

    def test_mtc13_solution_commands_ignore_wrong_section_and_invalid_resources(self):
        add_resource(
            self.db,
            "assignment",
            valid_resource("Assignment Bio", "https://example.com/assignment", section="assignment_resources"),
        )
        add_resource(
            self.db,
            "hidden",
            valid_resource("Hidden Bio", "https://example.com/hidden", status="hidden"),
        )
        add_resource(
            self.db,
            "archived",
            valid_resource("Archived Bio", "https://example.com/archived", status="archived"),
        )
        add_resource(
            self.db,
            "blank-url",
            valid_resource("Blank Bio", "   "),
        )
        add_resource(
            self.db,
            "non-http",
            valid_resource("Non Http Bio", "ftp://example.com/non-http"),
        )
        add_resource(
            self.db,
            "missing-title",
            valid_resource("", "https://example.com/missing-title"),
        )

        message = handle_standard_command("ชีวะ", "ชีวะ", self.context)

        self.assertIn("ยังไม่ได้ตั้งค่า", message.text)
        self.assertNotIn("Assignment Bio", message.text)
        self.assertNotIn("Hidden Bio", message.text)
        self.assertNotIn("Archived Bio", message.text)
        self.assertNotIn("Blank Bio", message.text)
        self.assertNotIn("Non Http Bio", message.text)
        self.assertNotIn("https://example.com/missing-title", message.text)

    def test_mtc13_solution_commands_do_not_cross_subjects(self):
        add_resource(
            self.db,
            "bio-main",
            valid_resource("Biology Only", "https://example.com/bio-only", subject_id="biology"),
        )
        add_resource(
            self.db,
            "physics-main",
            valid_resource(
                "Physics Only",
                "https://example.com/physics-only",
                subject_id="physics",
                subject_label="Physics",
            ),
        )

        bio_message = handle_standard_command("ชีวะ", "ชีวะ", self.context)
        physic_message = handle_standard_command("ฟิสิกส์", "ฟิสิกส์", self.context)

        self.assertIn("Biology Only", bio_message.text)
        self.assertNotIn("Physics Only", bio_message.text)
        self.assertIn("Physics Only", physic_message.text)
        self.assertNotIn("Biology Only", physic_message.text)

    def test_mtc13_solution_command_caps_output_for_line_text_safety(self):
        for index in range(12):
            add_resource(
                self.db,
                f"bio-{index:02}",
                valid_resource(f"Biology {index:02}", f"https://example.com/bio-{index:02}", sort_order=index),
            )

        message = handle_standard_command("ชีวะ", "ชีวะ", self.context)

        self.assertIn("Biology 00", message.text)
        self.assertIn("Biology 09", message.text)
        self.assertNotIn("Biology 10", message.text)
        self.assertNotIn("Biology 11", message.text)

    def test_mtc13_solution_command_truncates_overlong_text(self):
        long_title = "Biology " + ("A" * LINE_SAFE_TRUNCATE)
        add_resource(
            self.db,
            "long-bio",
            valid_resource(long_title, "https://example.com/long-bio"),
        )

        message = handle_standard_command("ชีวะ", "ชีวะ", self.context)

        self.assertLessEqual(len(message.text), LINE_SAFE_TRUNCATE + len("...\n\n(ข้อความยาวเกินไป ตัดบางส่วน)"))
        self.assertIn("ข้อความยาวเกินไป", message.text)


if __name__ == "__main__":
    unittest.main()
