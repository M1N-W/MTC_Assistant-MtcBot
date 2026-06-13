"""Firestore-backed encrypted class AI credentials."""

from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Callable

from mtc_assistant.ai_credentials import (
    CredentialCipher,
    CredentialScope,
    ResolvedCredential,
    StoredCredential,
    mask_api_key,
)
from mtc_assistant.ai_provider_adapters import ProviderErrorType
from mtc_assistant.ai_provider_adapters import build_default_adapters
from mtc_assistant.ai_provider_registry import (
    get_provider_definition,
    list_provider_definitions,
)
from mtc_assistant.invite_codes import is_valid_class_id


def build_credential_cipher_from_env() -> CredentialCipher:
    raw_keyring = os.environ.get("AI_CREDENTIALS_ENCRYPTION_KEYS", "").strip()
    current_version = int(os.environ.get("AI_CREDENTIALS_CURRENT_KEY_VERSION", "1"))

    if raw_keyring:
        parsed = json.loads(raw_keyring)
        if not isinstance(parsed, dict):
            raise ValueError("AI_CREDENTIALS_ENCRYPTION_KEYS must be a JSON object")
        keys = {
            int(version): base64.b64decode(str(encoded), validate=True)
            for version, encoded in parsed.items()
        }
        return CredentialCipher(keys, current_version)

    single_key = os.environ.get("AI_CREDENTIALS_ENCRYPTION_KEY", "").strip()
    if not single_key:
        raise ValueError("AI credential encryption is not configured")
    return CredentialCipher(
        {current_version: base64.b64decode(single_key, validate=True)},
        current_version,
    )


def system_credentials_from_env() -> dict[str, str]:
    values = {
        "gemini": (
            os.environ.get("GEMINI_API_KEY_PRIMARY")
            or os.environ.get("GEMINI_API_KEY")
            or ""
        ),
        "openai": os.environ.get("OPENAI_API_KEY", ""),
        "anthropic": os.environ.get("ANTHROPIC_API_KEY", ""),
    }
    return {provider: key.strip() for provider, key in values.items() if key.strip()}


class AICredentialService:
    def __init__(
        self,
        db,
        cipher: CredentialCipher,
        *,
        system_credentials: dict[str, str] | None = None,
        now_provider: Callable[[], datetime] | None = None,
        adapters: dict | None = None,
    ):
        self.db = db
        self.cipher = cipher
        self.system_credentials = dict(system_credentials or {})
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self.adapters = adapters or build_default_adapters()

    def validate_credential(
        self,
        provider_id: str,
        api_key: str,
        model: str,
    ) -> dict:
        definition = get_provider_definition(provider_id)
        definition.validate_model(model)
        result = self.adapters[provider_id].generate(
            str(api_key or "").strip(),
            model,
            "Reply with OK.",
        )
        return {
            "status": "valid",
            "provider_id": provider_id,
            "model": model,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        }

    def save_class_credential(
        self,
        class_id: str,
        provider_id: str,
        api_key: str,
        *,
        model: str,
        actor_id: str,
    ) -> dict:
        self._validate_target(class_id, provider_id)
        definition = get_provider_definition(provider_id)
        definition.validate_model(model)
        scope = CredentialScope("class", class_id, provider_id)
        encrypted = self.cipher.encrypt(api_key, scope)
        now = self._now_iso()
        existing = self._credential_ref(class_id, provider_id).get()
        existing_data = existing.to_dict() if getattr(existing, "exists", False) else {}
        data = {
            "provider_id": provider_id,
            "scope": "class",
            "owner_id": class_id,
            "ciphertext": encrypted.ciphertext,
            "nonce": encrypted.nonce,
            "key_version": encrypted.key_version,
            "masked_key": mask_api_key(api_key),
            "fingerprint_hmac": encrypted.fingerprint_hmac,
            "model": model,
            "status": "active",
            "last_validated_at": now,
            "last_used_at": existing_data.get("last_used_at"),
            "last_error_type": None,
            "cooldown_until": None,
            "created_by": existing_data.get("created_by") or actor_id,
            "created_at": existing_data.get("created_at") or now,
            "updated_by": actor_id,
            "updated_at": now,
        }
        self._credential_ref(class_id, provider_id).set(data)
        return _public_credential(data)

    def list_class_credentials(self, class_id: str) -> list[dict]:
        if not is_valid_class_id(class_id):
            raise ValueError("Invalid class_id")
        stored = {}
        for snapshot in self._credentials_collection(class_id).stream():
            data = snapshot.to_dict() or {}
            stored[str(data.get("provider_id") or snapshot.id)] = data

        result = []
        for definition in list_provider_definitions():
            data = stored.get(definition.provider_id)
            if data:
                result.append(_public_credential(data))
            else:
                result.append({
                    "provider_id": definition.provider_id,
                    "display_name": definition.display_name,
                    "configured": False,
                    "status": "not_configured",
                    "masked_key": "",
                    "model": definition.default_model,
                    "allowed_models": list(definition.models),
                    "updated_at": None,
                    "last_validated_at": None,
                    "last_used_at": None,
                    "last_error_type": None,
                    "cooldown_until": None,
                })
        return result

    def delete_class_credential(self, class_id: str, provider_id: str) -> bool:
        self._validate_target(class_id, provider_id)
        ref = self._credential_ref(class_id, provider_id)
        snapshot = ref.get()
        if not getattr(snapshot, "exists", False):
            return False
        ref.delete()
        return True

    def disable_class_credential(
        self,
        class_id: str,
        provider_id: str,
        *,
        actor_id: str,
    ) -> dict:
        self._validate_target(class_id, provider_id)
        ref = self._credential_ref(class_id, provider_id)
        snapshot = ref.get()
        if not getattr(snapshot, "exists", False):
            raise ValueError("AI credential was not found")
        now = self._now_iso()
        ref.set({
            "status": "disabled",
            "cooldown_until": None,
            "updated_by": actor_id,
            "updated_at": now,
        }, merge=True)
        updated = snapshot.to_dict() or {}
        updated.update({
            "status": "disabled",
            "cooldown_until": None,
            "updated_by": actor_id,
            "updated_at": now,
        })
        return _public_credential(updated)

    def resolve_candidates(self, request, provider_id: str) -> list[ResolvedCredential]:
        get_provider_definition(provider_id)
        candidates = []
        if request.class_id and is_valid_class_id(request.class_id):
            snapshot = self._credential_ref(request.class_id, provider_id).get()
            if getattr(snapshot, "exists", False):
                data = snapshot.to_dict() or {}
                if self._credential_is_usable(data):
                    scope = CredentialScope("class", request.class_id, provider_id)
                    stored = StoredCredential(
                        ciphertext=str(data.get("ciphertext") or ""),
                        nonce=str(data.get("nonce") or ""),
                        key_version=int(data.get("key_version") or 0),
                    )
                    candidates.append(ResolvedCredential(
                        "class",
                        self.cipher.decrypt(stored, scope),
                    ))

        system_key = self.system_credentials.get(provider_id)
        if system_key:
            candidates.append(ResolvedCredential(
                "system",
                system_key,
                requires_fallback_policy=bool(request.class_id),
                fallback_reason="class_unavailable",
            ))
        return candidates

    def mark_used(self, class_id: str, provider_id: str) -> None:
        ref = self._credential_ref(class_id, provider_id)
        snapshot = ref.get()
        if not getattr(snapshot, "exists", False):
            return
        ref.set({
            "last_used_at": self._now_iso(),
        }, merge=True)

    def mark_failure(
        self,
        class_id: str,
        provider_id: str,
        error_type: ProviderErrorType,
    ) -> None:
        ref = self._credential_ref(class_id, provider_id)
        snapshot = ref.get()
        if not getattr(snapshot, "exists", False):
            return
        now = self.now_provider()
        if error_type == ProviderErrorType.AUTHENTICATION:
            status = "invalid"
            cooldown = now + timedelta(hours=24)
        elif error_type == ProviderErrorType.QUOTA:
            status = "cooldown"
            cooldown = now + timedelta(minutes=15)
        else:
            status = "cooldown"
            cooldown = now + timedelta(minutes=5)
        ref.set({
            "status": status,
            "last_error_type": error_type.value,
            "cooldown_until": cooldown.isoformat(),
            "updated_at": now.isoformat(),
        }, merge=True)
        warning = {
            "event_type": "class_ai_credential_warning",
            "provider_id": provider_id,
            "class_id": class_id,
            "reason": error_type.value,
            "status": status,
            "created_at": now.isoformat(),
        }
        (
            self.db.collection("classes")
            .document(class_id)
            .collection("admin_notifications")
            .add(warning)
        )
        self.db.collection("system_ai_alerts").add({
            **warning,
            "audience": "super_admin",
        })

    def _credential_is_usable(self, data: dict) -> bool:
        status = str(data.get("status") or "")
        if status == "active":
            return True
        if status != "cooldown":
            return False
        cooldown_until = _parse_datetime(data.get("cooldown_until"))
        return cooldown_until is None or cooldown_until <= self.now_provider()

    def _validate_target(self, class_id: str, provider_id: str) -> None:
        if not is_valid_class_id(class_id):
            raise ValueError("Invalid class_id")
        get_provider_definition(provider_id)

    def _credentials_collection(self, class_id: str):
        return (
            self.db.collection("classes")
            .document(class_id)
            .collection("ai_credentials")
        )

    def _credential_ref(self, class_id: str, provider_id: str):
        return self._credentials_collection(class_id).document(provider_id)

    def _now_iso(self) -> str:
        return self.now_provider().isoformat()


def _public_credential(data: dict) -> dict:
    definition = get_provider_definition(str(data.get("provider_id") or ""))
    return {
        "provider_id": definition.provider_id,
        "display_name": definition.display_name,
        "configured": True,
        "status": str(data.get("status") or "unknown"),
        "masked_key": str(data.get("masked_key") or ""),
        "model": str(data.get("model") or definition.default_model),
        "allowed_models": list(definition.models),
        "updated_at": data.get("updated_at"),
        "last_validated_at": data.get("last_validated_at"),
        "last_used_at": data.get("last_used_at"),
        "last_error_type": data.get("last_error_type"),
        "cooldown_until": data.get("cooldown_until"),
    }


def _parse_datetime(value) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (TypeError, ValueError):
        return None
