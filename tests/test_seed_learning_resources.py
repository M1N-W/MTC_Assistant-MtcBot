import io
import json
import tempfile
import unittest
from pathlib import Path

from mtc_assistant.seed_learning_resources import execute_seed, main


class FakeSnapshot:
    def __init__(self, exists, data=None):
        self.exists = exists
        self._data = data or {}

    def to_dict(self):
        return dict(self._data)


class FakeDocument:
    def __init__(self, db, path):
        self.db = db
        self.path = path

    def get(self):
        return FakeSnapshot(self.path in self.db.store, self.db.store.get(self.path))

    def set(self, data, merge=False):
        current = self.db.store.get(self.path, {}) if merge else {}
        self.db.store[self.path] = {**current, **data}
        self.db.writes.append((self.path, dict(data), merge))

    def collection(self, name):
        return FakeCollection(self.db, f"{self.path}/{name}")


class FakeCollection:
    def __init__(self, db, path):
        self.db = db
        self.path = path

    def document(self, document_id):
        return FakeDocument(self.db, f"{self.path}/{document_id}")


class FakeDb:
    def __init__(self):
        self.store = {}
        self.writes = []

    def collection(self, name):
        return FakeCollection(self, name)


def valid_resource(resource_id="biology-m4-t1-solutions", **overrides):
    resource = {
        "id": resource_id,
        "status": "active",
        "section": "textbook_solutions",
        "type": "solution_manual",
        "subject_id": "biology",
        "subject_label": "ชีววิทยา",
        "grade_level": "m4",
        "term_label": "เทอม 1",
        "book_label": "ชีววิทยา ม.4",
        "title": "เฉลยชีววิทยา ม.4 เทอม 1",
        "url": "https://school.example.edu/biology",
        "sort_order": 10,
        "notes": "verified by Mawin",
    }
    resource.update(overrides)
    return resource


def valid_seed(resources=None, **overrides):
    seed = {
        "class_id": "mtc13",
        "term_id": "2569-t1",
        "updated_by": "mawin",
        "resources": resources if resources is not None else [valid_resource()],
    }
    seed.update(overrides)
    return seed


def add_registry(db, active_term_id="2569-t1", grade_level="m4"):
    db.store["system/class_registry/mtc13/main"] = {
        "display_name": "MTC13",
        "status": "active",
        "active_term_id": active_term_id,
        "grade_level": grade_level,
    }


class SeedLearningResourcesTest(unittest.TestCase):
    timestamp = "SERVER_TIMESTAMP"

    def setUp(self):
        self.db = FakeDb()
        add_registry(self.db)

    def execute(self, payload=None, *, apply=False):
        return execute_seed(
            self.db,
            payload or valid_seed(),
            apply=apply,
            timestamp=self.timestamp,
        )

    def test_dry_run_valid_seed_performs_no_writes_and_reports_create(self):
        result = self.execute()

        self.assertEqual("dry-run", result["mode"])
        self.assertEqual(["biology-m4-t1-solutions"], result["would_create"])
        self.assertTrue(result["would_create_term_doc"])
        self.assertEqual([], self.db.writes)
        self.assertTrue(result["no_writes_performed"])

    def test_apply_valid_seed_writes_term_and_resource_documents(self):
        result = self.execute(apply=True)

        self.assertEqual("apply", result["mode"])
        self.assertTrue(result["created_term_doc"])
        self.assertEqual(["biology-m4-t1-solutions"], result["created"])
        self.assertIn("classes/mtc13/terms/2569-t1", self.db.store)
        resource_path = "classes/mtc13/terms/2569-t1/resources/biology-m4-t1-solutions"
        self.assertIn(resource_path, self.db.store)
        self.assertEqual("mtc13", self.db.store[resource_path]["class_id"])
        self.assertEqual(self.timestamp, self.db.store[resource_path]["created_at"])
        self.assertEqual(self.timestamp, self.db.store[resource_path]["updated_at"])

    def test_apply_validates_all_records_before_writing(self):
        payload = valid_seed([
            valid_resource("valid"),
            valid_resource("invalid", url="http://example.com/invalid"),
        ])

        result = self.execute(payload, apply=True)

        self.assertTrue(result["errors"])
        self.assertEqual([], self.db.writes)

    def test_rejects_enabled(self):
        result = self.execute(valid_seed([valid_resource(enabled=True)]))

        self.assertTrue(any("enabled is obsolete" in error["message"] for error in result["errors"]))

    def test_rejects_invalid_status(self):
        result = self.execute(valid_seed([valid_resource(status="enabled")]))

        self.assertTrue(any("status" in error["message"] for error in result["errors"]))

    def test_rejects_missing_url(self):
        result = self.execute(valid_seed([valid_resource(url="")]))

        self.assertTrue(any("url" in error["message"] for error in result["errors"]))

    def test_rejects_non_https_url(self):
        result = self.execute(valid_seed([valid_resource(url="http://school.example.edu/bio")]))

        self.assertTrue(any("https" in error["message"] for error in result["errors"]))

    def test_rejects_local_file_path(self):
        result = self.execute(valid_seed([valid_resource(url="C:\\Users\\User\\bio.pdf")]))

        self.assertTrue(any("local file path" in error["message"] for error in result["errors"]))

    def test_rejects_textbook_solution_without_grade(self):
        result = self.execute(valid_seed([valid_resource(grade_level="")]))

        self.assertTrue(any("grade_level" in error["message"] for error in result["errors"]))

    def test_rejects_invalid_grade(self):
        result = self.execute(valid_seed([valid_resource(grade_level="M4")]))

        self.assertTrue(any("grade_level" in error["message"] for error in result["errors"]))

    def test_rejects_active_solution_grade_mismatch(self):
        result = self.execute(valid_seed([valid_resource(grade_level="m5")]))

        self.assertTrue(any("registry grade_level" in error["message"] for error in result["errors"]))

    def test_accepts_active_solution_grade_match(self):
        result = self.execute()

        self.assertEqual([], result["errors"])

    def test_accepts_assignment_without_grade(self):
        assignment = valid_resource(
            "assignment",
            section="assignment_resources",
            type="worksheet_pack",
            subject_id=None,
            subject_label=None,
            grade_level=None,
        )

        result = self.execute(valid_seed([assignment]))

        self.assertEqual([], result["errors"])

    def test_rejects_seed_term_mismatch_with_registry(self):
        result = self.execute(valid_seed(term_id="2569-t2"))

        self.assertTrue(any("active_term_id" in error["message"] for error in result["errors"]))

    def test_rejects_embedded_resource_term_conflict(self):
        result = self.execute(valid_seed([valid_resource(term_id="2569-t2")]))

        self.assertTrue(any("resource term_id" in error["message"] for error in result["errors"]))

    def test_rejects_embedded_resource_class_conflict(self):
        result = self.execute(valid_seed([valid_resource(class_id="mtc14")]))

        self.assertTrue(any("resource class_id" in error["message"] for error in result["errors"]))

    def test_apply_rejects_placeholder_url(self):
        result = self.execute(
            valid_seed([valid_resource(url="https://example.com/fake-resource")]),
            apply=True,
        )

        self.assertTrue(any("placeholder" in error["message"] for error in result["errors"]))
        self.assertEqual([], self.db.writes)

    def test_apply_rejects_reserved_example_tld(self):
        result = self.execute(
            valid_seed([valid_resource(url="https://verified.example/resource")]),
            apply=True,
        )

        self.assertTrue(any("placeholder" in error["message"] for error in result["errors"]))
        self.assertEqual([], self.db.writes)

    def test_rejects_empty_resources(self):
        result = self.execute(valid_seed([]), apply=True)

        self.assertTrue(any("resources" in error["message"] for error in result["errors"]))
        self.assertEqual([], self.db.writes)

    def test_rejects_unsafe_class_id_before_firestore_access(self):
        result = self.execute(valid_seed(class_id="mtc13/other"), apply=True)

        self.assertTrue(any("class_id" in error["message"] for error in result["errors"]))
        self.assertEqual([], self.db.writes)

    def test_existing_resources_are_not_deleted_or_disabled(self):
        existing_path = "classes/mtc13/terms/2569-t1/resources/existing"
        self.db.store["classes/mtc13/terms/2569-t1"] = {"term_id": "2569-t1"}
        self.db.store[existing_path] = {
            "id": "existing",
            "status": "active",
            "title": "Existing",
        }

        self.execute(apply=True)

        self.assertEqual("active", self.db.store[existing_path]["status"])
        self.assertNotIn(existing_path, [path for path, _, _ in self.db.writes])

    def test_unchanged_resource_is_skipped(self):
        resource = valid_resource()
        existing = {
            **resource,
            "class_id": "mtc13",
            "term_id": "2569-t1",
            "updated_by": "mawin",
            "created_at": "OLD",
            "updated_at": "OLD",
        }
        self.db.store["classes/mtc13/terms/2569-t1"] = {"term_id": "2569-t1"}
        self.db.store[
            "classes/mtc13/terms/2569-t1/resources/biology-m4-t1-solutions"
        ] = existing

        result = self.execute(apply=True)

        self.assertEqual(["biology-m4-t1-solutions"], result["skipped"])
        self.assertEqual([], self.db.writes)


class SeedLearningResourcesCliTest(unittest.TestCase):
    def setUp(self):
        self.db = FakeDb()
        add_registry(self.db)

    def run_cli(self, extra_args=None):
        with tempfile.TemporaryDirectory() as temp_dir:
            seed_path = Path(temp_dir) / "seed.json"
            seed_path.write_text(json.dumps(valid_seed(), ensure_ascii=False), encoding="utf-8")
            stdout = io.StringIO()
            exit_code = main(
                ["--seed", str(seed_path), *(extra_args or [])],
                db_factory=lambda: self.db,
                stdout=stdout,
                timestamp="SERVER_TIMESTAMP",
            )
            return exit_code, json.loads(stdout.getvalue())

    def test_default_mode_is_dry_run_and_performs_no_writes(self):
        exit_code, result = self.run_cli()

        self.assertEqual(0, exit_code)
        self.assertEqual("dry-run", result["mode"])
        self.assertEqual([], self.db.writes)

    def test_explicit_dry_run_performs_no_writes(self):
        exit_code, result = self.run_cli(["--dry-run"])

        self.assertEqual(0, exit_code)
        self.assertEqual("dry-run", result["mode"])
        self.assertEqual([], self.db.writes)

    def test_passing_dry_run_and_apply_fails(self):
        exit_code, result = self.run_cli(["--dry-run", "--apply"])

        self.assertNotEqual(0, exit_code)
        self.assertTrue(result["errors"])
        self.assertEqual([], self.db.writes)


if __name__ == "__main__":
    unittest.main()
