"""LINE-facing AI orchestration outside provider adapters."""

from __future__ import annotations

import os
from typing import Callable

from mtc_assistant.ai_credential_service import (
    AICredentialService,
    build_credential_cipher_from_env,
    system_credentials_from_env,
)
from mtc_assistant.ai_fallback_policy import FirestoreFallbackPolicy
from mtc_assistant.ai_model_gateway import AIModelGateway, AIRequest
from mtc_assistant.ai_provider_adapters import AIProviderError, build_default_adapters
from mtc_assistant.ai_provider_registry import get_provider_definition
from mtc_assistant.config import logger


SAFE_AI_UNAVAILABLE = (
    "ขออภัยครับ ขณะนี้ AI ยังไม่พร้อมใช้งาน กรุณาลองใหม่ภายหลัง"
)


def generate_ai_response(
    prompt: str,
    *,
    class_id: str,
    user_id: str | None,
    db,
    legacy_responder: Callable[[str], str],
    gateway_factory: Callable | None = None,
) -> str:
    if not _env_flag("ALLOW_CLASS_BYOK", default=False) or db is None:
        return legacy_responder(prompt)

    settings = _read_ai_settings(db, class_id)
    provider_id = str(settings.get("selected_provider") or "gemini")
    definition = get_provider_definition(provider_id)
    model = str(settings.get("selected_model") or definition.default_model)
    definition.validate_model(model)

    try:
        gateway = (gateway_factory or _build_gateway)(db)
        result = gateway.generate(
            AIRequest(
                prompt=prompt,
                task_type="line_chat",
                class_id=class_id,
                user_id=user_id,
            ),
            provider_id=provider_id,
            model=model,
        )
        return result.text
    except (AIProviderError, ValueError) as exc:
        logger.warning(
            "AI request unavailable provider=%s class_id=%s category=%s",
            provider_id,
            class_id,
            getattr(getattr(exc, "error_type", None), "value", "configuration"),
        )
        return SAFE_AI_UNAVAILABLE


def _build_gateway(db) -> AIModelGateway:
    adapters = build_default_adapters()
    credentials = AICredentialService(
        db,
        build_credential_cipher_from_env(),
        system_credentials=system_credentials_from_env(),
        adapters=adapters,
    )
    return AIModelGateway(
        credentials,
        adapters,
        FirestoreFallbackPolicy(db),
    )


def _read_ai_settings(db, class_id: str) -> dict:
    snapshot = (
        db.collection("classes")
        .document(class_id)
        .collection("config")
        .document("ai")
        .get()
    )
    return snapshot.to_dict() if getattr(snapshot, "exists", False) else {}


def _env_flag(name: str, *, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
