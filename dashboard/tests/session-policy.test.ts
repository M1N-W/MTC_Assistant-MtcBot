import assert from "node:assert/strict";
import test from "node:test";

import {
  FLASK_SESSION_COOKIE_NAME,
  MAX_FLASK_SESSION_AGE_SECONDS,
  buildFlaskSessionCookie,
  buildFlaskSessionDeletionCookie,
  sessionMaxAgeSeconds,
} from "../lib/session-cookie.ts";

const now = new Date("2026-06-15T00:00:00.000Z");

test("Flask session cookie is HttpOnly, same-site, root scoped, and opaque", () => {
  const cookie = buildFlaskSessionCookie(
    "opaque-value",
    "2026-06-15T01:00:00.000Z",
    { now, production: false },
  );
  assert.equal(cookie.name, FLASK_SESSION_COOKIE_NAME);
  assert.equal(cookie.value, "opaque-value");
  assert.equal(cookie.options.httpOnly, true);
  assert.equal(cookie.options.sameSite, "lax");
  assert.equal(cookie.options.path, "/");
  assert.equal(cookie.options.secure, false);
  assert.equal(cookie.options.maxAge, 3600);
  assert.deepEqual(Object.keys(cookie), ["name", "value", "options"]);
});

test("production cookie is secure and capped at twelve hours", () => {
  const cookie = buildFlaskSessionCookie(
    "opaque-value",
    "2026-06-16T12:00:00.000Z",
    { now, production: true },
  );
  assert.equal(cookie.options.secure, true);
  assert.equal(cookie.options.maxAge, MAX_FLASK_SESSION_AGE_SECONDS);
});

test("malformed and expired Flask expiries are rejected", () => {
  for (const expiresAt of [
    "not-a-date",
    "2026-06-14T23:59:59.000Z",
    "2026-06-15T12:00:00",
    "",
  ]) {
    assert.throws(() => sessionMaxAgeSeconds(expiresAt, now));
  }
});

test("cookie deletion matches security attributes and root path", () => {
  const deletion = buildFlaskSessionDeletionCookie(true);
  assert.equal(deletion.name, FLASK_SESSION_COOKIE_NAME);
  assert.equal(deletion.value, "");
  assert.equal(deletion.options.httpOnly, true);
  assert.equal(deletion.options.sameSite, "lax");
  assert.equal(deletion.options.secure, true);
  assert.equal(deletion.options.path, "/");
  assert.equal(deletion.options.maxAge, 0);
});
