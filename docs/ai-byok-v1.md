# Class AI BYOK v1

## Runtime Boundary

```text
LINE /callback
  -> Flask command-first routing
  -> AI runtime policy
  -> credential resolver
  -> fixed provider adapter
  -> LINE-safe response
```

The browser submits credentials through the authenticated Next.js admin proxy.
Only Flask validates, encrypts, persists, decrypts, and selects credentials.
LINE messages never accept API keys.

BYOK v1 is managed by super admins only. Class-admin access remains disabled
until individual class-admin authentication and actor identity are implemented.

## Supported Providers

- Google Gemini
- OpenAI
- Anthropic

Models come from `ai_provider_registry.py`. Custom model names and custom base
URLs are rejected.

## Storage

Class credentials use:

```text
classes/{classId}/ai_credentials/{providerId}
```

The document stores AES-256-GCM ciphertext, nonce, key version, masked key,
HMAC fingerprint, status, safe error metadata, and audit timestamps. Provider,
scope, owner, and key version are authenticated associated data.

Class policy uses:

```text
classes/{classId}/config/ai
```

Fallback usage and audit metadata use date-partitioned class collections.
Credential failures create class-scoped admin notifications and system operational
alerts containing provider, class, reason, and status only.

## Required Environment

```text
ALLOW_CLASS_BYOK=true
ALLOW_USER_BYOK=false
AI_CREDENTIALS_ENCRYPTION_KEYS={"1":"<base64 32-byte key>"}
AI_CREDENTIALS_CURRENT_KEY_VERSION=1
```

System fallback credentials remain server environment variables:

```text
GEMINI_API_KEY_PRIMARY
OPENAI_API_KEY
ANTHROPIC_API_KEY
```

The ciphertext stores a key version for forward compatibility. Runtime
decryption can use configured older key versions, and new writes use the
current version. An operation that re-encrypts existing credentials during key
rotation is future work and is not implemented in BYOK v1.

## Admin Lifecycle

Super admins can operate class-scoped credentials across classes. Class-admin
principals are rejected for BYOK v1. The dashboard supports connection testing,
create or replace, disable, delete, selected model policy, system fallback, and
daily request/token budgets. Responses never include plaintext keys,
ciphertext, nonces, complete prompts, or provider responses.

## BYOK v2

Personal credentials remain reserved at:

```text
users/{userId}/ai_credentials/{providerId}
```

`ALLOW_USER_BYOK` remains false until student web identity, explicit provider
consent, per-user quotas, privacy tests, and recovery flows are implemented.
