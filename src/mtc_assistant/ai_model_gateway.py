"""Credential-aware server-side AI model gateway."""

from __future__ import annotations

from dataclasses import dataclass

from mtc_assistant.ai_provider_adapters import (
    AIProviderError,
    AIProviderResult,
    ProviderErrorType,
)
from mtc_assistant.ai_provider_registry import get_provider_definition


@dataclass(frozen=True)
class AIRequest:
    prompt: str
    task_type: str
    class_id: str
    user_id: str | None


class AIModelGateway:
    def __init__(self, credential_resolver, adapters: dict, fallback_policy):
        self.credential_resolver = credential_resolver
        self.adapters = adapters
        self.fallback_policy = fallback_policy

    def generate(
        self,
        request: AIRequest,
        *,
        provider_id: str,
        model: str,
    ) -> AIProviderResult:
        definition = get_provider_definition(provider_id)
        definition.validate_model(model)
        try:
            adapter = self.adapters[provider_id]
        except KeyError as exc:
            raise ValueError("AI provider adapter is unavailable") from exc

        credentials = self.credential_resolver.resolve_candidates(request, provider_id)
        if not credentials:
            raise AIProviderError(
                ProviderErrorType.AUTHENTICATION,
                "No AI credential is configured",
            )

        last_error = None
        for credential in credentials:
            if credential.requires_fallback_policy:
                if not self.fallback_policy.reserve_system_fallback(request.class_id):
                    break
            try:
                result = adapter.generate(credential.api_key, model, request.prompt)
                if credential.source == "class":
                    self.credential_resolver.mark_used(
                        request.class_id,
                        provider_id,
                    )
                if credential.requires_fallback_policy:
                    self.fallback_policy.record_fallback(
                        class_id=request.class_id,
                        provider_id=provider_id,
                        reason=(
                            last_error.error_type.value
                            if last_error
                            else credential.fallback_reason or "class_unavailable"
                        ),
                        selected_fallback="system",
                        input_tokens=result.input_tokens,
                        output_tokens=result.output_tokens,
                    )
                return result
            except AIProviderError as exc:
                last_error = exc
                if credential.source == "class":
                    self.credential_resolver.mark_failure(
                        request.class_id,
                        provider_id,
                        exc.error_type,
                    )
                if credential.source == "system":
                    break

        if last_error:
            raise last_error
        raise AIProviderError(
            ProviderErrorType.AUTHENTICATION,
            "No allowed AI credential is available",
        )
