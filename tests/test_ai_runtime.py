import os
import unittest
from unittest.mock import patch

from mtc_assistant.ai_provider_adapters import (
    AIProviderError,
    AIProviderResult,
    ProviderErrorType,
)
from mtc_assistant.ai_runtime import generate_ai_response


class _Snapshot:
    def __init__(self, data=None):
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return dict(self._data or {})


class _Document:
    def __init__(self, data):
        self.data = data

    def collection(self, _name):
        return self

    def document(self, _name):
        return self

    def get(self):
        return _Snapshot(self.data)


class _Db:
    def __init__(self, settings):
        self.settings = settings

    def collection(self, _name):
        return _Document(self.settings)


class _Gateway:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def generate(self, request, *, provider_id, model):
        self.calls.append((request, provider_id, model))
        if self.error:
            raise self.error
        return self.result


class AIRuntimeTest(unittest.TestCase):
    def test_uses_legacy_responder_when_byok_is_disabled(self):
        legacy = lambda prompt: f"legacy:{prompt}"
        with patch.dict(os.environ, {"ALLOW_CLASS_BYOK": "false"}, clear=False):
            result = generate_ai_response(
                "hello",
                class_id="mtc13",
                user_id="u1",
                db=_Db({"selected_provider": "openai", "selected_model": "gpt-4.1-mini"}),
                legacy_responder=legacy,
            )
        self.assertEqual(result, "legacy:hello")

    def test_routes_configured_class_request_through_gateway(self):
        gateway = _Gateway(AIProviderResult("gateway answer", 4, 8))
        with patch.dict(os.environ, {"ALLOW_CLASS_BYOK": "true"}, clear=False):
            result = generate_ai_response(
                "hello",
                class_id="mtc13",
                user_id="u1",
                db=_Db({"selected_provider": "openai", "selected_model": "gpt-4.1-mini"}),
                legacy_responder=lambda prompt: f"legacy:{prompt}",
                gateway_factory=lambda _db: gateway,
            )
        self.assertEqual(result, "gateway answer")
        request, provider_id, model = gateway.calls[0]
        self.assertEqual(request.class_id, "mtc13")
        self.assertEqual(provider_id, "openai")
        self.assertEqual(model, "gpt-4.1-mini")

    def test_returns_safe_message_for_provider_failure(self):
        gateway = _Gateway(error=AIProviderError(
            ProviderErrorType.AUTHENTICATION,
            "secret provider detail",
        ))
        with patch.dict(os.environ, {"ALLOW_CLASS_BYOK": "true"}, clear=False):
            result = generate_ai_response(
                "hello",
                class_id="mtc13",
                user_id=None,
                db=_Db({"selected_provider": "openai", "selected_model": "gpt-4.1-mini"}),
                legacy_responder=lambda prompt: f"legacy:{prompt}",
                gateway_factory=lambda _db: gateway,
            )
        self.assertNotIn("secret provider detail", result)
        self.assertIn("AI", result)


if __name__ == "__main__":
    unittest.main()
