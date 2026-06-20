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


if __name__ == "__main__":
    unittest.main()
