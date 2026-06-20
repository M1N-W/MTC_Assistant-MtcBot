import json
import unittest

from linebot.v3.messaging import FlexMessage

from tests.fake_firestore import FakeDb, seed_class_user, seed_registry


PEPPER = "test-pepper-with-enough-length"


class LineAccountIdentityTest(unittest.TestCase):
    def setUp(self):
        self.db = FakeDb()
        for class_id, grade in (("mtc11", "m6"), ("mtc12", "m5"), ("mtc13", "m4")):
            seed_registry(self.db, class_id, grade)

    def test_student_key_is_hmac_and_raw_student_id_is_not_persisted(self):
        from mtc_assistant.identity_verification import build_student_key

        key = build_student_key("  12345  ", PEPPER)

        self.assertEqual(64, len(key))
        self.assertNotIn("12345", key)

    def test_identity_session_persists_only_student_key_after_id_step(self):
        from mtc_assistant.identity_verification import (
            IDENTITY_SESSION_DOC_ID,
            IdentitySessionService,
            build_student_key,
        )

        service = IdentitySessionService(self.db, pepper=PEPPER)
        service.start("user-a")
        service.handle_message("user-a", "MTC11")
        service.handle_message("user-a", "12345")

        session = self.db.store[f"users/user-a/sessions/{IDENTITY_SESSION_DOC_ID}"]
        self.assertEqual(build_student_key("12345", PEPPER), session["student_key"])
        self.assertNotIn("student_id", session)
        self.assertNotIn("raw_student_id", session)
        self.assertNotIn("submitted_student_id", session)

    def test_verification_binds_only_matching_class_roster(self):
        from mtc_assistant.identity_verification import IdentitySessionService, build_student_key

        key = build_student_key("ABC001", PEPPER)
        self.db.store[f"classes/mtc11/roster/{key}"] = {
            "first_name": "Ada",
            "last_name": "Lovelace",
            "full_name": "Ada Lovelace",
            "normalized_first_name": "Ada",
            "normalized_last_name": "Lovelace",
            "class_number": 7,
            "status": "active",
        }
        self.db.store[f"classes/mtc12/roster/{key}"] = {
            "first_name": "Wrong",
            "last_name": "Class",
            "normalized_first_name": "Wrong",
            "normalized_last_name": "Class",
            "class_number": 7,
            "status": "active",
        }

        service = IdentitySessionService(self.db, pepper=PEPPER)
        service.start("user-a")
        for text in ("MTC11", "ABC001", "Ada", "Lovelace", "7"):
            service.handle_message("user-a", text)
        result = service.handle_message("user-a", "ยืนยัน")

        self.assertTrue(result.success)
        self.assertEqual("verified", self.db.store["users/user-a"]["identity_status"])
        self.assertEqual(["mtc11"], self.db.store["users/user-a"]["class_ids"])
        class_user = self.db.store["classes/mtc11/users/user-a"]
        self.assertEqual(7, class_user["class_number"])
        self.assertEqual("verified", class_user["verification_status"])
        self.assertNotIn("student_id", class_user)

    def test_duplicate_roster_binding_to_other_line_user_fails_safely(self):
        from mtc_assistant.identity_verification import IdentitySessionService, build_student_key

        key = build_student_key("ABC001", PEPPER)
        self.db.store[f"classes/mtc11/roster/{key}"] = {
            "first_name": "Ada",
            "last_name": "Lovelace",
            "normalized_first_name": "Ada",
            "normalized_last_name": "Lovelace",
            "class_number": 7,
            "status": "active",
            "bound_user_id": "other-user",
        }

        service = IdentitySessionService(self.db, pepper=PEPPER)
        service.start("user-a")
        for text in ("MTC11", "ABC001", "Ada", "Lovelace", "7"):
            service.handle_message("user-a", text)
        result = service.handle_message("user-a", "ยืนยัน")

        self.assertFalse(result.success)
        self.assertNotIn("classes/mtc11/users/user-a", self.db.store)

    def test_class_selection_allows_invite_membership_without_verifying_identity(self):
        from mtc_assistant.class_selection import select_active_class

        self.db.store["users/user-a"] = {
            "user_id": "user-a",
            "class_ids": ["mtc11", "mtc12"],
            "active_class_id": "mtc12",
            "identity_status": "unverified",
        }
        seed_class_user(self.db, "mtc11", "user-a", verification_status="unverified")
        seed_class_user(self.db, "mtc12", "user-a", verification_status="unverified")

        result = select_active_class(self.db, "user-a", "mtc11")

        self.assertTrue(result.success)
        self.assertEqual("mtc11", self.db.store["users/user-a"]["active_class_id"])
        self.assertEqual("unverified", self.db.store["classes/mtc11/users/user-a"]["verification_status"])

    def test_class_selection_rejects_unauthorized_class(self):
        from mtc_assistant.class_selection import select_active_class

        self.db.store["users/user-a"] = {"class_ids": ["mtc12"], "active_class_id": "mtc12"}
        seed_class_user(self.db, "mtc12", "user-a")

        result = select_active_class(self.db, "user-a", "mtc11")

        self.assertFalse(result.success)
        self.assertNotEqual("mtc11", self.db.store["users/user-a"]["active_class_id"])

    def test_account_card_verified_state_has_grade_and_no_sensitive_identifiers(self):
        from mtc_assistant.user_account_service import build_account_message

        self.db.store["users/user-a"] = {
            "line_display_name": "Line Name",
            "line_picture_url": "https://example.com/profile.png",
            "class_ids": ["mtc11"],
            "active_class_id": "mtc11",
            "identity_status": "verified",
        }
        self.db.store["classes/mtc11/users/user-a"] = {
            "full_name": "Ada Lovelace",
            "class_number": 7,
            "role": "student",
            "verification_status": "verified",
            "roster_key": "secret-roster-key",
            "status": "active",
        }

        message = build_account_message(self.db, "user-a")

        self.assertIsInstance(message, FlexMessage)
        payload = json.dumps(message.contents.to_dict(), ensure_ascii=False)
        self.assertIn("MTC11", payload)
        self.assertIn("m6", payload)
        self.assertIn("เลขที่ 7", payload)
        self.assertNotIn("user-a", payload)
        self.assertNotIn("secret-roster-key", payload)

    def test_account_card_missing_optional_mtc11_metadata_is_safe(self):
        from mtc_assistant.user_account_service import build_account_message

        self.db.store["users/user-a"] = {
            "line_display_name": "Line Name",
            "class_ids": ["mtc11"],
            "active_class_id": "mtc11",
            "identity_status": "unverified",
        }
        seed_class_user(self.db, "mtc11", "user-a", verification_status="unverified")

        message = build_account_message(self.db, "user-a")

        payload = json.dumps(message.contents.to_dict(), ensure_ascii=False)
        self.assertIn("ยังไม่ได้ตั้งค่าภาคเรียน", payload)
        self.assertNotIn("mtc12", payload.lower())

    def test_account_card_does_not_render_invalid_stored_picture_url(self):
        from mtc_assistant.user_account_service import build_account_message

        self.db.store["users/user-a"] = {
            "line_display_name": "Line Name",
            "line_picture_url": "http://not-secure.example/profile.png",
            "class_ids": ["mtc11"],
            "active_class_id": "mtc11",
        }
        seed_class_user(self.db, "mtc11", "user-a")

        message = build_account_message(self.db, "user-a")

        payload = json.dumps(message.contents.to_dict(), ensure_ascii=False)
        self.assertNotIn("http://not-secure.example/profile.png", payload)

    def test_line_profile_sync_caches_https_picture_only(self):
        from mtc_assistant.line_profile_service import sync_line_profile_if_stale

        class Profile:
            display_name = "LINE Mawin"
            picture_url = "http://not-secure.example/profile.png"

        class Api:
            def __init__(self):
                self.calls = 0

            def get_profile(self, user_id):
                self.calls += 1
                return Profile()

        api = Api()
        sync_line_profile_if_stale(self.db, "user-a", api)

        user = self.db.store["users/user-a"]
        self.assertEqual("LINE Mawin", user["line_display_name"])
        self.assertNotIn("line_picture_url", user)
        self.assertEqual(1, api.calls)

    def test_identity_redaction_hides_active_session_input(self):
        from mtc_assistant.identity_verification import IdentitySessionService, redacted_message_for_logging

        service = IdentitySessionService(self.db, pepper=PEPPER)
        service.start("user-a")

        self.assertEqual("[identity input redacted]", redacted_message_for_logging(self.db, "user-a", "12345"))


if __name__ == "__main__":
    unittest.main()
