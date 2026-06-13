import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from mtc_assistant.ai_entry_router import AIEntryKind, classify_ai_entry


class AIEntryRouterTest(unittest.TestCase):
    def test_explicit_prefixes_strip_the_prompt(self):
        cases = {
            "ai อธิบายลำดับเลขคณิต": "อธิบายลำดับเลขคณิต",
            "AI: อธิบายลำดับเลขคณิต": "อธิบายลำดับเลขคณิต",
            "เอไอ อธิบายลำดับเลขคณิต": "อธิบายลำดับเลขคณิต",
            "ถามAI อธิบายลำดับเลขคณิต": "อธิบายลำดับเลขคณิต",
            "ถาม AI อธิบายลำดับเลขคณิต": "อธิบายลำดับเลขคณิต",
            "ถาม ai อธิบายลำดับเลขคณิต": "อธิบายลำดับเลขคณิต",
            "ถาม เอไอ อธิบายลำดับเลขคณิต": "อธิบายลำดับเลขคณิต",
        }

        for text, expected_prompt in cases.items():
            with self.subTest(text=text):
                decision = classify_ai_entry(text)
                self.assertEqual(AIEntryKind.EXPLICIT_AI, decision.kind)
                self.assertEqual(expected_prompt, decision.prompt)

    def test_prefix_requires_a_boundary(self):
        self.assertEqual(AIEntryKind.UNKNOWN, classify_ai_entry("airdrop").kind)

    def test_empty_and_overlong_explicit_prompts_return_guidance(self):
        for text in ("ai", "ถามAI", "เอไอ"):
            with self.subTest(text=text):
                self.assertEqual(AIEntryKind.EMPTY_AI, classify_ai_entry(text).kind)

        decision = classify_ai_entry("ai " + ("ก" * 1001))
        self.assertEqual(AIEntryKind.EMPTY_AI, decision.kind)
        self.assertIn("1,000", decision.response_text)

    def test_date_utilities_use_bangkok_date(self):
        now = datetime(2026, 6, 12, 7, 30, tzinfo=ZoneInfo("Asia/Bangkok"))

        today = classify_ai_entry("วันนี้เป็นวันอะไร?", now=now)
        tomorrow = classify_ai_entry("พรุ่งนี้วันที่เท่าไหร่", now=now)

        self.assertEqual(AIEntryKind.DATE_UTILITY, today.kind)
        self.assertEqual("วันนี้คือวันศุกร์ที่ 12 มิถุนายน 2026", today.response_text)
        self.assertEqual(AIEntryKind.DATE_UTILITY, tomorrow.kind)
        self.assertEqual("พรุ่งนี้คือวันเสาร์ที่ 13 มิถุนายน 2026", tomorrow.response_text)

    def test_classroom_questions_bridge_to_existing_commands(self):
        cases = {
            "วันจันทร์ส่งอะไรบ้าง": "การบ้าน",
            "พรุ่งนี้เรียนอะไร": "ตารางเรียน",
            "สอบกลางภาควันไหน": "ปฏิทินกิจกรรม",
        }

        for text, command in cases.items():
            with self.subTest(text=text):
                decision = classify_ai_entry(text)
                self.assertEqual(AIEntryKind.CLASSROOM_BRIDGE, decision.kind)
                self.assertIn(command, decision.response_text)

    def test_explicit_prefix_cannot_bypass_deterministic_or_classroom_routing(self):
        cases = {
            "ai พรุ่งนี้เรียนอะไร": (AIEntryKind.CLASSROOM_BRIDGE, "ตารางเรียน"),
            "เอไอ วันจันทร์ส่งไรบ้าง": (AIEntryKind.CLASSROOM_BRIDGE, "การบ้าน"),
            "ถามAI วันนี้เป็นวันอะไร": (AIEntryKind.DATE_UTILITY, "วันนี้คือ"),
        }

        for text, (expected_kind, expected_text) in cases.items():
            with self.subTest(text=text):
                decision = classify_ai_entry(
                    text,
                    now=datetime(2026, 6, 12, 7, 30, tzinfo=ZoneInfo("Asia/Bangkok")),
                )
                self.assertEqual(expected_kind, decision.kind)
                self.assertIn(expected_text, decision.response_text)

    def test_allowlisted_learning_questions_enter_ai(self):
        for text in (
            "ทำไมท้องฟ้าถึงเป็นสีฟ้า",
            "อธิบายลำดับเลขคณิตหน่อย",
            "ช่วยสรุปเรื่องเมทริกซ์หน่อย",
            "แรงเสียดทานคืออะไร",
        ):
            with self.subTest(text=text):
                decision = classify_ai_entry(text)
                self.assertEqual(AIEntryKind.NATURAL_AI, decision.kind)
                self.assertEqual(text, decision.prompt)

    def test_ambiguous_and_gibberish_messages_stay_unknown(self):
        for text in ("?", "555", "อืม", "asdfasdf", "งานน", "ลิง", "ไรอะ"):
            with self.subTest(text=text):
                self.assertEqual(AIEntryKind.UNKNOWN, classify_ai_entry(text).kind)


if __name__ == "__main__":
    unittest.main()
