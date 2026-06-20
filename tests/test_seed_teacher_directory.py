import json
import unittest

from tests.fake_firestore import FakeDb, seed_registry


class SeedTeacherDirectoryTest(unittest.TestCase):
    def setUp(self):
        self.db = FakeDb()
        for class_id, grade in (("mtc11", "m6"), ("mtc12", "m5"), ("mtc13", "m4")):
            seed_registry(self.db, class_id, grade)

    def fake_seed(self):
        return {
            "teachers": [
                {
                    "teacher_id": "fake-m4-home",
                    "display_name": "ครูสมมติ มอสี่",
                    "verification_code_hash": "scrypt:32768:8:1$fake$hash",
                    "assignments": [{
                        "class_id": "mtc13",
                        "assignment_roles": ["mtc_math_adviser", "homeroom_teacher"],
                    }],
                },
                {
                    "teacher_id": "fake-m4-adviser",
                    "display_name": "ครูตัวอย่าง มอสี่",
                    "verification_code_hash": "scrypt:32768:8:1$fake$hash",
                    "assignments": [{
                        "class_id": "mtc13",
                        "assignment_roles": ["mtc_math_adviser"],
                    }],
                },
                {
                    "teacher_id": "fake-m5-home",
                    "display_name": "ครูสมมติ มอห้า",
                    "verification_code_hash": "scrypt:32768:8:1$fake$hash",
                    "assignments": [{
                        "class_id": "mtc12",
                        "assignment_roles": ["mtc_math_adviser", "homeroom_teacher"],
                    }],
                },
                {
                    "teacher_id": "fake-m5-adviser",
                    "display_name": "ครูตัวอย่าง มอห้า",
                    "verification_code_hash": "scrypt:32768:8:1$fake$hash",
                    "assignments": [{
                        "class_id": "mtc12",
                        "assignment_roles": ["mtc_math_adviser"],
                    }],
                },
                {
                    "teacher_id": "fake-m6-home",
                    "display_name": "ครูสมมติ มอหก",
                    "verification_code_hash": "scrypt:32768:8:1$fake$hash",
                    "assignments": [{
                        "class_id": "mtc11",
                        "assignment_roles": ["mtc_math_adviser", "homeroom_teacher"],
                    }],
                },
            ],
        }

    def test_dry_run_validates_three_class_assignment_matrix(self):
        from mtc_assistant.seed_teacher_directory import execute_seed

        result = execute_seed(self.fake_seed(), db=self.db, apply=False)

        self.assertFalse(result["errors"])
        self.assertEqual({"mtc13": 2, "mtc12": 2, "mtc11": 1}, result["assignment_counts"])
        self.assertEqual(5, result["counts"]["would_upsert"])
        self.assertEqual(5, result["counts"]["single_assignment_teachers"])
        self.assertEqual(3, result["counts"]["homeroom_teachers"])

    def test_apply_writes_directory_and_verification_without_plaintext_code(self):
        from mtc_assistant.seed_teacher_directory import execute_seed

        result = execute_seed(self.fake_seed(), db=self.db, apply=True)

        self.assertFalse(result["errors"])
        directory = self.db.store["system/teacher_directory/records/fake-m4-home"]
        verification = self.db.store["system/teacher_verification/records/fake-m4-home"]
        self.assertEqual("verified", directory["verification_status"])
        self.assertEqual(["mtc13"], directory["assigned_class_ids"])
        self.assertNotIn("verification_code", directory)
        self.assertIn("verification_code_hash", verification)
        self.assertNotIn("teacher-code-1234", json.dumps(self.db.store, ensure_ascii=False))

    def test_rejects_plaintext_code_or_internal_role_escalation(self):
        from mtc_assistant.seed_teacher_directory import execute_seed

        seed = self.fake_seed()
        seed["teachers"][0]["verification_code"] = "plaintext"
        seed["teachers"][1]["assignments"][0]["assignment_roles"].append("class_admin")

        result = execute_seed(seed, db=self.db, apply=True)

        self.assertTrue(result["errors"])
        self.assertFalse(any(path.startswith("system/teacher_directory/records/") for path in self.db.store))


if __name__ == "__main__":
    unittest.main()
