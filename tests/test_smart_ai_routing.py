import unittest
from unittest.mock import patch

from linebot.v3.messaging import TextMessage

import mtc_assistant.handlers as handlers
from tests.test_homework_session_routing import FakeDb, FakeEvent


class SmartAIRoutingHandlerTest(unittest.TestCase):
    def _run_message(self, text, ai_response="AI response"):
        db = FakeDb()
        db.store["users/test-user"] = {
            "user_id": "test-user",
            "active_class_id": "mtc13",
        }
        replies = []

        def fake_reply(_token, messages):
            replies.extend(messages)
            return True

        with patch.object(handlers.features, "db", db), \
                patch.object(handlers, "reply_to_line", side_effect=fake_reply), \
                patch.object(handlers, "is_rate_limited", return_value=False), \
                patch.object(handlers.broadcast, "track_user"), \
                patch.object(handlers, "get_gemini_response", return_value=ai_response) as ai_call, \
                patch("mtc_assistant.user_blacklist.check_user_banned", return_value=(False, "")):
            handlers.handle_message(FakeEvent(text))

        return replies, ai_call

    def test_explicit_ai_prefix_calls_existing_ai_path(self):
        replies, ai_call = self._run_message("ถาม AI อธิบายลำดับเลขคณิต")

        ai_call.assert_called_once_with("อธิบายลำดับเลขคณิต")
        self.assertEqual("AI response", replies[0].text)

    def test_empty_ai_prefix_returns_guidance_without_ai(self):
        replies, ai_call = self._run_message("ai")

        ai_call.assert_not_called()
        self.assertIn("อยากถาม AI เรื่องอะไร", replies[0].text)

    def test_natural_learning_question_calls_ai(self):
        replies, ai_call = self._run_message("อธิบายลำดับเลขคณิตหน่อย")

        ai_call.assert_called_once_with("อธิบายลำดับเลขคณิตหน่อย")
        self.assertEqual("AI response", replies[0].text)

    def test_unknown_message_returns_quick_reply_without_ai(self):
        replies, ai_call = self._run_message("asdfasdf")

        ai_call.assert_not_called()
        self.assertIsInstance(replies[0], TextMessage)
        self.assertIn("ยังไม่เจอคำสั่งนี้", replies[0].text)
        actions = {
            item.action.label: item.action.text
            for item in replies[0].quick_reply.items
        }
        self.assertEqual({
            "ถาม AI": "ai",
            "ดูคำสั่ง": "ช่วยเหลือ",
            "การบ้าน": "การบ้าน",
            "ตารางเรียน": "ตารางเรียน",
        }, actions)

    def test_classroom_question_does_not_call_ai(self):
        replies, ai_call = self._run_message("วันจันทร์ส่งอะไรบ้าง")

        ai_call.assert_not_called()
        self.assertIn("การบ้าน", replies[0].text)

    def test_explicit_classroom_question_does_not_call_ai(self):
        replies, ai_call = self._run_message("ai พรุ่งนี้เรียนอะไร")

        ai_call.assert_not_called()
        self.assertIn("ตารางเรียน", replies[0].text)


if __name__ == "__main__":
    unittest.main()
