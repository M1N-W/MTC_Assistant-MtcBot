import unittest

from mtc_assistant.command_router import handle_standard_command
from mtc_assistant.homework_session import (
    cancel_homework_session,
    handle_homework_session,
    has_homework_session,
    start_homework_session,
)


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


if __name__ == "__main__":
    unittest.main()
