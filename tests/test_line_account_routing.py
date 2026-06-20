import unittest
from unittest.mock import patch

from linebot.v3.messaging import TextMessage


class LineAccountRoutingTest(unittest.TestCase):
    def test_account_command_is_handled_before_ai_gateway(self):
        from mtc_assistant import handlers

        with patch("mtc_assistant.handlers.build_account_message", return_value=TextMessage(text="account")) as account, \
                patch("mtc_assistant.handlers.generate_ai_response", side_effect=AssertionError("AI called")):
            reply = handlers.handle_account_identity_or_class_command(
                db=None,
                user_id="user-a",
                user_message="บัญชี",
                line_api=None,
            )

        self.assertEqual("account", reply.text)
        account.assert_called_once()

    def test_mtc67_near_matches_still_do_not_trigger_video(self):
        from mtc_assistant.command_router import handle_standard_command

        self.assertIsNone(handle_standard_command("abc67", "abc67"))
        self.assertIsNone(handle_standard_command("67 test", "67 test"))


if __name__ == "__main__":
    unittest.main()
