import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from tests.fake_firestore import FakeDb, seed_registry


PEPPER = "test-pepper-with-enough-length"


class SeedClassRosterTest(unittest.TestCase):
    def setUp(self):
        self.db = FakeDb()
        seed_registry(self.db, "mtc11", "m6")
        seed_registry(self.db, "mtc12", "m5")
        seed_registry(self.db, "mtc13", "m4")

    def fake_seed(self, **overrides):
        seed = {
            "class_id": "mtc-example",
            "students": [
                {
                    "student_id": "EXAMPLE-001",
                    "first_name": "ตัวอย่าง",
                    "last_name": "นักเรียน",
                    "class_number": 1,
                    "status": "active",
                }
            ],
        }
        seed.update(overrides)
        return seed

    def test_dry_run_accepts_committed_example_without_writes(self):
        from mtc_assistant.seed_class_roster import execute_seed

        before = dict(self.db.store)
        result = execute_seed(self.fake_seed(), db=self.db, apply=False, pepper=PEPPER)

        self.assertEqual("dry-run", result["mode"])
        self.assertEqual(1, result["counts"]["would_upsert"])
        self.assertEqual(before, self.db.store)

    def test_apply_rejects_example_class_and_example_student_id(self):
        from mtc_assistant.seed_class_roster import execute_seed

        result = execute_seed(self.fake_seed(), db=self.db, apply=True, pepper=PEPPER)

        self.assertTrue(result["errors"])
        self.assertFalse(any(path.startswith("classes/mtc-example/roster/") for path in self.db.store))

    def test_apply_rejects_placeholder_domain_and_placeholder_values(self):
        from mtc_assistant.seed_class_roster import execute_seed

        result = execute_seed(
            self.fake_seed(
                class_id="mtc11",
                students=[{
                    "student_id": "PRIVATE-001",
                    "first_name": "Ada",
                    "last_name": "example.com",
                    "full_name": "TODO",
                    "class_number": 7,
                }],
            ),
            db=self.db,
            apply=True,
            pepper=PEPPER,
        )

        self.assertTrue(result["errors"])
        self.assertFalse(any(path.startswith("classes/mtc11/roster/") for path in self.db.store))

    def test_apply_writes_hmac_roster_without_raw_student_id(self):
        from mtc_assistant.seed_class_roster import execute_seed

        result = execute_seed(
            self.fake_seed(
                class_id="mtc11",
                students=[
                    {
                        "student_id": "PRIVATE-001",
                        "first_name": "Ada",
                        "last_name": "Lovelace",
                        "class_number": 7,
                        "status": "active",
                    }
                ],
            ),
            db=self.db,
            apply=True,
            pepper=PEPPER,
        )

        self.assertFalse(result["errors"])
        roster_paths = [path for path in self.db.store if path.startswith("classes/mtc11/roster/")]
        self.assertEqual(1, len(roster_paths))
        stored = self.db.store[roster_paths[0]]
        self.assertEqual(7, stored["class_number"])
        self.assertNotIn("student_id", stored)
        self.assertNotIn("PRIVATE-001", json.dumps(result))

    def test_seed_output_does_not_print_raw_student_id(self):
        from mtc_assistant.seed_class_roster import main

        def fake_read_text(_path, encoding=None):
            return json.dumps({
                "class_id": "mtc11",
                "students": [{
                    "student_id": "PRIVATE-001",
                    "first_name": "Ada",
                    "last_name": "Lovelace",
                    "class_number": 7,
                }],
            })

        with patch("pathlib.Path.read_text", fake_read_text), \
                patch("mtc_assistant.seed_class_roster._get_firestore_db", return_value=self.db), \
                patch.dict("os.environ", {"STUDENT_ID_PEPPER": PEPPER}, clear=False):
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["--seed", "fake-seed.json"])

        self.assertEqual(0, code)
        self.assertNotIn("PRIVATE-001", out.getvalue())

    def test_production_validation_reports_only_aggregate_metadata(self):
        from mtc_assistant.seed_class_roster import validate_multiple_seeds

        seeds = [
            self._production_seed("mtc11", 31),
            self._production_seed("mtc12", 33),
            self._production_seed("mtc13", 36),
        ]

        result = validate_multiple_seeds(seeds, db=self.db, pepper=PEPPER)
        output = json.dumps(result, ensure_ascii=False)

        self.assertEqual(0, result["counts"]["errors"])
        self.assertEqual(100, result["counts"]["records"])
        self.assertEqual(31, result["classes"]["mtc11"]["record_count"])
        self.assertEqual(33, result["classes"]["mtc12"]["record_count"])
        self.assertEqual(36, result["classes"]["mtc13"]["record_count"])
        self.assertNotIn("PRIVATE-MTC11-001", output)
        self.assertNotIn("First1", output)
        self.assertNotIn("Last1", output)
        self.assertNotIn("student_key", output)

    def test_production_validation_rejects_class_number_gap_and_cross_class_duplicate_id(self):
        from mtc_assistant.seed_class_roster import validate_multiple_seeds

        mtc11 = self._production_seed("mtc11", 31)
        mtc12 = self._production_seed("mtc12", 33)
        mtc13 = self._production_seed("mtc13", 36)
        mtc12["students"][0]["student_id"] = mtc11["students"][0]["student_id"]
        mtc13["students"][2]["class_number"] = 99

        result = validate_multiple_seeds([mtc11, mtc12, mtc13], db=self.db, pepper=PEPPER)

        self.assertGreater(result["counts"]["errors"], 0)
        codes = {error["code"] for error in result["errors"]}
        self.assertIn("cross_class_duplicate_student_id", codes)
        self.assertIn("class_number_sequence_gap", codes)

    def test_apply_requires_matching_registry_grade_when_production_validation_enabled(self):
        from mtc_assistant.seed_class_roster import execute_seed

        seed_registry(self.db, "mtc11", "m5")

        result = execute_seed(
            self._production_seed("mtc11", 31),
            db=self.db,
            apply=True,
            pepper=PEPPER,
            production=True,
        )

        self.assertTrue(result["errors"])
        self.assertIn("registry grade_level mismatch", json.dumps(result))
        self.assertFalse(any(path.startswith("classes/mtc11/roster/") for path in self.db.store))

    def test_rejects_urls_and_paths_in_identity_fields(self):
        from mtc_assistant.seed_class_roster import execute_seed

        seed = self.fake_seed(
            class_id="mtc11",
            students=[{
                "student_id": "PRIVATE-001",
                "title": "นาย",
                "first_name": "https://example.test/name",
                "last_name": r"C:\\private\\name",
                "class_number": 1,
            }],
        )

        result = execute_seed(seed, db=self.db, apply=False, pepper=PEPPER)

        self.assertTrue(result["errors"])
        self.assertNotIn("https://example.test/name", json.dumps(result))

    def _production_seed(self, class_id, count):
        return {
            "class_id": class_id,
            "academic_year": 2569,
            "term_id": "2569-t1",
            "students": [
                {
                    "student_id": f"PRIVATE-{class_id.upper()}-{index:03d}",
                    "title": "นาย" if index % 2 else "นางสาว",
                    "first_name": f"First{index}",
                    "last_name": f"Last{index}",
                    "class_number": index,
                    "status": "active",
                }
                for index in range(1, count + 1)
            ],
        }


if __name__ == "__main__":
    unittest.main()
