import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from mtc_assistant.ai_fallback_policy import (
    FirestoreFallbackPolicy,
    _add_tokens_transaction,
    _reserve_request_transaction,
)
from tests.test_ai_credential_service import FakeDb


def reserve_runner(_db, ref, request_budget, token_budget, now_iso):
    snapshot = ref.get()
    data = snapshot.to_dict() if snapshot.exists else {}
    request_count = int(data.get("request_count", 0) or 0)
    token_count = int(data.get("token_count", 0) or 0)
    if request_count >= request_budget or token_count >= token_budget:
        return False
    ref.set({
        "request_count": request_count + 1,
        "token_count": token_count,
        "updated_at": now_iso,
    }, merge=True)
    return True


def token_runner(_db, ref, token_delta, now_iso):
    snapshot = ref.get()
    data = snapshot.to_dict() if snapshot.exists else {}
    ref.set({
        "request_count": int(data.get("request_count", 0) or 0),
        "token_count": int(data.get("token_count", 0) or 0) + token_delta,
        "updated_at": now_iso,
    }, merge=True)


class FakeTransaction:
    def set(self, ref, data, merge=False):
        ref.set(data, merge=merge)


class FakeTransactionDb:
    def transaction(self):
        return FakeTransaction()


class AIFallbackPolicyTest(unittest.TestCase):
    def setUp(self):
        self.db = FakeDb()
        self.policy = FirestoreFallbackPolicy(
            self.db,
            default_request_budget=2,
            default_token_budget=10,
            now_provider=lambda: datetime(2026, 6, 12, tzinfo=timezone.utc),
            reserve_runner=reserve_runner,
            token_runner=token_runner,
        )

    def test_reserves_fallback_request_below_daily_budgets(self):
        self.assertTrue(self.policy.reserve_system_fallback("mtc13"))
        counter = self.db.store["classes/mtc13/ai_fallback_usage/2026-06-12"]
        self.assertEqual(1, counter["request_count"])

    def test_record_fallback_updates_bounded_counter_and_audit(self):
        self.assertTrue(self.policy.reserve_system_fallback("mtc13"))
        self.policy.record_fallback(
            class_id="mtc13",
            provider_id="openai",
            reason="authentication",
            selected_fallback="system",
            input_tokens=3,
            output_tokens=2,
        )

        counter = self.db.store["classes/mtc13/ai_fallback_usage/2026-06-12"]
        self.assertEqual(1, counter["request_count"])
        self.assertEqual(5, counter["token_count"])
        audit_paths = [
            path for path in self.db.store
            if path.startswith("classes/mtc13/ai_audit/")
        ]
        self.assertEqual(1, len(audit_paths))
        self.assertNotIn("prompt", self.db.store[audit_paths[0]])

    def test_blocks_when_request_or_token_budget_is_reached(self):
        self.db.store["classes/mtc13/ai_fallback_usage/2026-06-12"] = {
            "request_count": 2,
            "token_count": 5,
        }
        self.assertFalse(self.policy.reserve_system_fallback("mtc13"))

        self.db.store["classes/mtc13/ai_fallback_usage/2026-06-12"] = {
            "request_count": 1,
            "token_count": 10,
        }
        self.assertFalse(self.policy.reserve_system_fallback("mtc13"))

    def test_production_transaction_helpers_compare_and_update_atomically(self):
        ref = self.db.collection("classes").document("mtc13")
        transaction_db = FakeTransactionDb()
        with patch(
            "mtc_assistant.ai_fallback_policy.firestore.transactional",
            side_effect=lambda function: function,
        ):
            reserved = _reserve_request_transaction(
                transaction_db,
                ref,
                request_budget=2,
                token_budget=10,
                now_iso="2026-06-12T00:00:00+00:00",
            )
            _add_tokens_transaction(
                transaction_db,
                ref,
                token_delta=4,
                now_iso="2026-06-12T00:00:01+00:00",
            )

        self.assertTrue(reserved)
        self.assertEqual(1, self.db.store["classes/mtc13"]["request_count"])
        self.assertEqual(4, self.db.store["classes/mtc13"]["token_count"])


if __name__ == "__main__":
    unittest.main()
