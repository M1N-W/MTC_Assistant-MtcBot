import unittest

from mtc_assistant.ai_provider_adapters import (
    AIProviderError,
    AnthropicAdapter,
    GeminiAdapter,
    OpenAIAdapter,
    ProviderErrorType,
)
from mtc_assistant.ai_provider_registry import get_provider_definition


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class RecordingTransport:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, url, *, headers, json, timeout):
        self.calls.append({
            "url": url,
            "headers": headers,
            "json": json,
            "timeout": timeout,
        })
        return self.response


class AIProviderAdapterTest(unittest.TestCase):
    def test_registry_rejects_unknown_provider_and_model(self):
        with self.assertRaises(ValueError):
            get_provider_definition("custom")

        definition = get_provider_definition("openai")
        with self.assertRaises(ValueError):
            definition.validate_model("user-controlled-model")

    def test_gemini_adapter_uses_fixed_endpoint_and_extracts_text(self):
        transport = RecordingTransport(FakeResponse(200, {
            "candidates": [{"content": {"parts": [{"text": "Gemini answer"}]}}],
            "usageMetadata": {"promptTokenCount": 4, "candidatesTokenCount": 2},
        }))

        result = GeminiAdapter(transport).generate(
            api_key="secret-key",
            model="gemini-2.5-flash",
            prompt="hello",
        )

        self.assertEqual("Gemini answer", result.text)
        self.assertNotIn("secret-key", transport.calls[0]["url"])
        self.assertEqual("secret-key", transport.calls[0]["headers"]["x-goog-api-key"])

    def test_openai_adapter_uses_responses_api(self):
        transport = RecordingTransport(FakeResponse(200, {
            "output": [{
                "type": "message",
                "content": [{"type": "output_text", "text": "OpenAI answer"}],
            }],
            "usage": {"input_tokens": 5, "output_tokens": 3},
        }))

        result = OpenAIAdapter(transport).generate(
            api_key="secret-key",
            model="gpt-4.1-mini",
            prompt="hello",
        )

        self.assertEqual("OpenAI answer", result.text)
        self.assertEqual("https://api.openai.com/v1/responses", transport.calls[0]["url"])
        self.assertEqual("Bearer secret-key", transport.calls[0]["headers"]["Authorization"])

    def test_anthropic_adapter_uses_messages_api(self):
        transport = RecordingTransport(FakeResponse(200, {
            "content": [{"type": "text", "text": "Claude answer"}],
            "usage": {"input_tokens": 6, "output_tokens": 4},
        }))

        result = AnthropicAdapter(transport).generate(
            api_key="secret-key",
            model="claude-haiku-4-5",
            prompt="hello",
        )

        self.assertEqual("Claude answer", result.text)
        self.assertEqual("https://api.anthropic.com/v1/messages", transport.calls[0]["url"])
        self.assertEqual("secret-key", transport.calls[0]["headers"]["x-api-key"])

    def test_provider_errors_are_normalized(self):
        cases = (
            (401, ProviderErrorType.AUTHENTICATION),
            (429, ProviderErrorType.QUOTA),
            (400, ProviderErrorType.INVALID_REQUEST),
            (500, ProviderErrorType.PROVIDER_SERVICE),
        )

        for status, expected_type in cases:
            with self.subTest(status=status):
                adapter = OpenAIAdapter(RecordingTransport(FakeResponse(status, {"error": {}})))
                with self.assertRaises(AIProviderError) as raised:
                    adapter.generate("secret-key", "gpt-4.1-mini", "hello")
                self.assertEqual(expected_type, raised.exception.error_type)
                self.assertNotIn("secret-key", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
