import unittest

from mtc_assistant import rate_limit


class RateLimitTest(unittest.TestCase):
    def setUp(self):
        with rate_limit._rate_limit_lock:
            rate_limit._user_message_history.clear()
            rate_limit._banned_users.clear()

    def tearDown(self):
        with rate_limit._rate_limit_lock:
            rate_limit._user_message_history.clear()
            rate_limit._banned_users.clear()

    def test_first_message_is_tracked(self):
        self.assertFalse(rate_limit.is_rate_limited("user-a"))

        with rate_limit._rate_limit_lock:
            self.assertEqual(1, len(rate_limit._user_message_history["user-a"]))

    def test_user_is_limited_after_threshold(self):
        for _ in range(rate_limit.RATE_LIMIT_MAX):
            self.assertFalse(rate_limit.is_rate_limited("user-a"))

        self.assertTrue(rate_limit.is_rate_limited("user-a"))

    def test_severe_abuse_bans_user(self):
        for _ in range(rate_limit.RATE_LIMIT_MAX * 3 + 1):
            rate_limit.is_rate_limited("user-a")

        self.assertTrue(rate_limit.is_rate_limited("user-a"))
        with rate_limit._rate_limit_lock:
            self.assertIn("user-a", rate_limit._banned_users)


if __name__ == "__main__":
    unittest.main()
