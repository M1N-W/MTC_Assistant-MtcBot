# AI Architecture Rework: AI-0 and AI-1

## Decision

MTC Assistant remains a command-first classroom system. LINE messages enter the
Flask webhook, deterministic features run before AI, and model providers remain
behind server-side policy and service boundaries.

AI-1 introduces Smart AI Entry Routing. It does not introduce AI Mode, memory,
classroom context generation, provider credentials, or dashboard AI settings.

## Current Call Map

```text
LINE /callback
  -> handlers.handle_message
  -> blacklist and rate limit
  -> class resolution
  -> active homework and exam flows
  -> specialized deterministic handlers
  -> command_router.handle_standard_command
  -> unconditional features.get_gemini_response fallback
  -> LINE reply
```

The unconditional final fallback is the behavior AI-1 replaces.

## AI-1 Routing Contract

```text
1. Preserve blacklist, rate limit, onboarding, and modal session handling.
2. Detect an explicit AI prefix.
3. Run existing specialized and standard commands.
4. Answer deterministic date/day utilities in Asia/Bangkok.
5. Bridge classroom questions to existing commands without AI.
6. Send conservative allowlisted learning questions to AI.
7. Return a Quick Reply helper for ambiguous or unknown messages.
```

Supported explicit prefixes are `ai`, `เอไอ`, `ถามAI`, `ถาม AI`,
`ถาม ai`, and `ถาม เอไอ`. Prefix matching is anchored at the beginning and
requires a boundary. An empty prompt returns usage guidance without calling a
model.

No-prefix AI entry is intentionally conservative. Short acknowledgements,
numeric chatter, ASCII gibberish, likely command typos, and a question mark by
itself do not call AI.

Classroom questions such as homework, timetable, and exam questions do not call
AI until a later context service can provide sourced classroom data.

## Risk Sheet

Deliverable:
Smart AI Entry Routing plus a documented path to a server-side multi-provider
gateway and BYOK.

Tightest constraint:
Non-AI routing must perform no network I/O and remain negligible relative to
LINE webhook and provider latency.

Blast radius:
LINE text routing, Gemini invocation count, help copy, Quick Replies, and future
AI provider selection.

Dependency graph:
`handlers.py -> ai_entry_router.py -> command_router.py | features.py`.
Future work adds `ai_model_gateway.py -> provider adapters` and
`ai_credential_service.py -> Firestore`.

Load order:
Flask initializes Firebase and system Gemini clients. The AI entry classifier
has no initialization or external I/O.

Smallest delta:
Add one pure routing module, narrow handler dispatch changes, one Quick Reply
builder, focused help copy, and tests.

Architecture smells:
`handlers.py` owns too many routing responsibilities. Substring command matching
also creates implicit precedence coupling. AI-1 does not rewrite either system.

Exit criteria:
Unknown text does not call AI. Existing commands and modal sessions keep their
precedence. Focused and full tests pass except separately documented pre-existing
failures.

Rollback:
Revert the AI-1 code change. No data migration or Firestore rollback is needed.

## Delivery Phases

1. AI-0: this audit and the Flask runtime-boundary ADR.
2. AI-1: Smart AI Entry Routing.
3. AI Gateway: fixed Gemini, OpenAI, and Anthropic adapters.
4. Dashboard principal: signed identity, role, and allowed-class claims.
5. BYOK v1: super-admin managed class credentials, encrypted at rest.
6. BYOK v2: personal credentials after student web identity and consent.

BYOK is not collected through LINE. The initial release accepts only fixed
provider presets and system-controlled model allowlists. Custom base URLs are
not supported.

## Verification

```powershell
python -m compileall -q src
$env:PYTHONPATH='src'; python -m unittest discover -s tests
cd dashboard
npm run lint
npm run typecheck
npm run build
```
