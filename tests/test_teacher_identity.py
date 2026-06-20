import json
import unittest

from linebot.v3.messaging import FlexMessage

from mtc_assistant.dashboard_auth_models import hash_password
from tests.fake_firestore import FakeDb, seed_registry


class TeacherIdentityTest(unittest.TestCase):
    def setUp(self):
        self.db = FakeDb()
        for class_id, grade in (("mtc11", "m6"), ("mtc12", "m5"), ("mtc13", "m4")):
            seed_registry(self.db, class_id, grade, room_label=f"ห้อง-{grade}")
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
        self.db.store["system/teacher_verification/records/t-fake-1"] = {
            "verification_code_hash": hash_password("teacher-code-1234", "t-fake-1"),
            "status": "active",
        }

    def test_teacher_name_alone_cannot_verify_identity(self):
        from mtc_assistant.identity_verification import IdentitySessionService

        service = IdentitySessionService(self.db)
        service.start("user-a")
        service.handle_message("user-a", "คุณครู MTC")
        result = service.handle_message("user-a", "ครูตัวอย่าง หนึ่ง")

        self.assertTrue(result.success)
        self.assertIn("รหัสยืนยัน", result.message.text)
        self.assertNotIn("users/user-a", self.db.store)

    def test_correct_teacher_one_time_code_verifies_assigned_class_only(self):
        from mtc_assistant.identity_verification import IdentitySessionService

        service = IdentitySessionService(self.db)
        service.start("user-a")
        for text in ("คุณครู MTC", "ครูตัวอย่าง หนึ่ง"):
            service.handle_message("user-a", text)
        result = service.handle_message("user-a", "teacher-code-1234")

        self.assertTrue(result.success)
        root = self.db.store["users/user-a"]
        self.assertEqual("mtc_teacher", root["identity_type"])
        self.assertEqual("verified", root["verification_status"])
        self.assertEqual(["mtc13"], root["class_ids"])
        self.assertEqual("mtc13", root["active_class_id"])
        class_user = self.db.store["classes/mtc13/users/user-a"]
        self.assertEqual("teacher", class_user["role"])
        self.assertEqual(["mtc_math_adviser", "homeroom_teacher"], class_user["assignment_roles"])
        self.assertNotIn("classes/mtc12/users/user-a", self.db.store)
        self.assertNotIn("classes/mtc11/users/user-a", self.db.store)
        self.assertNotIn("class_admin", json.dumps(root))
        self.assertNotIn("super_admin", json.dumps(class_user))
        self.assertIn("used_at", self.db.store["system/teacher_verification/records/t-fake-1"])

    def test_wrong_or_used_teacher_code_fails_generically(self):
        from mtc_assistant.identity_verification import IdentitySessionService

        service = IdentitySessionService(self.db)
        service.start("user-a")
        for text in ("คุณครู MTC", "ครูตัวอย่าง หนึ่ง"):
            service.handle_message("user-a", text)
        wrong = service.handle_message("user-a", "wrong-code")

        self.assertFalse(wrong.success)
        self.assertNotIn("users/user-a", self.db.store)
        self.assertNotIn("wrong-code", json.dumps(self.db.store, ensure_ascii=False))

        service = IdentitySessionService(self.db)
        service.start("user-a")
        for text in ("คุณครู MTC", "ครูตัวอย่าง หนึ่ง", "teacher-code-1234"):
            service.handle_message("user-a", text)
        service.start("user-b")
        for text in ("คุณครู MTC", "ครูตัวอย่าง หนึ่ง"):
            service.handle_message("user-b", text)
        reused = service.handle_message("user-b", "teacher-code-1234")

        self.assertFalse(reused.success)
        self.assertNotIn("users/user-b", self.db.store)

    def test_teacher_bound_to_other_line_user_is_rejected(self):
        from mtc_assistant.identity_verification import IdentitySessionService

        self.db.store["system/teacher_directory/records/t-fake-1"]["bound_user_id"] = "other-user"
        service = IdentitySessionService(self.db)
        service.start("user-a")
        for text in ("คุณครู MTC", "ครูตัวอย่าง หนึ่ง"):
            service.handle_message("user-a", text)
        result = service.handle_message("user-a", "teacher-code-1234")

        self.assertFalse(result.success)
        self.assertNotIn("users/user-a", self.db.store)

    def test_verified_teacher_account_card_shows_public_roles_only(self):
        from mtc_assistant.user_account_service import build_account_message

        self.db.store["users/user-a"] = {
            "line_display_name": "LINE Teacher",
            "identity_type": "mtc_teacher",
            "verification_status": "verified",
            "class_ids": ["mtc13"],
            "active_class_id": "mtc13",
        }
        self.db.store["classes/mtc13/users/user-a"] = {
            "display_name": "ครูตัวอย่าง หนึ่ง",
            "role": "teacher",
            "status": "active",
            "verification_status": "verified",
            "assignment_roles": ["mtc_math_adviser", "homeroom_teacher"],
        }

        message = build_account_message(self.db, "user-a")

        self.assertIsInstance(message, FlexMessage)
        payload = json.dumps(message.contents.to_dict(), ensure_ascii=False)
        self.assertIn("คุณครู MTC", payload)
        self.assertIn("ครูประจำชั้น", payload)
        self.assertIn("ครูคณิตศาสตร์ที่ปรึกษา MTC", payload)
        self.assertIn("MTC13", payload)
        self.assertIn("m4", payload)
        self.assertNotIn("t-fake-1", payload)
        self.assertNotIn("mtc_math_adviser", payload)

    def test_custom_max_attempts_disables_after_limit(self):
        # 1. Test custom max_attempts = 3
        self.db.store["system/teacher_verification/records/t-fake-1"] = {
            "verification_code_hash": hash_password("teacher-code-1234", "t-fake-1"),
            "status": "active",
            "max_attempts": 3,
            "failed_attempts": 0,
        }
        from mtc_assistant.teacher_identity import verify_teacher_code_and_bind

        # Attempt 1 (fail)
        r1 = verify_teacher_code_and_bind(self.db, "user-a", "t-fake-1", "wrong")
        self.assertFalse(r1.success)
        self.assertEqual(1, self.db.store["system/teacher_verification/records/t-fake-1"]["failed_attempts"])
        self.assertEqual("active", self.db.store["system/teacher_verification/records/t-fake-1"]["status"])

        # Attempt 2 (fail)
        r2 = verify_teacher_code_and_bind(self.db, "user-a", "t-fake-1", "wrong")
        self.assertFalse(r2.success)
        self.assertEqual(2, self.db.store["system/teacher_verification/records/t-fake-1"]["failed_attempts"])
        self.assertEqual("active", self.db.store["system/teacher_verification/records/t-fake-1"]["status"])

        # Attempt 3 (fail -> reaches 3 attempts, disables)
        r3 = verify_teacher_code_and_bind(self.db, "user-a", "t-fake-1", "wrong")
        self.assertFalse(r3.success)
        self.assertEqual(3, self.db.store["system/teacher_verification/records/t-fake-1"]["failed_attempts"])
        self.assertEqual("disabled", self.db.store["system/teacher_verification/records/t-fake-1"]["status"])

        # Attempt 4 (fail, status already disabled)
        r4 = verify_teacher_code_and_bind(self.db, "user-a", "t-fake-1", "teacher-code-1234")
        self.assertFalse(r4.success)

    def test_default_missing_max_attempts_falls_back_to_five(self):
        self.db.store["system/teacher_verification/records/t-fake-1"] = {
            "verification_code_hash": hash_password("teacher-code-1234", "t-fake-1"),
            "status": "active",
            "failed_attempts": 4, # 4 attempts done
        }
        from mtc_assistant.teacher_identity import verify_teacher_code_and_bind

        # Attempt 5 (fail -> reaches 5 attempts, disables)
        r = verify_teacher_code_and_bind(self.db, "user-a", "t-fake-1", "wrong")
        self.assertFalse(r.success)
        self.assertEqual(5, self.db.store["system/teacher_verification/records/t-fake-1"]["failed_attempts"])
        self.assertEqual("disabled", self.db.store["system/teacher_verification/records/t-fake-1"]["status"])

    def test_max_attempts_bounds_correctly(self):
        from mtc_assistant.teacher_identity import verify_teacher_code_and_bind

        # Value below 1 should bound to 1
        self.db.store["system/teacher_verification/records/t-fake-1"] = {
            "verification_code_hash": hash_password("teacher-code-1234", "t-fake-1"),
            "status": "active",
            "max_attempts": 0,
            "failed_attempts": 0,
        }
        r1 = verify_teacher_code_and_bind(self.db, "user-a", "t-fake-1", "wrong")
        self.assertFalse(r1.success)
        self.assertEqual("disabled", self.db.store["system/teacher_verification/records/t-fake-1"]["status"])

        # Value above 10 should bound to 10
        self.db.store["system/teacher_verification/records/t-fake-1"] = {
            "verification_code_hash": hash_password("teacher-code-1234", "t-fake-1"),
            "status": "active",
            "max_attempts": 100,
            "failed_attempts": 9,
        }
        r2 = verify_teacher_code_and_bind(self.db, "user-a", "t-fake-1", "wrong")
        self.assertFalse(r2.success)
        self.assertEqual("disabled", self.db.store["system/teacher_verification/records/t-fake-1"]["status"])

        # Malformed value should fallback to 5
        self.db.store["system/teacher_verification/records/t-fake-1"] = {
            "verification_code_hash": hash_password("teacher-code-1234", "t-fake-1"),
            "status": "active",
            "max_attempts": "not-an-integer",
            "failed_attempts": 4,
        }
        r3 = verify_teacher_code_and_bind(self.db, "user-a", "t-fake-1", "wrong")
        self.assertFalse(r3.success)
        self.assertEqual("disabled", self.db.store["system/teacher_verification/records/t-fake-1"]["status"])

    def test_successful_verification_before_limit_succeeds_and_prevents_reuse(self):
        self.db.store["system/teacher_verification/records/t-fake-1"] = {
            "verification_code_hash": hash_password("teacher-code-1234", "t-fake-1"),
            "status": "active",
            "max_attempts": 3,
            "failed_attempts": 2,
        }
        from mtc_assistant.teacher_identity import verify_teacher_code_and_bind

        # Verification succeeds (only 2 failed attempts prior, limit is 3)
        r1 = verify_teacher_code_and_bind(self.db, "user-a", "t-fake-1", "teacher-code-1234")
        self.assertTrue(r1.success)
        self.assertEqual("used", self.db.store["system/teacher_verification/records/t-fake-1"]["status"])
        self.assertIsNotNone(self.db.store["system/teacher_verification/records/t-fake-1"].get("used_at"))

        # Re-verification attempt fails (reuse blocked)
        r2 = verify_teacher_code_and_bind(self.db, "user-b", "t-fake-1", "teacher-code-1234")
        self.assertFalse(r2.success)


if __name__ == "__main__":
    unittest.main()
