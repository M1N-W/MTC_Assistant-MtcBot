import unittest

from mtc_assistant.ai_credentials import ResolvedCredential
from mtc_assistant.ai_model_gateway import AIModelGateway, AIRequest
from mtc_assistant.ai_provider_adapters import (
    AIProviderError,
    AIProviderResult,
    ProviderErrorType,
)


class FakeCredentialResolver:
    def __init__(self, credentials):
        self.credentials = list(credentials)
        self.calls = []
        self.failures = []
        self.used = []

    def resolve_candidates(self, request, provider_id):
        self.calls.append((request, provider_id))
        return list(self.credentials)

    def mark_failure(self, class_id, provider_id, error_type):
        self.failures.append((class_id, provider_id, error_type))

    def mark_used(self, class_id, provider_id):
        self.used.append((class_id, provider_id))


class FakeAdapter:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def generate(self, api_key, model, prompt):
        self.calls.append((api_key, model, prompt))
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FakeFallbackPolicy:
    def __init__(self, allowed=True):
        self.allowed = allowed
        self.events = []
        self.reserve_calls = []

    def reserve_system_fallback(self, class_id):
        self.reserve_calls.append(class_id)
        return self.allowed

    def record_fallback(self, **event):
        self.events.append(event)


class AIModelGatewayTest(unittest.TestCase):
    def test_uses_class_credential_before_system(self):
        credentials = [
            ResolvedCredential("class", "class-key"),
            ResolvedCredential(
                "system",
                "system-key",
                requires_fallback_policy=True,
                fallback_reason="class_unavailable",
            ),
        ]
        adapter = FakeAdapter([AIProviderResult("answer", 2, 1)])
        gateway = AIModelGateway(
            credential_resolver=FakeCredentialResolver(credentials),
            adapters={"openai": adapter},
            fallback_policy=FakeFallbackPolicy(),
        )

        result = gateway.generate(
            AIRequest("hello", "general_chat", "mtc13", "user-a"),
            provider_id="openai",
            model="gpt-4.1-mini",
        )

        self.assertEqual("answer", result.text)
        self.assertEqual("class-key", adapter.calls[0][0])
        self.assertEqual([("mtc13", "openai")], gateway.credential_resolver.used)

    def test_class_failure_automatically_falls_back_to_system_and_records_event(self):
        credentials = [
            ResolvedCredential("class", "class-key"),
            ResolvedCredential(
                "system",
                "system-key",
                requires_fallback_policy=True,
                fallback_reason="class_unavailable",
            ),
        ]
        adapter = FakeAdapter([
            AIProviderError(ProviderErrorType.AUTHENTICATION, "Authentication failed"),
            AIProviderResult("system answer", 3, 2),
        ])
        policy = FakeFallbackPolicy()
        gateway = AIModelGateway(
            credential_resolver=FakeCredentialResolver(credentials),
            adapters={"openai": adapter},
            fallback_policy=policy,
        )

        result = gateway.generate(
            AIRequest("hello", "general_chat", "mtc13", "user-a"),
            provider_id="openai",
            model="gpt-4.1-mini",
        )

        self.assertEqual("system answer", result.text)
        self.assertEqual("system-key", adapter.calls[1][0])
        self.assertEqual("authentication", policy.events[0]["reason"])
        self.assertEqual(
            ("mtc13", "openai", ProviderErrorType.AUTHENTICATION),
            gateway.credential_resolver.failures[0],
        )
        self.assertEqual(["mtc13"], policy.reserve_calls)

    def test_budget_guard_can_block_system_fallback(self):
        credentials = [
            ResolvedCredential("class", "class-key"),
            ResolvedCredential(
                "system",
                "system-key",
                requires_fallback_policy=True,
                fallback_reason="class_unavailable",
            ),
        ]
        adapter = FakeAdapter([
            AIProviderError(ProviderErrorType.QUOTA, "Quota limited"),
        ])
        gateway = AIModelGateway(
            credential_resolver=FakeCredentialResolver(credentials),
            adapters={"openai": adapter},
            fallback_policy=FakeFallbackPolicy(allowed=False),
        )

        with self.assertRaises(AIProviderError) as raised:
            gateway.generate(
                AIRequest("hello", "general_chat", "mtc13", "user-a"),
                provider_id="openai",
                model="gpt-4.1-mini",
            )

        self.assertEqual(ProviderErrorType.QUOTA, raised.exception.error_type)
        self.assertEqual(1, len(adapter.calls))

    def test_system_only_candidate_still_requires_fallback_policy(self):
        credential = ResolvedCredential(
            "system",
            "system-key",
            requires_fallback_policy=True,
            fallback_reason="class_unavailable",
        )
        adapter = FakeAdapter([AIProviderResult("answer", 2, 1)])
        policy = FakeFallbackPolicy(allowed=False)
        gateway = AIModelGateway(
            credential_resolver=FakeCredentialResolver([credential]),
            adapters={"openai": adapter},
            fallback_policy=policy,
        )

        with self.assertRaises(AIProviderError):
            gateway.generate(
                AIRequest("hello", "general_chat", "mtc13", "user-a"),
                provider_id="openai",
                model="gpt-4.1-mini",
            )

        self.assertEqual(["mtc13"], policy.reserve_calls)
        self.assertEqual([], adapter.calls)

    def test_failed_class_provider_call_does_not_mark_credential_used(self):
        resolver = FakeCredentialResolver([
            ResolvedCredential("class", "class-key"),
        ])
        gateway = AIModelGateway(
            credential_resolver=resolver,
            adapters={"openai": FakeAdapter([
                AIProviderError(ProviderErrorType.TIMEOUT, "timeout"),
            ])},
            fallback_policy=FakeFallbackPolicy(),
        )

        with self.assertRaises(AIProviderError):
            gateway.generate(
                AIRequest("hello", "general_chat", "mtc13", "user-a"),
                provider_id="openai",
                model="gpt-4.1-mini",
            )

        self.assertEqual([], resolver.used)


if __name__ == "__main__":
    unittest.main()
