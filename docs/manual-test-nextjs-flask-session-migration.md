# Next.js Flask-Session Migration Manual Test

## Scope

Verify the local Next.js BFF migration with fake identities only. Do not use
production accounts, production Firestore, real service credentials, student
data, full LINE IDs, or a production bootstrap command. Do not deploy.

## Local Configuration

Use placeholder values in a local uncommitted environment file:

```text
DASHBOARD_AUTH_MODE=flask
DASHBOARD_PUBLIC_ORIGIN=http://localhost:3000
MTC_BOT_API_BASE_URL=http://127.0.0.1:5000
MTC_DASHBOARD_API_TOKEN=<local-placeholder-service-token>
```

For rollback verification only:

```text
DASHBOARD_AUTH_MODE=legacy
DASHBOARD_PASSWORD=<local-placeholder-password>
DASHBOARD_SESSION_SECRET=<local-placeholder-session-secret>
```

Flask mode requires fake local accounts created in an isolated local test
store. Do not run the bootstrap CLI against production.

## Automated Checks

From `dashboard/`:

```powershell
npm ci
npm run test:auth
npm run lint
npm run typecheck
npm run build
npm audit --audit-level=moderate
```

From the repository root:

```powershell
python -m compileall -q src
$env:PYTHONPATH='src'
python -m unittest tests.test_dashboard_auth_api tests.test_dashboard_auth_service tests.test_dashboard_auth_health
```

## Legacy Mode

1. Set `DASHBOARD_AUTH_MODE=legacy`.
2. Confirm the login page remains password-only.
3. Confirm the configured shared password signs in.
4. Confirm logout clears the legacy cookie.
5. Confirm Flask auth endpoints are not required.

## Flask Login And Cookie

1. Set `DASHBOARD_AUTH_MODE=flask`.
2. Confirm the page shows username and password fields with `username` and
   `current-password` autocomplete values.
3. Sign in with a fake local account.
4. Confirm the browser response body contains no raw session value and no
   service credential.
5. Confirm `mtc_dashboard_flask_session` is HttpOnly, SameSite=Lax, Path=/,
   bounded to at most 12 hours, and Secure on production HTTPS.
6. Confirm browser JavaScript cannot read the cookie. The cookie value remains
   visible in normal browser network/storage inspection as expected.
7. Confirm local storage, session storage, rendered HTML, URLs, console logs,
   and analytics contain no raw session.

## Principal And Role Gate

Use separate fake local accounts for each role:

1. `super_admin`: confirm `/auth/me` resolves the account and the current
   global Dashboard loads.
2. `teacher`: confirm the signed-in limited screen appears.
3. `class_admin`: confirm the signed-in limited screen appears.
4. `student`: confirm the signed-in limited screen appears.
5. Confirm each limited screen shows only safe identity and role text, offers
   logout, and does not mount the global Dashboard shell.
6. Confirm Network shows no calls to Overview, Accounts, Homework, Broadcast,
   Blacklist, Links, AI Settings, Paperless, System, or `workspaces` APIs for
   limited roles.
7. Call `/api/admin/*` directly while signed in as each limited role. Confirm
   `403` and confirm Flask receives no global Admin API request.

## Session Failure States

1. Remove the cookie and confirm protected navigation redirects to `/login`.
2. Use an expired fake session and confirm local cookie clearing followed by
   login navigation.
3. Revoke a fake session and repeat the check.
4. Disable the fake account and repeat the check.
5. Stop the local Flask service. Confirm the Dashboard reports a temporary
   auth outage and does not claim the user is signed out.

## Logout

1. Sign out once and confirm Next.js calls Flask logout server-side.
2. Confirm both the Flask and legacy local auth cookies are cleared.
3. Submit logout again and confirm the result remains safe.
4. Stop Flask, sign out, and confirm the local cookie is still cleared while
   upstream revocation is reported only as unconfirmed.
5. Confirm request bodies, query strings, and browser headers cannot provide a
   replacement session value.
6. Set an invalid local `DASHBOARD_AUTH_MODE`, submit a same-origin logout,
   and confirm both cookies are still cleared without authentication fallback.

## Same-Origin And Redirect Checks

1. Submit login and logout from `DASHBOARD_PUBLIC_ORIGIN`; confirm acceptance.
2. Send POST, PUT, PATCH, and DELETE proxy requests with a cross-origin
   `Origin`; confirm `403` before upstream access.
3. Repeat with a malformed or missing production Origin; confirm rejection.
4. Confirm no wildcard origin or widened CORS behavior was added.
5. Confirm GET and HEAD routes remain side-effect free.
6. Confirm login always continues to `/` and logout to `/login`; arbitrary
   return URLs are not accepted.

## Secret And Data Review

Confirm browser responses, HTML, logs, fixtures, and committed files contain
no service credential, raw session, session digest, real username, password,
Firebase credential, student data, full LINE ID, or internal production URL.

This guide does not prove production rollout. It performs no production
bootstrap, production write, environment mutation, Render change, or deploy.
