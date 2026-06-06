import io
import json
import unittest

from mtc_assistant.check_term_readiness import check_term_readiness, main


class FakeSnapshot:
    def __init__(self, data=None):
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return dict(self._data or {})


class FakeDocument:
    def __init__(self, db, path):
        self._db = db
        self._path = path

    def collection(self, name):
        return FakeCollection(self._db, f"{self._path}/{name}")

    def get(self):
        self._db.reads.append(self._path)
        return FakeSnapshot(self._db.documents.get(self._path))


class FakeCollection:
    def __init__(self, db, path):
        self._db = db
        self._path = path

    def document(self, document_id):
        return FakeDocument(self._db, f"{self._path}/{document_id}")

    def stream(self):
        self._db.reads.append(self._path)
        return [
            FakeSnapshot(data)
            for data in self._db.collections.get(self._path, [])
        ]


class FakeDb:
    def __init__(self, documents=None, collections=None):
        self.documents = dict(documents or {})
        self.collections = dict(collections or {})
        self.reads = []
        self.writes = []

    def collection(self, name):
        return FakeCollection(self, name)


def ready_db(active_term_id="2569-t1", grade_level="m4", term_id="2569-t1"):
    return FakeDb(
        documents={
            "system/class_registry/mtc13/main": {
                "active_term_id": active_term_id,
                "grade_level": grade_level,
                "status": "active",
            },
            f"classes/mtc13/terms/{term_id}": {"status": "planned"},
            f"classes/mtc13/terms/{term_id}/config/links": {
                "school_url": "https://example.test/school",
                "grade_url": "https://example.test/grade",
                "absence_form_url": "https://example.test/absence",
                "worksheet_url": "https://example.test/worksheets",
            },
            f"classes/mtc13/terms/{term_id}/config/timetable": {
                "image_url": "https://example.test/timetable.png",
                "days": {
                    "0": [
                        {
                            "start": "08:30",
                            "end": "09:20",
                            "subject": "คณิตศาสตร์",
                        }
                    ]
                },
            },
        },
        collections={
            f"classes/mtc13/terms/{term_id}/resources": [
                {
                    "subject_id": "biology",
                    "section": "textbook_solutions",
                    "grade_level": grade_level,
                    "status": "active",
                    "url": "https://example.test/biology",
                },
                {
                    "subject_id": "physics",
                    "section": "textbook_solutions",
                    "grade_level": grade_level,
                    "status": "active",
                    "url": "https://example.test/physics",
                },
                {
                    "subject_id": "chemistry",
                    "section": "reference",
                    "grade_level": grade_level,
                    "status": "inactive",
                    "url": "https://example.test/chemistry",
                },
            ]
        },
    )


class TermReadinessCheckTests(unittest.TestCase):
    def test_ready_term_reports_all_required_checks(self):
        db = ready_db()

        result = check_term_readiness(db, "mtc13", "2569-t1")

        self.assertTrue(result["ready_to_switch"])
        self.assertTrue(result["is_active_term"])
        self.assertEqual([], result["errors"])
        self.assertEqual("pass", result["checks"]["registry"]["status"])
        self.assertEqual("pass", result["checks"]["term_doc"]["status"])
        self.assertEqual("pass", result["checks"]["links_config"]["status"])
        self.assertEqual("pass", result["checks"]["timetable_config"]["status"])
        self.assertEqual("pass", result["checks"]["resources"]["status"])

    def test_missing_registry_is_a_readiness_error(self):
        db = ready_db()
        del db.documents["system/class_registry/mtc13/main"]

        result = check_term_readiness(db, "mtc13", "2569-t1")

        self.assertFalse(result["ready_to_switch"])
        self.assertEqual("missing", result["checks"]["registry"]["status"])
        self.assertIn("Class registry document is missing.", result["errors"])

    def test_invalid_registry_grade_is_a_readiness_error(self):
        db = ready_db(grade_level="m7")

        result = check_term_readiness(db, "mtc13", "2569-t1")

        self.assertFalse(result["ready_to_switch"])
        self.assertEqual("error", result["checks"]["registry"]["status"])
        self.assertIn("Registry grade_level must be one of: m4, m5, m6.", result["errors"])

    def test_missing_term_document_is_a_readiness_error(self):
        db = ready_db()
        del db.documents["classes/mtc13/terms/2569-t1"]

        result = check_term_readiness(db, "mtc13", "2569-t1")

        self.assertFalse(result["ready_to_switch"])
        self.assertEqual("missing", result["checks"]["term_doc"]["status"])

    def test_missing_links_document_is_a_readiness_error(self):
        db = ready_db()
        del db.documents["classes/mtc13/terms/2569-t1/config/links"]

        result = check_term_readiness(db, "mtc13", "2569-t1")

        self.assertFalse(result["ready_to_switch"])
        self.assertEqual("missing", result["checks"]["links_config"]["status"])

    def test_missing_required_link_is_a_readiness_error(self):
        db = ready_db()
        db.documents["classes/mtc13/terms/2569-t1/config/links"]["grade_url"] = ""

        result = check_term_readiness(db, "mtc13", "2569-t1")

        self.assertFalse(result["ready_to_switch"])
        self.assertEqual("error", result["checks"]["links_config"]["status"])
        self.assertEqual(
            "missing",
            result["checks"]["links_config"]["required_fields"]["grade_url"],
        )

    def test_missing_timetable_document_is_a_readiness_error(self):
        db = ready_db()
        del db.documents["classes/mtc13/terms/2569-t1/config/timetable"]

        result = check_term_readiness(db, "mtc13", "2569-t1")

        self.assertFalse(result["ready_to_switch"])
        self.assertEqual("missing", result["checks"]["timetable_config"]["status"])

    def test_missing_worksheet_url_does_not_block_readiness(self):
        db = ready_db()
        del db.documents["classes/mtc13/terms/2569-t1/config/links"]["worksheet_url"]

        result = check_term_readiness(db, "mtc13", "2569-t1")

        self.assertTrue(result["ready_to_switch"])
        self.assertEqual(
            "optional_missing",
            result["checks"]["links_config"]["worksheet_url"],
        )

    def test_active_resources_are_counted(self):
        db = ready_db()

        result = check_term_readiness(db, "mtc13", "2569-t1")

        self.assertEqual(2, result["checks"]["resources"]["active_count"])

    def test_missing_active_resources_blocks_readiness(self):
        db = ready_db()
        db.collections["classes/mtc13/terms/2569-t1/resources"] = []

        result = check_term_readiness(db, "mtc13", "2569-t1")

        self.assertFalse(result["ready_to_switch"])
        self.assertEqual("missing", result["checks"]["resources"]["status"])

    def test_matching_textbook_solution_grades_pass(self):
        db = ready_db()

        result = check_term_readiness(db, "mtc13", "2569-t1")

        subjects = result["checks"]["resources"]["textbook_solutions"]
        self.assertEqual("pass", subjects["biology"])
        self.assertEqual("pass", subjects["physics"])

    def test_missing_textbook_solution_is_a_warning_only(self):
        db = ready_db()
        db.collections["classes/mtc13/terms/2569-t1/resources"] = [
            db.collections["classes/mtc13/terms/2569-t1/resources"][0]
        ]

        result = check_term_readiness(db, "mtc13", "2569-t1")

        self.assertTrue(result["ready_to_switch"])
        self.assertEqual(
            "missing",
            result["checks"]["resources"]["textbook_solutions"]["physics"],
        )
        self.assertIn(
            "Active physics textbook_solutions resource is missing.",
            result["warnings"],
        )

    def test_textbook_solution_grade_mismatch_blocks_readiness(self):
        db = ready_db()
        db.collections["classes/mtc13/terms/2569-t1/resources"][0][
            "grade_level"
        ] = "m5"

        result = check_term_readiness(db, "mtc13", "2569-t1")

        self.assertFalse(result["ready_to_switch"])
        self.assertEqual(
            "grade_mismatch",
            result["checks"]["resources"]["textbook_solutions"]["biology"],
        )
        self.assertIn(
            "Active biology textbook_solutions resource does not match registry grade_level m4.",
            result["errors"],
        )

    def test_future_term_can_be_ready_without_being_active(self):
        db = ready_db(active_term_id="2569-t1", term_id="2569-t2")

        result = check_term_readiness(db, "mtc13", "2569-t2")

        self.assertTrue(result["ready_to_switch"])
        self.assertFalse(result["is_active_term"])

    def test_check_never_calls_a_write_api(self):
        db = ready_db()

        check_term_readiness(db, "mtc13", "2569-t1")

        self.assertEqual([], db.writes)

    def test_cli_emits_stable_json_and_returns_zero_when_not_ready(self):
        db = ready_db()
        del db.documents["classes/mtc13/terms/2569-t1/config/links"]
        stdout = io.StringIO()
        stderr = io.StringIO()

        exit_code = main(
            ["--class-id", "mtc13", "--term-id", "2569-t1"],
            db_factory=lambda: db,
            stdout=stdout,
            stderr=stderr,
        )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(0, exit_code)
        self.assertFalse(payload["ready_to_switch"])
        self.assertEqual("mtc13", payload["class_id"])
        self.assertEqual("2569-t1", payload["term_id"])
        self.assertEqual("", stderr.getvalue())
        self.assertEqual(
            [
                "checks",
                "class_id",
                "errors",
                "is_active_term",
                "ready_to_switch",
                "registry_active_term_id",
                "registry_grade_level",
                "registry_status",
                "term_id",
                "warnings",
            ],
            sorted(payload),
        )


if __name__ == "__main__":
    unittest.main()
