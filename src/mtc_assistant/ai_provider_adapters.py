"""Server-side HTTP adapters for fixed AI providers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

import requests

from mtc_assistant.ai_provider_registry import get_provider_definition


DEFAULT_TIMEOUT_SECONDS = 15


class ProviderErrorType(str, Enum):
    AUTHENTICATION = "authentication"
    QUOTA = "quota"
    TIMEOUT = "timeout"
    INVALID_REQUEST = "invalid_request"
    SAFETY = "safety"
    PROVIDER_SERVICE = "provider_service"
    INVALID_RESPONSE = "invalid_response"


class AIProviderError(Exception):
    def __init__(self, error_type: ProviderErrorType, message: str):
        super().__init__(message)
        self.error_type = error_type


@dataclass(frozen=True)
class AIProviderResult:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0


class RequestsTransport:
    def post(self, url: str, *, headers: dict, json: dict, timeout: float):
        return requests.post(url, headers=headers, json=json, timeout=timeout)


class BaseProviderAdapter:
    provider_id = ""

    def __init__(self, transport=None, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS):
        self.transport = transport or RequestsTransport()
        self.timeout_seconds = timeout_seconds

    def _post(self, url: str, *, headers: dict, payload: dict):
        try:
            response = self.transport.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout_seconds,
            )
        except requests.Timeout as exc:
            raise AIProviderError(ProviderErrorType.TIMEOUT, "AI provider timed out") from exc
        except requests.RequestException as exc:
            raise AIProviderError(
                ProviderErrorType.PROVIDER_SERVICE,
                "AI provider request failed",
            ) from exc

        if response.status_code >= 400:
            raise AIProviderError(
                _error_type_for_status(response.status_code),
                _safe_error_message(response.status_code),
            )
        try:
            return response.json()
        except (TypeError, ValueError) as exc:
            raise AIProviderError(
                ProviderErrorType.INVALID_RESPONSE,
                "AI provider returned invalid JSON",
            ) from exc

    def _validate_model(self, model: str) -> str:
        return get_provider_definition(self.provider_id).validate_model(model)


class GeminiAdapter(BaseProviderAdapter):
    provider_id = "gemini"

    def generate(self, api_key: str, model: str, prompt: str) -> AIProviderResult:
        model = self._validate_model(model)
        payload = self._post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
            payload={
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            },
        )
        if payload.get("promptFeedback", {}).get("blockReason"):
            raise AIProviderError(ProviderErrorType.SAFETY, "AI provider blocked the prompt")
        parts = (
            payload.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [])
        )
        text = "".join(str(part.get("text", "")) for part in parts).strip()
        usage = payload.get("usageMetadata", {})
        return _result_or_error(
            text,
            usage.get("promptTokenCount", 0),
            usage.get("candidatesTokenCount", 0),
        )


class OpenAIAdapter(BaseProviderAdapter):
    provider_id = "openai"

    def generate(self, api_key: str, model: str, prompt: str) -> AIProviderResult:
        model = self._validate_model(model)
        payload = self._post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            payload={
                "model": model,
                "input": prompt,
                "max_output_tokens": 1200,
            },
        )
        text_parts = []
        for output in payload.get("output", []):
            if output.get("type") != "message":
                continue
            for content in output.get("content", []):
                if content.get("type") == "output_text":
                    text_parts.append(str(content.get("text", "")))
        usage = payload.get("usage", {})
        return _result_or_error(
            "".join(text_parts).strip(),
            usage.get("input_tokens", 0),
            usage.get("output_tokens", 0),
        )


class AnthropicAdapter(BaseProviderAdapter):
    provider_id = "anthropic"

    def generate(self, api_key: str, model: str, prompt: str) -> AIProviderResult:
        model = self._validate_model(model)
        payload = self._post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            payload={
                "model": model,
                "max_tokens": 1200,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        text = "".join(
            str(content.get("text", ""))
            for content in payload.get("content", [])
            if content.get("type") == "text"
        ).strip()
        usage = payload.get("usage", {})
        return _result_or_error(
            text,
            usage.get("input_tokens", 0),
            usage.get("output_tokens", 0),
        )


def build_default_adapters(transport=None) -> dict[str, BaseProviderAdapter]:
    return {
        "gemini": GeminiAdapter(transport),
        "openai": OpenAIAdapter(transport),
        "anthropic": AnthropicAdapter(transport),
    }


def _result_or_error(text: str, input_tokens: Any, output_tokens: Any) -> AIProviderResult:
    if not text:
        raise AIProviderError(
            ProviderErrorType.INVALID_RESPONSE,
            "AI provider returned no text",
        )
    return AIProviderResult(
        text=text,
        input_tokens=_safe_int(input_tokens),
        output_tokens=_safe_int(output_tokens),
    )


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _error_type_for_status(status_code: int) -> ProviderErrorType:
    if status_code in (401, 403):
        return ProviderErrorType.AUTHENTICATION
    if status_code == 429:
        return ProviderErrorType.QUOTA
    if status_code in (400, 404, 422):
        return ProviderErrorType.INVALID_REQUEST
    return ProviderErrorType.PROVIDER_SERVICE


def _safe_error_message(status_code: int) -> str:
    if status_code in (401, 403):
        return "AI provider authentication failed"
    if status_code == 429:
        return "AI provider quota is limited"
    if status_code in (400, 404, 422):
        return "AI provider rejected the request"
    return "AI provider is unavailable"
