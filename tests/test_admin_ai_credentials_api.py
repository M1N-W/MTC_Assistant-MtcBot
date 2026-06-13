import unittest
from unittest.mock import patch

from flask import Flask

from mtc_assistant.admin_api import create_admin_api_blueprint
from tests.test_ai_credential_service import FakeDb


TOKEN = "test-dashboard-token"
BASE = "/api/admin/classes/mtc13/ai"


class FakeCredentialService:
    def __init__(self):
        self.saved = {}
        self.validations = []

    def list_class_credentials(self, class_id):
        return list(self.saved.values())

    def validate_credential(self, provider_id, api_key, model):
        self.validations.append((provider_id, api_key, model))
        return {"status": "valid", "provider_id": provider_id, "model": model}

    def save_class_credential(self, class_id, provider_id, api_key, *, model, actor_id):
        item = {
            "provider_id": provider_id,
            "display_name": provider_id.title(),
            "configured": True,
            "status": "active",
            "masked_key": f"••••{api_key[-4:]}",
            "model": model,
            "allowed_models": [model],
            "updated_at": "2026-06-12T00:00:00+00:00",
            "last_validated_at": "2026-06-12T00:00:00+00:00",
            "last_used_at": None,
            "last_error_type": None,
            "cooldown_until": None,
        }
        self.saved[provider_id] = item
        return item

    def delete_class_credential(self, class_id, provider_id):
        return self.saved.pop(provider_id, None) is not None

    def disable_class_credential(self, class_id, provider_id, *, actor_id):
        item = self.saved[provider_id]
        item = {**item, "status": "disabled"}
        self.saved[provider_id] = item
        return item


class AdminAICredentialsApiTest(unittest.TestCase):
    def setUp(self):
        self.db = FakeDb()
        self.service = FakeCredentialService()
        app = Flask(__name__)
        app.register_blueprint(create_admin_api_blueprint(
            get_db=lambda: self.db,
            get_metrics=lambda: {},
            get_services=lambda: {},
            get_ai_credential_service=lambda _db: self.service,
        ))
        self.client = app.test_client()
        self.token_patch = patch("mtc_assistant.admin_api.MTC_DASHBOARD_API_TOKEN", TOKEN)
        self.token_patch.start()

    def tearDown(self):
        self.token_patch.stop()

    def headers(self, role="class_admin", classes="mtc13"):
        return {
            "Authorization": f"Bearer {TOKEN}",
            "X-MTC-Admin-Id": "admin-a",
            "X-MTC-Admin-Role": role,
            "X-MTC-Admin-Classes": classes,
        }

    def test_missing_principal_claims_are_rejected(self):
        response = self.client.get(
            f"{BASE}/credentials",
            headers={"Authorization": f"Bearer {TOKEN}"},
        )

        self.assertEqual(403, response.status_code)
        self.assertEqual("ADMIN_PRINCIPAL_REQUIRED", response.get_json()["error"]["code"])

    def test_class_admin_cannot_manage_byok_even_for_assigned_class(self):
        response = self.client.get(
            f"{BASE}/credentials",
            headers=self.headers(classes="mtc13"),
        )

        self.assertEqual(403, response.status_code)
        self.assertEqual("SUPER_ADMIN_REQUIRED", response.get_json()["error"]["code"])

    def test_cross_class_claims_cannot_write_byok_credentials(self):
        response = self.client.put(
            f"{BASE}/credentials/openai",
            headers=self.headers(classes="mtc12"),
            json={"api_key": "sk-class-secret", "model": "gpt-4.1-mini"},
        )

        self.assertEqual(403, response.status_code)

    def test_super_admin_can_access_any_class(self):
        response = self.client.get(
            "/api/admin/classes/mtc12/ai/credentials",
            headers=self.headers(role="super_admin", classes=""),
        )

        self.assertEqual(200, response.status_code)

    def test_put_validates_then_saves_without_echoing_plaintext(self):
        response = self.client.put(
            f"{BASE}/credentials/openai",
            headers=self.headers(role="super_admin"),
            json={"api_key": "sk-class-secret", "model": "gpt-4.1-mini"},
        )

        payload = response.get_json()["data"]
        self.assertEqual(200, response.status_code)
        self.assertEqual(
            ("openai", "sk-class-secret", "gpt-4.1-mini"),
            self.service.validations[0],
        )
        self.assertNotIn("sk-class-secret", str(payload))
        self.assertEqual("••••cret", payload["masked_key"])

    def test_validate_does_not_persist_key(self):
        response = self.client.post(
            f"{BASE}/credentials/anthropic/validate",
            headers=self.headers(role="super_admin"),
            json={"api_key": "sk-ant-secret", "model": "claude-haiku-4-5"},
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual({}, self.service.saved)
        self.assertNotIn("sk-ant-secret", str(response.get_json()))

    def test_delete_removes_credential(self):
        self.service.save_class_credential(
            "mtc13",
            "gemini",
            "gemini-secret",
            model="gemini-2.5-flash",
            actor_id="admin-a",
        )

        response = self.client.delete(
            f"{BASE}/credentials/gemini",
            headers=self.headers(role="super_admin"),
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual({}, self.service.saved)

    def test_put_can_disable_without_resubmitting_plaintext(self):
        self.service.save_class_credential(
            "mtc13",
            "openai",
            "sk-class-secret",
            model="gpt-4.1-mini",
            actor_id="admin-a",
        )

        response = self.client.put(
            f"{BASE}/credentials/openai",
            headers=self.headers(role="super_admin"),
            json={"status": "disabled"},
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual("disabled", response.get_json()["data"]["status"])
        self.assertEqual([], self.service.validations)

    def test_feature_flag_can_disable_class_byok(self):
        with patch.dict("os.environ", {"ALLOW_CLASS_BYOK": "false"}):
            response = self.client.get(
                f"{BASE}/credentials",
                headers=self.headers(),
            )

        self.assertEqual(503, response.status_code)
        self.assertEqual("CLASS_BYOK_DISABLED", response.get_json()["error"]["code"])

    def test_patch_settings_validates_provider_model_and_budgets(self):
        response = self.client.patch(
            f"{BASE}/settings",
            headers=self.headers(role="super_admin"),
            json={
                "selected_provider": "openai",
                "selected_model": "gpt-4.1-mini",
                "system_fallback_enabled": True,
                "daily_fallback_request_budget": 25,
                "daily_fallback_token_budget": 40000,
            },
        )

        self.assertEqual(200, response.status_code)
        stored = self.db.store["classes/mtc13/config/ai"]
        self.assertEqual("openai", stored["selected_provider"])
        self.assertEqual(25, stored["daily_fallback_request_budget"])

        invalid = self.client.patch(
            f"{BASE}/settings",
            headers=self.headers(role="super_admin"),
            json={
                "selected_provider": "openai",
                "selected_model": "custom-model",
                "system_fallback_enabled": True,
                "daily_fallback_request_budget": 25,
                "daily_fallback_token_budget": 40000,
            },
        )
        self.assertEqual(422, invalid.status_code)


if __name__ == "__main__":
    unittest.main()
