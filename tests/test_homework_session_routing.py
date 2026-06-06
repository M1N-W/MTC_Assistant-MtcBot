from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

import mtc_assistant.handlers as handlers
from mtc_assistant.class_context import ClassContext
from mtc_assistant.command_router import handle_standard_command
from mtc_assistant.constants import HOMEWORK_VIEW_COMMANDS
from mtc_assistant.homework_session import (
    cancel_homework_session,
    handle_homework_session,
    has_homework_session,
    start_homework_session,
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

    def set(self, data, merge=False):
        if merge and self.path in self.db.store:
            self.db.store[self.path].update(data)
        else:
            self.db.store[self.path] = dict(data)

    def delete(self):
        self.db.store.pop(self.path, None)

    def collection(self, name):
        return FakeCollection(self.db, f"{self.path}/{name}")


class FakeCollection:
    def __init__(self, db, path):
        self.db = db
        self.path = path

    def document(self, doc_id=None):
        doc_id = doc_id or f"auto-{len(self.db.store) + 1}"
        return FakeDocRef(self.db, f"{self.path}/{doc_id}")


class FakeDb:
    def __init__(self):
        self.store = {}

    def collection(self, name):
        return FakeCollection(self, name)


class FailingDocRef(FakeDocRef):
    def get(self):
        if self.db.fail_get:
            raise RuntimeError("read failed")
        return super().get()

    def set(self, data, merge=False):
        if self.db.fail_set:
            raise RuntimeError("write failed")
        return super().set(data, merge=merge)

    def delete(self):
        if self.db.fail_delete:
            raise RuntimeError("delete failed")
        return super().delete()

    def collection(self, name):
        return FailingCollection(self.db, f"{self.path}/{name}")


class FailingCollection(FakeCollection):
    def document(self, doc_id=None):
        doc_id = doc_id or f"auto-{len(self.db.store) + 1}"
        return FailingDocRef(self.db, f"{self.path}/{doc_id}")


class FailingDb(FakeDb):
    def __init__(self, fail_get=False, fail_set=False, fail_delete=False):
        super().__init__()
        self.fail_get = fail_get
        self.fail_set = fail_set
        self.fail_delete = fail_delete

    def collection(self, name):
        return FailingCollection(self, name)


class FakeMessage:
    def __init__(self, text):
        self.text = text


class FakeSource:
    user_id = "test-user"


class FakeEvent:
    def __init__(self, text):
        self.message = FakeMessage(text)
        self.source = FakeSource()
        self.reply_token = "reply-token"


class HomeworkSessionRoutingTest(unittest.TestCase):
    def tearDown(self):
        cancel_homework_session("test-user")

    def test_homework_detail_can_contain_existing_command_words(self):
        start_homework_session("test-user")
        subject_reply = handle_homework_session("test-user", "อังกฤษพื้นฐาน")
        detail_reply = handle_homework_session("test-user", "เคลียร์การบ้าน")

        self.assertIn("พิมพ์รายละเอียดการบ้านได้เลย", subject_reply.text)
        self.assertIn("รายละเอียด: เคลียร์การบ้าน", detail_reply.text)
        self.assertIn("กำหนดส่งวันไหน", detail_reply.text)
        self.assertTrue(has_homework_session("test-user"))

    def test_broad_homework_keyword_does_not_match_inside_longer_text(self):
        reply = handle_standard_command("เคลียร์การบ้าน", "เคลียร์การบ้าน")

        self.assertIsNone(reply)

    def test_homework_command_is_reserved_for_persisted_homework_records(self):
        self.assertIn("การบ้าน", HOMEWORK_VIEW_COMMANDS)
        self.assertIsNone(handle_standard_command("การบ้าน", "การบ้าน"))

    def test_homework_session_continues_from_firestore_when_memory_is_empty(self):
        db = FakeDb()
        class_context = ClassContext("mtc13", "test-user")

        start_homework_session("test-user", class_context=class_context, db=db)
        cancel_homework_session("test-user")

        subject_reply = handle_homework_session("test-user", "ฟิสิกส์", db=db)
        detail_reply = handle_homework_session("test-user", "แบบฝึกหัด 5.2", db=db)

        self.assertIn("พิมพ์รายละเอียดการบ้านได้เลย", subject_reply.text)
        self.assertIn("รายละเอียด: แบบฝึกหัด 5.2", detail_reply.text)
        self.assertIn("กำหนดส่งวันไหน", detail_reply.text)
        self.assertEqual(
            "แบบฝึกหัด 5.2",
            db.store["users/test-user/sessions/homework_create"]["detail"],
        )

    def test_due_date_saves_homework_and_clears_firestore_session(self):
        db = FakeDb()
        class_context = ClassContext("mtc13", "test-user")

        start_homework_session("test-user", class_context=class_context, db=db)
        handle_homework_session("test-user", "ฟิสิกส์", db=db)
        handle_homework_session("test-user", "แบบฝึกหัด 5.2", db=db)

        with patch("mtc_assistant.homework_session.add_homework_to_db", return_value="บันทึกการบ้านวิชา ฟิสิกส์ เรียบร้อยแล้ว") as add_homework:
            success_reply = handle_homework_session("test-user", "พรุ่งนี้", db=db)

        add_homework.assert_called_once()
        self.assertEqual("ฟิสิกส์", add_homework.call_args.args[0])
        self.assertEqual("แบบฝึกหัด 5.2", add_homework.call_args.args[1])
        self.assertEqual("พรุ่งนี้", add_homework.call_args.args[2])
        self.assertEqual("mtc13", add_homework.call_args.kwargs["class_context"].class_id)
        self.assertIn("บันทึกการบ้านแล้ว", success_reply.text)
        self.assertNotIn("users/test-user/sessions/homework_create", db.store)

    def test_corrupt_firestore_session_fails_closed_and_clears_session(self):
        db = FakeDb()
        db.store["users/test-user/sessions/homework_create"] = {"step": "detail"}

        reply = handle_homework_session("test-user", "แบบฝึกหัด 5.2", db=db)

        self.assertIn("เริ่มบันทึกการบ้านใหม่", reply.text)
        self.assertNotIn("users/test-user/sessions/homework_create", db.store)

    def test_expired_firestore_session_fails_closed_and_clears_session(self):
        db = FakeDb()
        db.store["users/test-user/sessions/homework_create"] = {
            "step": "detail",
            "subject": "ฟิสิกส์",
            "expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        }

        reply = handle_homework_session("test-user", "แบบฝึกหัด 5.2", db=db)

        self.assertIn("เริ่มบันทึกการบ้านใหม่", reply.text)
        self.assertNotIn("users/test-user/sessions/homework_create", db.store)

    def test_cancel_clears_firestore_session(self):
        db = FakeDb()
        start_homework_session("test-user", class_context=ClassContext("mtc13", "test-user"), db=db)

        result = cancel_homework_session("test-user", db=db)

        self.assertEqual("ยกเลิกการเพิ่มการบ้านแล้ว", result)
        self.assertNotIn("users/test-user/sessions/homework_create", db.store)

    def test_active_session_text_does_not_call_gemini_fallback(self):
        db = FakeDb()
        db.store["users/test-user"] = {"user_id": "test-user", "active_class_id": "mtc13"}
        start_homework_session("test-user", class_context=ClassContext("mtc13", "test-user"), db=db)
        handle_homework_session("test-user", "ฟิสิกส์", db=db)
        cancel_homework_session("test-user")
        replies = []

        def fake_reply(_token, messages):
            replies.extend(messages)
            return True

        with patch.object(handlers.features, "db", db), \
                patch.object(handlers, "reply_to_line", side_effect=fake_reply), \
                patch.object(handlers, "is_rate_limited", return_value=False), \
                patch.object(handlers.broadcast, "track_user"), \
                patch.object(handlers, "get_gemini_response", side_effect=AssertionError("Gemini fallback was called")), \
                patch("mtc_assistant.user_blacklist.check_user_banned", return_value=(False, "")):
            handlers.handle_message(FakeEvent("เปิดเพลง Shape of You"))

        self.assertEqual(1, len(replies))
        self.assertIn("รายละเอียด: เปิดเพลง Shape of You", replies[0].text)
        self.assertIn("กำหนดส่งวันไหน", replies[0].text)

    def test_session_read_failure_does_not_call_gemini_or_standard_routing(self):
        db = FailingDb(fail_get=True)
        db.store["users/test-user"] = {"user_id": "test-user", "active_class_id": "mtc13"}
        replies = []

        def fake_reply(_token, messages):
            replies.extend(messages)
            return True

        with patch.object(handlers.features, "db", db), \
                patch.object(handlers, "reply_to_line", side_effect=fake_reply), \
                patch.object(handlers, "is_rate_limited", return_value=False), \
                patch.object(handlers.broadcast, "track_user"), \
                patch.object(handlers, "get_gemini_response", side_effect=AssertionError("Gemini fallback was called")), \
                patch.object(handlers, "handle_standard_command", side_effect=AssertionError("Standard routing was called")), \
                patch("mtc_assistant.user_blacklist.check_user_banned", return_value=(False, "")):
            handlers.handle_message(FakeEvent("เปิดเพลง Shape of You"))

        self.assertEqual(1, len(replies))
        self.assertIn("อ่านสถานะไม่สำเร็จ", replies[0].text)

    def test_start_write_failure_returns_controlled_failure(self):
        db = FailingDb(fail_set=True)

        message, quick_reply = start_homework_session(
            "test-user",
            class_context=ClassContext("mtc13", "test-user"),
            db=db,
        )

        self.assertIsNone(quick_reply)
        self.assertIn("บันทึกสถานะไม่สำเร็จ", message.text)
        self.assertNotIn("users/test-user/sessions/homework_create", db.store)

    def test_subject_write_failure_returns_controlled_failure(self):
        db = FakeDb()
        start_homework_session("test-user", class_context=ClassContext("mtc13", "test-user"), db=db)
        failing_db = FailingDb(fail_set=True)
        failing_db.store = db.store

        reply = handle_homework_session("test-user", "ฟิสิกส์", db=failing_db)

        self.assertIn("บันทึกสถานะไม่สำเร็จ", reply.text)
        self.assertEqual("subject", failing_db.store["users/test-user/sessions/homework_create"]["step"])

    def test_cancel_delete_failure_returns_controlled_failure(self):
        db = FakeDb()
        start_homework_session("test-user", class_context=ClassContext("mtc13", "test-user"), db=db)
        failing_db = FailingDb(fail_delete=True)
        failing_db.store = db.store

        result = cancel_homework_session("test-user", db=failing_db)

        self.assertIn("ลบสถานะไม่สำเร็จ", result)


if __name__ == "__main__":
    unittest.main()
