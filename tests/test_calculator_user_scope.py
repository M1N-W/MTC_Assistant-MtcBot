import unittest

from mtc_assistant.features import get_calculator_response
from mtc_assistant.smart_calc import clear_vars


class CalculatorUserScopeTest(unittest.TestCase):
    def tearDown(self):
        clear_vars("user-a")
        clear_vars("user-b")

    def test_variables_are_scoped_by_user_id(self):
        self.assertEqual("x = 5", get_calculator_response("คำนวณ x = 5", "user-a").text)

        user_a_reply = get_calculator_response("คำนวณ x * 2", "user-a")
        user_b_reply = get_calculator_response("คำนวณ x * 2", "user-b")

        self.assertIn("10", user_a_reply.text)
        self.assertIn("ตัวแปรไม่อนุญาต: x", user_b_reply.text)


if __name__ == "__main__":
    unittest.main()
