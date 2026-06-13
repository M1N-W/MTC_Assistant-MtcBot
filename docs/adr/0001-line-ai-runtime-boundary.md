# ADR 0001: Keep Flask as the LINE AI Runtime Boundary

Status: Accepted

Date: 2026-06-12

## Context

MTC Assistant receives student messages through the LINE webhook. AI responses
can depend on command precedence, class membership, classroom records, privacy
filtering, quotas, credential scope, and safe failure behavior.

Firebase AI Logic is designed for direct mobile and web client calls. Moving
LINE AI execution into a client surface would bypass the existing webhook and
service policy boundary. Moving the entire runtime to Vertex AI would add a new
operational boundary without solving the immediate routing problem.

## Decision

Flask remains the runtime and policy boundary for all LINE AI requests.

```text
LINE webhook
  -> Flask routing and policy
  -> classroom services and privacy filtering
  -> credential and provider selection
  -> fixed provider adapter
  -> Flask response formatting
  -> LINE reply
```

Gemini, OpenAI, Anthropic, Vertex AI, and future providers are implementation
details behind a server-side model gateway. They do not own LINE routing,
classroom context decisions, credential scope, or audit policy.

API keys are never collected through LINE or exposed to browser clients after
submission. BYOK uses fixed providers only; arbitrary custom endpoints are not
allowed.

## Consequences

- Existing LINE routing and classroom services remain authoritative.
- Provider changes do not require a webhook or product-boundary rewrite.
- The backend owns encryption, credential resolution, quotas, and fallback.
- Client-side Firebase AI Logic is not used for LINE AI requests.
- A future web/mobile AI product may use a separate ADR and security model.
