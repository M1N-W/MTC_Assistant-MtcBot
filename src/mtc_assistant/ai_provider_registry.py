"""Fixed AI provider and model allowlists."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderDefinition:
    provider_id: str
    display_name: str
    models: tuple[str, ...]
    default_model: str

    def validate_model(self, model: str) -> str:
        if model not in self.models:
            raise ValueError(f"Unsupported model for {self.provider_id}")
        return model


PROVIDERS = {
    "gemini": ProviderDefinition(
        provider_id="gemini",
        display_name="Google Gemini",
        models=("gemini-2.5-flash", "gemini-3.5-flash"),
        default_model="gemini-2.5-flash",
    ),
    "openai": ProviderDefinition(
        provider_id="openai",
        display_name="OpenAI",
        models=("gpt-4.1-mini", "gpt-5.5"),
        default_model="gpt-4.1-mini",
    ),
    "anthropic": ProviderDefinition(
        provider_id="anthropic",
        display_name="Anthropic",
        models=("claude-haiku-4-5", "claude-sonnet-4-6"),
        default_model="claude-haiku-4-5",
    ),
}


def get_provider_definition(provider_id: str) -> ProviderDefinition:
    try:
        return PROVIDERS[provider_id]
    except KeyError as exc:
        raise ValueError("Unsupported AI provider") from exc


def list_provider_definitions() -> tuple[ProviderDefinition, ...]:
    return tuple(PROVIDERS.values())
