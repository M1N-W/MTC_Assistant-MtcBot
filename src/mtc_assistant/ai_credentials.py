"""Encrypted credential primitives shared by BYOK services."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from typing import Literal

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


CredentialScopeName = Literal["system", "class", "user"]
ProviderId = Literal["gemini", "openai", "anthropic"]


@dataclass(frozen=True)
class CredentialScope:
    scope: CredentialScopeName
    owner_id: str
    provider_id: ProviderId


@dataclass(frozen=True)
class StoredCredential:
    ciphertext: str
    nonce: str
    key_version: int


@dataclass(frozen=True)
class EncryptedCredential(StoredCredential):
    fingerprint_hmac: str


@dataclass(frozen=True)
class ResolvedCredential:
    source: CredentialScopeName
    api_key: str
    requires_fallback_policy: bool = False
    fallback_reason: str | None = None


class CredentialCipher:
    def __init__(self, keys: dict[int, bytes], current_version: int):
        if current_version not in keys:
            raise ValueError("Current credential key version is unavailable")
        for key in keys.values():
            if len(key) != 32:
                raise ValueError("Credential encryption keys must be 32 bytes")
        self._keys = dict(keys)
        self.current_version = current_version

    def encrypt(self, api_key: str, scope: CredentialScope) -> EncryptedCredential:
        secret = str(api_key or "").strip()
        if not secret:
            raise ValueError("API key is required")
        key = self._keys[self.current_version]
        nonce = os.urandom(12)
        ciphertext = AESGCM(key).encrypt(
            nonce,
            secret.encode("utf-8"),
            _scope_aad(scope, self.current_version),
        )
        fingerprint = hmac.new(key, secret.encode("utf-8"), hashlib.sha256).hexdigest()
        return EncryptedCredential(
            ciphertext=base64.b64encode(ciphertext).decode("ascii"),
            nonce=base64.b64encode(nonce).decode("ascii"),
            key_version=self.current_version,
            fingerprint_hmac=fingerprint,
        )

    def decrypt(self, stored: StoredCredential, scope: CredentialScope) -> str:
        try:
            key = self._keys[stored.key_version]
        except KeyError as exc:
            raise ValueError("Credential encryption key version is unavailable") from exc
        plaintext = AESGCM(key).decrypt(
            base64.b64decode(stored.nonce, validate=True),
            base64.b64decode(stored.ciphertext, validate=True),
            _scope_aad(scope, stored.key_version),
        )
        return plaintext.decode("utf-8")


def mask_api_key(api_key: str) -> str:
    secret = str(api_key or "")
    if len(secret) < 4:
        return "••••"
    return f"••••{secret[-4:]}"


def _scope_aad(scope: CredentialScope, key_version: int) -> bytes:
    return json.dumps({
        "scope": scope.scope,
        "owner_id": scope.owner_id,
        "provider_id": scope.provider_id,
        "key_version": key_version,
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")
