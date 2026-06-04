import unittest
from unittest.mock import patch


BANNED_ADMIN_TERMS = (
    "สวมรอย",
    "ไร้ร่องรอย",
    "บอส",
    "เป้าหมาย",
    "สายลับ",
    "ภารกิจ",
    "TOP SECRET",
    "😈",
    "🤫",
)

VALID_USER_ID = "U" + ("a" * 32)
VALID_ADMIN_ID = "U" + ("b" * 32)


def assert_no_banned_terms(test_case, text):
    for term in BANNED_ADMIN_TERMS:
        test_case.assertNotIn(term, text)


class FakeLineApi:
    def __init__(self):
        self.requests = []

    def push_message(self, request):
        self.requests.append(request)


class FakeBlacklistManager:
    def __init__(self, banned=None, ban_success=True, unban_success=True):
        self.banned = banned or {}
        self.ban_success = ban_success
        self.unban_success = unban_success

    def ban_user(self, user_id, admin_id, reason):
        return self.ban_success

    def unban_user(self, user_id):
        return self.unban_success

    def get_all_banned(self):
        return self.banned

    def get_stats(self):
        return "รายงานสถิติการระงับผู้ใช้\n\nTotal banned: 0"


class AdminReplyWordingTest(unittest.TestCase):
    def test_impersonate_admin_outputs_do_not_use_unsafe_terms(self):
        import mtc_assistant.admin_impersonate as impersonate

        with impersonate._cache_lock:
            impersonate._recent_users_cache.clear()

        fake_line_api = FakeLineApi()
        with patch.object(impersonate, "_line_api", fake_line_api):
            success, result = impersonate.send_impersonate_message(
                VALID_USER_ID,
                "test message",
                max_retries=1,
            )

        self.assertTrue(success)
        self.assertEqual(1, len(fake_line_api.requests))

        with patch.object(
            impersonate,
            "send_impersonate_message",
            return_value=(
                True,
                "✅ ส่งข้อความจากบอทสำเร็จ\n\nผู้ใช้: Uaaaaaaa...\nสถานะ: บันทึกผลการส่งแล้ว",
            ),
        ):
            send_reply = impersonate.handle_send_impersonate_command(
                VALID_ADMIN_ID,
                f"ส่งถึง {VALID_USER_ID} hello",
            )
            test_reply = impersonate.handle_test_impersonate_command(
                VALID_ADMIN_ID,
                "ทดสอบส่ง สวัสดี",
            )

        outputs = [
            result,
            impersonate.handle_list_users_command(VALID_ADMIN_ID),
            impersonate.handle_send_impersonate_command(VALID_ADMIN_ID, "ส่งถึง invalid สวัสดี"),
            impersonate.get_impersonate_help(),
            send_reply,
            test_reply,
        ]

        for output in outputs:
            assert_no_banned_terms(self, output)

    def test_broadcast_admin_outputs_do_not_use_unsafe_terms(self):
        import mtc_assistant.broadcast as broadcast

        with patch.object(broadcast, "line_api", object()), \
             patch.object(broadcast, "get_all_users", return_value=[VALID_USER_ID, VALID_ADMIN_ID]), \
             patch.object(broadcast, "_push_with_retry", side_effect=[True, False]):
            result = broadcast.broadcast_message("ประกาศทดสอบ")

        with patch.object(broadcast, "db", None):
            unavailable_stats = broadcast.get_broadcast_stats()

        outputs = [
            result["message"],
            unavailable_stats,
        ]

        for output in outputs:
            assert_no_banned_terms(self, output)

    def test_blacklist_admin_outputs_do_not_use_unsafe_terms(self):
        import mtc_assistant.user_blacklist as user_blacklist

        with patch.object(
            user_blacklist,
            "get_blacklist_manager",
            return_value=FakeBlacklistManager(),
        ):
            outputs = [
                user_blacklist.handle_ban_user_command(VALID_ADMIN_ID, "แบน"),
                user_blacklist.handle_ban_user_command(VALID_ADMIN_ID, f"แบน {VALID_USER_ID} spam"),
                user_blacklist.handle_unban_user_command(VALID_ADMIN_ID, "ปลดแบน"),
                user_blacklist.handle_unban_user_command(VALID_ADMIN_ID, f"ปลดแบน {VALID_USER_ID}"),
                user_blacklist.handle_list_banned_command(VALID_ADMIN_ID),
                user_blacklist.handle_ban_stats_command(VALID_ADMIN_ID),
            ]

        with patch.object(
            user_blacklist,
            "get_blacklist_manager",
            return_value=FakeBlacklistManager(unban_success=False),
        ):
            outputs.append(user_blacklist.handle_unban_user_command(VALID_ADMIN_ID, f"ปลดแบน {VALID_USER_ID}"))

        for output in outputs:
            assert_no_banned_terms(self, output)


if __name__ == "__main__":
    unittest.main()
