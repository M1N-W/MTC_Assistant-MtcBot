import io
import json
import unittest
from unittest.mock import patch

from tests.fake_firestore import FakeDb
from mtc_assistant.issue_teacher_verification_code import main
from mtc_assistant.teacher_identity import verify_teacher_code_and_bind


class IssueTeacherVerificationCodeTest(unittest.TestCase):
    def setUp(self):
        self.db = FakeDb()
        self.db.store["system/teacher_directory/records/t-fake-1"] = {
            "teacher_id": "t-fake-1",
            "display_name": "ครูตัวอย่าง หนึ่ง",
            "normalized_full_name": "ครูตัวอย่าง หนึ่ง",
            "status": "active",
            "verification_status": "unverified",
            "assignments": [{
                "class_id": "mtc13",
                "assignment_roles": ["mtc_math_adviser", "homeroom_teacher"],
            }],
        }
        self.db.store["system/teacher_directory/records/t-inactive"] = {
            "teacher_id": "t-inactive",
            "display_name": "ครู ตัวร้าย",
            "status": "disabled",
            "verification_status": "unverified",
            "assignments": [],
        }

    def test_dry_run_is_default_and_performs_no_write(self):
        with patch("mtc_assistant.issue_teacher_verification_code.connect_firestore", return_value=self.db), \
             patch("sys.stdout", new=io.StringIO()) as out:
            code = main(["--teacher-id", "t-fake-1"])

        self.assertEqual(0, code)
        self.assertNotIn("SUCCESS", out.getvalue())
        data = json.loads(out.getvalue())
        self.assertTrue(data["dry_run"])
        self.assertEqual("t-fake-1", data["teacher_id"])
        self.assertFalse(data["existing_credential_replaced"])
        self.assertNotIn("system/teacher_verification/records/t-fake-1", self.db.store)

    def test_dry_run_and_apply_cannot_be_combined(self):
        with patch("sys.stderr", new=io.StringIO()) as err:
            code = main(["--teacher-id", "t-fake-1", "--dry-run", "--apply"])
        self.assertEqual(1, code)
        self.assertIn("mutually exclusive", err.getvalue())

    def test_missing_teacher_id_is_rejected(self):
        # argparse raises SystemExit when missing required args
        with self.assertRaises(SystemExit):
            main([])

    def test_malformed_teacher_id_is_rejected(self):
        with patch("sys.stderr", new=io.StringIO()) as err:
            code = main(["--teacher-id", "bad id!!", "--apply"])
        self.assertEqual(1, code)
        self.assertIn("Invalid teacher_id format", err.getvalue())

    def test_missing_teacher_record_fails_safely(self):
        with patch("mtc_assistant.issue_teacher_verification_code.connect_firestore", return_value=self.db), \
             patch("sys.stderr", new=io.StringIO()) as err:
            code = main(["--teacher-id", "t-nonexistent", "--apply"])
        self.assertEqual(1, code)
        self.assertIn("Teacher record does not exist", err.getvalue())

    def test_inactive_teacher_record_fails_safely(self):
        with patch("mtc_assistant.issue_teacher_verification_code.connect_firestore", return_value=self.db), \
             patch("sys.stderr", new=io.StringIO()) as err:
            code = main(["--teacher-id", "t-inactive", "--apply"])
        self.assertEqual(1, code)
        self.assertIn("Teacher is not active", err.getvalue())

    def test_successful_apply_writes_correct_credential_document(self):
        with patch("mtc_assistant.issue_teacher_verification_code.connect_firestore", return_value=self.db), \
             patch("sys.stdout", new=io.StringIO()) as out:
            code = main(["--teacher-id", "t-fake-1", "--apply", "--expires-in-hours", "12", "--max-attempts", "7"])

        self.assertEqual(0, code)
        self.assertIn("SUCCESS", out.getvalue())
        
        # Extract code from output
        output = out.getvalue()
        self.assertIn("Code: ", output)
        generated_code = ""
        for line in output.splitlines():
            if line.startswith("Code: "):
                generated_code = line.split("Code: ")[1].strip()

        self.assertEqual(16, len(generated_code))
        
        doc_path = "system/teacher_verification/records/t-fake-1"
        self.assertIn(doc_path, self.db.store)
        doc = self.db.store[doc_path]
        
        self.assertEqual("t-fake-1", doc["teacher_id"])
        self.assertEqual("active", doc["status"])
        self.assertEqual(0, doc["failed_attempts"])
        self.assertEqual(7, doc["max_attempts"])
        self.assertIn("expires_at", doc)
        self.assertIn("created_at", doc)
        
        # Verify hash matches code
        from mtc_assistant.dashboard_auth_models import verify_password
        self.assertTrue(verify_password(doc["verification_code_hash"], generated_code))
        self.assertNotIn(generated_code, doc["verification_code_hash"])

    def test_existing_unused_credential_is_replaced_safely(self):
        # Seed an old credential
        doc_path = "system/teacher_verification/records/t-fake-1"
        self.db.store[doc_path] = {
            "teacher_id": "t-fake-1",
            "verification_code_hash": "old-hash",
            "status": "active",
            "failed_attempts": 2,
            "max_attempts": 5,
        }

        with patch("mtc_assistant.issue_teacher_verification_code.connect_firestore", return_value=self.db), \
             patch("sys.stdout", new=io.StringIO()) as out:
            code = main(["--teacher-id", "t-fake-1", "--apply"])

        self.assertEqual(0, code)
        doc = self.db.store[doc_path]
        self.assertNotEqual("old-hash", doc["verification_code_hash"])
        self.assertEqual(0, doc["failed_attempts"])  # Reset

        # Verify teacher assignments and binding are untouched
        teacher = self.db.store["system/teacher_directory/records/t-fake-1"]
        self.assertNotIn("bound_user_id", teacher)
        self.assertEqual("unverified", teacher["verification_status"])

    def test_firestore_write_failure_does_not_leak_code(self):
        """Firestore write failure must not print the plaintext code to stdout."""
        from tests.fake_firestore import FakeDb, FakeDocRef, FakeCollection

        VERIFICATION_PATH = "system/teacher_verification/records/t-fake-1"

        class FailOnSetDocRef(FakeDocRef):
            """FakeDocRef that raises RuntimeError on set() for the verification doc."""
            def set(self, data, merge=False):
                if self.path == VERIFICATION_PATH:
                    raise RuntimeError("Simulated Firestore write failure")
                super().set(data, merge=merge)

            def collection(self, name):
                return FailOnWriteCollection(self.db, f"{self.path}/{name}")

        class FailOnWriteCollection(FakeCollection):
            def document(self, doc_id):
                return FailOnSetDocRef(self.db, f"{self.path}/{doc_id}")

        class FailOnWriteDb(FakeDb):
            def collection(self, name):
                return FailOnWriteCollection(self, name)

        broken_db = FailOnWriteDb()
        # Seed the teacher directory record so reads succeed
        broken_db.store["system/teacher_directory/records/t-fake-1"] = {
            "teacher_id": "t-fake-1",
            "display_name": "ครูตัวอย่าง หนึ่ง",
            "status": "active",
        }

        with patch("mtc_assistant.issue_teacher_verification_code.connect_firestore", return_value=broken_db), \
             patch("sys.stdout", new=io.StringIO()) as out, \
             patch("sys.stderr", new=io.StringIO()) as err:
            code = main(["--teacher-id", "t-fake-1", "--apply"])

        self.assertEqual(1, code)
        self.assertIn("Error", err.getvalue())
        self.assertNotIn("SUCCESS", out.getvalue())
        self.assertNotIn("Code:", out.getvalue())

    def test_verification_runtime_consumes_newly_issued_credential(self):
        # 1. Issue code
        with patch("mtc_assistant.issue_teacher_verification_code.connect_firestore", return_value=self.db), \
             patch("sys.stdout", new=io.StringIO()) as out:
            main(["--teacher-id", "t-fake-1", "--apply"])

        output = out.getvalue()
        generated_code = ""
        for line in output.splitlines():
            if line.startswith("Code: "):
                generated_code = line.split("Code: ")[1].strip()

        # 2. Run runtime verification
        from mtc_assistant.identity_verification import IdentitySessionService
        service = IdentitySessionService(self.db)
        service.start("user-a")
        service.handle_message("user-a", "คุณครู MTC")
        service.handle_message("user-a", "ครูตัวอย่าง หนึ่ง")
        result = service.handle_message("user-a", generated_code)

        self.assertTrue(result.success)
        self.assertEqual("verified", self.db.store["users/user-a"]["verification_status"])
        self.assertEqual("used", self.db.store["system/teacher_verification/records/t-fake-1"]["status"])

        # 3. Attempt reuse
        service.start("user-b")
        service.handle_message("user-b", "คุณครู MTC")
        service.handle_message("user-b", "ครูตัวอย่าง หนึ่ง")
        result2 = service.handle_message("user-b", generated_code)
        self.assertFalse(result2.success)


if __name__ == "__main__":
    unittest.main()
