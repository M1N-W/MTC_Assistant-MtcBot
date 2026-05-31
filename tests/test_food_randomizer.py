import unittest
from unittest.mock import patch

from mtc_assistant.food_randomizer import handle_food_randomizer_command


class FoodRandomizerTest(unittest.TestCase):
    def test_food_randomizer_returns_text_message(self):
        with patch("mtc_assistant.food_randomizer.random.choice", return_value="ข้าวผัด"):
            reply = handle_food_randomizer_command("กินอะไรดี")

        self.assertEqual("วันนี้ลองกิน ข้าวผัด ดีไหมครับ", reply.text)


if __name__ == "__main__":
    unittest.main()
