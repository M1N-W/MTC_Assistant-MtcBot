# Dashboard Auth And Role Foundation Manual Test

## Scope

This guide verifies the Flask-owned backend foundation only. It does not
migrate the Next.js login, create production accounts, modify Dashboard UI, or
authorize existing global admin routes for teachers or class admins.

Use fake local identities only. Do not use real usernames, student data, LINE
IDs, passwords, reset tokens, Firebase credentials, or production service
tokens.

## Architecture Boundary

The trusted request path remains:

```text
Browser -> future Next.js BFF -> Flask /api/admin/auth/*
```

`Authorization: Bearer ...` authenticates the Next.js service. The separate
`X-MTC-Dashboard-Session` header identifies a human account. The browser must
never receive the service token or call Flask directly as the normal flow.

Flask does not set a browser cookie in this milestone. CSRF protection belongs
at the Next.js mutation boundary during the next migration phase.

## Local Verification

From the repository root:

```powershell
python -m compileall -q src
$env:PYTHONPATH='src'
python -m unittest tests.test_dashboard_auth_models
python -m unittest tests.test_dashboard_auth_service
python -m unittest tests.test_dashboard_auth_repository
python -m unittest tests.test_dashboard_auth_api
python -m unittest tests.test_bootstrap_dashboard_super_admin
python -m unittest tests.test_dashboard_auth_health
python -m unittest discover -s tests
```

The existing unrelated wording test may still fail because
`src/mtc_assistant/broadcast.py` contains the word `บอส`. Do not modify that
module as part of auth verification.

## Fake Account Scenarios

Use handles such as `fake.teacher`, `fake.classadmin`, and `fake.superadmin`.
Use generated local-only passwords of at least 12 characters. Never copy test
credentials into production.

Verify:

1. `student` has zero or one class and no admin capability.
2. `teacher` requires one or more explicit classes.
3. `class_admin` requires exactly one class.
4. `super_admin` requires no class assignment.
5. Duplicate normalized usernames are rejected.
6. Thai, Unicode, whitespace, reserved handles, and punctuation at either end
   are rejected.

## Login And Session Behavior

All auth requests require a fake local service bearer value.

```text
POST /api/admin/auth/login
GET  /api/admin/auth/me
POST /api/admin/auth/logout
```

Verify successful login returns a raw opaque token once, while persisted
storage contains only its SHA-256 digest. Verify `/auth/me` requires both the
service bearer and `X-MTC-Dashboard-Session`.

Verify logout succeeds repeatedly for the same syntactically valid token and a
revoked token cannot call `/auth/me`.

Verify sessions fail after 12 hours, account disablement, password reset,
role/assignment change, revoke-all, or session-version mismatch.

## Negative Authorization Checks

Verify:

- Service authentication alone does not create a human principal.
- A human session without service authentication is rejected.
- Transitional `X-MTC-Admin-*` headers cannot authenticate `/auth/me`.
- Student accounts receive no admin capabilities.
- Teachers and class admins cannot authorize another class.
- Unknown capabilities and disabled accounts are denied.
- Existing global Admin API endpoints are not represented as migrated.

## Firestore Paths

```text
system/dashboard_auth/accounts/{accountId}
system/dashboard_auth/usernames/{usernameDigest}
system/dashboard_auth/sessions/{tokenDigest}
system/dashboard_auth/login_throttles/{usernameDigest}
system/dashboard_auth/guards/super_admin_bootstrap
system/dashboard_security/audit_events/{eventId}
```

Username reservations prevent duplicate normalized handles. Session document
IDs are SHA-256 token digests. Login throttle documents are created only after
a username reservation resolves to a real account.

Invalid, unknown, disabled, corrupt, wrong-password, and internally blocked
credentials all return the same generic `401` response. Blocked accounts do
not receive a distinct `429`, `Retry-After`, or public throttle indicator.
Invalid and unknown usernames produce only redacted process-local telemetry;
they do not create durable audit or throttle documents.

## Bootstrap Safety

Do not run the bootstrap CLI against production during this task.

In an isolated fake-client test, verify the CLI:

- compares `--project-id` with the actual configured Firebase client project;
- requires the project ID to be typed again;
- reads the password twice through non-echoing input;
- refuses an existing bootstrap guard; and
- atomically writes the guard, username reservation, account, and audit event.

## Operational Health

A best-effort audit failure increments
`security_audit_write_failures` and reports
`services.security_audit = false`. It must not mark LINE, Firebase, or the
webhook unavailable. `/healthz` remains HTTP 200 while the core runtime is
usable and reports overall `degraded`.

## Rollback

Remove the new auth blueprint registration and auth modules. Existing
shared-password Dashboard login and transitional principal headers remain
unchanged. Additive Firestore records may remain dormant; no existing
collection requires restoration.
