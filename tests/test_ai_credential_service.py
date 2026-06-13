import unittest
from datetime import datetime, timedelta, timezone

from mtc_assistant.ai_credential_service import AICredentialService
from mtc_assistant.ai_credentials import CredentialCipher
from mtc_assistant.ai_model_gateway import AIRequest
from mtc_assistant.ai_provider_adapters import ProviderErrorType


class FakeSnapshot:
    def __init__(self, data=None, doc_id=""):
        self._data = data
        self.id = doc_id
        self.exists = data is not None

    def to_dict(self):
        return dict(self._data or {})


class FakeDoc:
    def __init__(self, db, path):
        self.db = db
        self.path = path
        self.id = path.split("/")[-1]

    def collection(self, name):
        return FakeCollection(self.db, f"{self.path}/{name}")

    def get(self, transaction=None):
        return FakeSnapshot(self.db.store.get(self.path), self.id)

    def set(self, data, merge=False):
        if merge:
            current = dict(self.db.store.get(self.path, {}))
            current.update(data)
            self.db.store[self.path] = current
        else:
            self.db.store[self.path] = dict(data)

    def delete(self):
        self.db.store.pop(self.path, None)


class FakeCollection:
    def __init__(self, db, path):
        self.db = db
        self.path = path

    def document(self, doc_id):
        return FakeDoc(self.db, f"{self.path}/{doc_id}")

    def stream(self):
        prefix = f"{self.path}/"
        for path, data in sorted(self.db.store.items()):
            suffix = path[len(prefix):] if path.startswith(prefix) else ""
            if suffix and "/" not in suffix:
                yield FakeSnapshot(data, suffix)

    def add(self, data):
        doc_id = f"auto-{len(self.db.store) + 1}"
        self.document(doc_id).set(data)
        return self.document(doc_id), None


class FakeDb:
    def __init__(self):
        self.store = {}

    def collection(self, name):
        return FakeCollection(self, name)


class AICredentialServiceTest(unittest.TestCase):
    def setUp(self):
        self.db = FakeDb()
        self.cipher = CredentialCipher({1: b"k" * 32}, current_version=1)
        self.service = AICredentialService(
            self.db,
            self.cipher,
            system_credentials={"openai": "system-secret"},
            now_provider=lambda: datetime(2026, 6, 12, tzinfo=timezone.utc),
        )

    def test_save_persists_ciphertext_and_returns_public_metadata_only(self):
        public = self.service.save_class_credential(
            "mtc13",
            "openai",
            "sk-class-secret",
            model="gpt-4.1-mini",
            actor_id="admin-a",
        )

        stored = self.db.store["classes/mtc13/ai_credentials/openai"]
        self.assertNotIn("sk-class-secret", str(stored))
        self.assertNotIn("ciphertext", public)
        self.assertEqual("••••cret", public["masked_key"])
        self.assertEqual("active", public["status"])

    def test_resolver_returns_class_then_system_credentials(self):
        self.service.save_class_credential(
            "mtc13",
            "openai",
            "sk-class-secret",
            model="gpt-4.1-mini",
            actor_id="admin-a",
        )

        candidates = self.service.resolve_candidates(
            AIRequest("hello", "general_chat", "mtc13", "user-a"),
            "openai",
        )

        self.assertEqual(["class", "system"], [item.source for item in candidates])
        self.assertEqual("sk-class-secret", candidates[0].api_key)
        self.assertEqual("system-secret", candidates[1].api_key)

    def test_failure_marks_credential_and_applies_cooldown(self):
        self.service.save_class_credential(
            "mtc13",
            "openai",
            "sk-class-secret",
            model="gpt-4.1-mini",
            actor_id="admin-a",
        )

        self.service.mark_failure("mtc13", "openai", ProviderErrorType.AUTHENTICATION)

        stored = self.db.store["classes/mtc13/ai_credentials/openai"]
        self.assertEqual("invalid", stored["status"])
        self.assertEqual("authentication", stored["last_error_type"])
        self.assertGreater(
            datetime.fromisoformat(stored["cooldown_until"]),
            datetime(2026, 6, 12, tzinfo=timezone.utc),
        )
        self.assertTrue(any(
            path.startswith("classes/mtc13/admin_notifications/")
            for path in self.db.store
        ))
        self.assertTrue(any(
            path.startswith("system_ai_alerts/")
            for path in self.db.store
        ))

    def test_disabled_or_cooling_credential_is_skipped(self):
        self.service.save_class_credential(
            "mtc13",
            "openai",
            "sk-class-secret",
            model="gpt-4.1-mini",
            actor_id="admin-a",
        )
        self.db.store["classes/mtc13/ai_credentials/openai"].update({
            "status": "invalid",
            "cooldown_until": (
                datetime(2026, 6, 12, tzinfo=timezone.utc) + timedelta(hours=1)
            ).isoformat(),
        })

        candidates = self.service.resolve_candidates(
            AIRequest("hello", "general_chat", "mtc13", "user-a"),
            "openai",
        )

        self.assertEqual(["system"], [item.source for item in candidates])
        self.assertTrue(candidates[0].requires_fallback_policy)
        self.assertEqual("class_unavailable", candidates[0].fallback_reason)

    def test_delete_removes_class_credential(self):
        self.service.save_class_credential(
            "mtc13",
            "openai",
            "sk-class-secret",
            model="gpt-4.1-mini",
            actor_id="admin-a",
        )

        self.assertTrue(self.service.delete_class_credential("mtc13", "openai"))
        self.assertNotIn("classes/mtc13/ai_credentials/openai", self.db.store)

    def test_disable_prevents_class_credential_resolution(self):
        self.service.save_class_credential(
            "mtc13",
            "openai",
            "sk-class-secret",
            model="gpt-4.1-mini",
            actor_id="admin-a",
        )

        public = self.service.disable_class_credential(
            "mtc13",
            "openai",
            actor_id="admin-a",
        )
        candidates = self.service.resolve_candidates(
            AIRequest("hello", "general_chat", "mtc13", "user-a"),
            "openai",
        )

        self.assertEqual("disabled", public["status"])
        self.assertEqual(["system"], [item.source for item in candidates])

    def test_mark_used_updates_only_persisted_class_credential(self):
        self.service.save_class_credential(
            "mtc13",
            "openai",
            "sk-class-secret",
            model="gpt-4.1-mini",
            actor_id="admin-a",
        )

        self.service.mark_used("mtc13", "openai")

        stored = self.db.store["classes/mtc13/ai_credentials/openai"]
        self.assertEqual("2026-06-12T00:00:00+00:00", stored["last_used_at"])


if __name__ == "__main__":
    unittest.main()
