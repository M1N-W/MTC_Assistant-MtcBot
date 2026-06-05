import unittest
from unittest.mock import patch

from linebot.v3.messaging import FlexMessage

import mtc_assistant.handlers as handlers


class FakeDocSnapshot:
    exists = False

    def to_dict(self):
        return {}


class FakeDocRef:
    def get(self):
        return FakeDocSnapshot()


class FakeCollection:
    def document(self, _doc_id):
        return FakeDocRef()


class FakeDb:
    def collection(self, _name):
        return FakeCollection()


class FakeMessage:
    def __init__(self, text):
        self.text = text


class FakeSource:
    user_id = "user-a"


class FakeEvent:
    def __init__(self, text):
        self.message = FakeMessage(text)
        self.source = FakeSource()
        self.reply_token = "reply-token"


class InviteOnboardingHandlerTest(unittest.TestCase):
    def _run_message(self, text):
        replies = []

        def fake_reply(_token, messages):
            replies.extend(messages)
            return True

        with patch.object(handlers.features, "db", FakeDb()), \
                patch.object(handlers, "reply_to_line", side_effect=fake_reply), \
                patch.object(handlers, "is_rate_limited", return_value=False), \
                patch("mtc_assistant.user_blacklist.check_user_banned", return_value=(False, "")):
            handlers.handle_message(FakeEvent(text))

        return replies

    def test_unknown_user_can_use_help_before_joining(self):
        replies = self._run_message("help")

        self.assertEqual(1, len(replies))
        self.assertIsInstance(replies[0], FlexMessage)
        self.assertEqual("คำสั่งที่ใช้ได้ของ MTC Assistant", replies[0].alt_text)

    def test_unknown_user_is_blocked_from_class_specific_commands(self):
        replies = self._run_message("ตารางเรียน")

        self.assertEqual(1, len(replies))
        self.assertIn("JOIN <code>", replies[0].text)

    def test_join_command_log_redacts_code(self):
        with self.assertLogs("mtc_assistant", level="INFO") as logs:
            self._run_message("JOIN SECRET123")

        joined_logs = "\n".join(logs.output)
        self.assertNotIn("SECRET123", joined_logs)
        self.assertIn("[join command redacted]", joined_logs)


if __name__ == "__main__":
    unittest.main()
