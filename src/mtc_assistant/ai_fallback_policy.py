"""Bounded automatic fallback from class credentials to system credentials."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from firebase_admin import firestore


class FirestoreFallbackPolicy:
    def __init__(
        self,
        db,
        *,
        default_request_budget: int = 20,
        default_token_budget: int = 30000,
        now_provider: Callable[[], datetime] | None = None,
        reserve_runner=None,
        token_runner=None,
    ):
        self.db = db
        self.default_request_budget = max(0, default_request_budget)
        self.default_token_budget = max(0, default_token_budget)
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self.reserve_runner = reserve_runner or _reserve_request_transaction
        self.token_runner = token_runner or _add_tokens_transaction

    def reserve_system_fallback(self, class_id: str) -> bool:
        settings = self._settings(class_id)
        if not settings["system_fallback_enabled"]:
            return False
        return self.reserve_runner(
            self.db,
            self._counter_ref(class_id),
            settings["daily_request_budget"],
            settings["daily_token_budget"],
            self.now_provider().isoformat(),
        )

    def record_fallback(
        self,
        *,
        class_id: str,
        provider_id: str,
        reason: str,
        selected_fallback: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        now = self.now_provider()
        token_count = max(0, int(input_tokens or 0)) + max(0, int(output_tokens or 0))
        self.token_runner(
            self.db,
            self._counter_ref(class_id),
            token_count,
            now.isoformat(),
        )
        (
            self.db.collection("classes")
            .document(class_id)
            .collection("ai_audit")
            .add({
                "event_type": "system_fallback",
                "provider_id": provider_id,
                "reason": reason,
                "selected_fallback": selected_fallback,
                "input_tokens": max(0, int(input_tokens or 0)),
                "output_tokens": max(0, int(output_tokens or 0)),
                "created_at": now.isoformat(),
            })
        )

    def _settings(self, class_id: str) -> dict:
        snapshot = (
            self.db.collection("classes")
            .document(class_id)
            .collection("config")
            .document("ai")
            .get()
        )
        data = snapshot.to_dict() if getattr(snapshot, "exists", False) else {}
        return {
            "system_fallback_enabled": bool(data.get("system_fallback_enabled", True)),
            "daily_request_budget": _bounded_int(
                data.get("daily_fallback_request_budget"),
                self.default_request_budget,
                maximum=1000,
            ),
            "daily_token_budget": _bounded_int(
                data.get("daily_fallback_token_budget"),
                self.default_token_budget,
                maximum=10_000_000,
            ),
        }

    def _counter_ref(self, class_id: str):
        day = self.now_provider().date().isoformat()
        return (
            self.db.collection("classes")
            .document(class_id)
            .collection("ai_fallback_usage")
            .document(day)
        )


def _bounded_int(value, default: int, maximum: int) -> int:
    try:
        return max(0, min(int(value), maximum))
    except (TypeError, ValueError):
        return default


def _reserve_request_transaction(
    db,
    ref,
    request_budget: int,
    token_budget: int,
    now_iso: str,
) -> bool:
    transaction = db.transaction()

    @firestore.transactional
    def reserve(transaction):
        snapshot = ref.get(transaction=transaction)
        data = snapshot.to_dict() if getattr(snapshot, "exists", False) else {}
        request_count = int(data.get("request_count", 0) or 0)
        token_count = int(data.get("token_count", 0) or 0)
        if request_count >= request_budget or token_count >= token_budget:
            return False
        transaction.set(ref, {
            "request_count": request_count + 1,
            "token_count": token_count,
            "updated_at": now_iso,
        }, merge=True)
        return True

    return bool(reserve(transaction))


def _add_tokens_transaction(db, ref, token_delta: int, now_iso: str) -> None:
    transaction = db.transaction()

    @firestore.transactional
    def add_tokens(transaction):
        snapshot = ref.get(transaction=transaction)
        data = snapshot.to_dict() if getattr(snapshot, "exists", False) else {}
        transaction.set(ref, {
            "request_count": int(data.get("request_count", 0) or 0),
            "token_count": int(data.get("token_count", 0) or 0) + token_delta,
            "updated_at": now_iso,
        }, merge=True)

    add_tokens(transaction)
