import assert from "node:assert/strict";
import test from "node:test";

import {
  applyLoginCookieTransition,
  buildLegacySessionDeletionCookie,
  clearAllAuthCookies,
  LEGACY_SESSION_COOKIE_NAME,
} from "../lib/auth-cookies.ts";
import {
  FLASK_SESSION_COOKIE_NAME,
  buildFlaskSessionDeletionCookie,
} from "../lib/session-cookie.ts";
import { logoutRevocationToken } from "../lib/logout-policy.ts";

type Write = {
  name: string;
  value: string;
  options: Record<string, unknown>;
};

function fakeStore() {
  const writes: Write[] = [];
  return {
    writes,
    set(name: string, value: string, options: Record<string, unknown>) {
      writes.push({ name, value, options });
    },
  };
}

const legacyCookie = {
  name: LEGACY_SESSION_COOKIE_NAME,
  value: "legacy-cookie",
  options: {
    httpOnly: true as const,
    sameSite: "lax" as const,
    secure: false,
    path: "/" as const,
    maxAge: 28_800,
  },
};

const flaskCookie = {
  name: FLASK_SESSION_COOKIE_NAME,
  value: "opaque-cookie",
  options: {
    httpOnly: true as const,
    sameSite: "lax" as const,
    secure: false,
    path: "/" as const,
    maxAge: 3_600,
  },
};

test("successful Flask login sets Flask cookie and clears legacy cookie", () => {
  const store = fakeStore();
  applyLoginCookieTransition(store, { mode: "flask", cookie: flaskCookie }, false);
  assert.deepEqual(store.writes.map((write) => write.name), [
    FLASK_SESSION_COOKIE_NAME,
    LEGACY_SESSION_COOKIE_NAME,
  ]);
  assert.equal(store.writes[1]?.options.maxAge, 0);
});

test("successful legacy login sets legacy cookie and clears Flask cookie", () => {
  const store = fakeStore();
  applyLoginCookieTransition(store, { mode: "legacy", cookie: legacyCookie }, false);
  assert.deepEqual(store.writes.map((write) => write.name), [
    LEGACY_SESSION_COOKIE_NAME,
    FLASK_SESSION_COOKIE_NAME,
  ]);
  assert.equal(store.writes[1]?.options.maxAge, 0);
});

test("failed login changes neither cookie", () => {
  const store = fakeStore();
  applyLoginCookieTransition(store, null, false);
  assert.deepEqual(store.writes, []);
});

test("logout clears both cookies in every mode", () => {
  for (const production of [false, true]) {
    const store = fakeStore();
    clearAllAuthCookies(store, production);
    assert.deepEqual(store.writes.map((write) => write.name), [
      LEGACY_SESSION_COOKIE_NAME,
      FLASK_SESSION_COOKIE_NAME,
    ]);
    assert.ok(store.writes.every((write) => write.value === ""));
    assert.ok(store.writes.every((write) => write.options.maxAge === 0));
  }
});

test("legacy and Flask deletion attributes match and introduce no Domain", () => {
  for (const deletion of [
    buildLegacySessionDeletionCookie(true),
    buildFlaskSessionDeletionCookie(true),
  ]) {
    assert.equal(deletion.options.httpOnly, true);
    assert.equal(deletion.options.sameSite, "lax");
    assert.equal(deletion.options.secure, true);
    assert.equal(deletion.options.path, "/");
    assert.equal(deletion.options.maxAge, 0);
    assert.equal("domain" in deletion.options, false);
  }
});

test("only Flask mode can select the Flask cookie for revocation", () => {
  const cookieToken = "x".repeat(43);
  assert.equal(logoutRevocationToken("flask", cookieToken), cookieToken);
  assert.equal(logoutRevocationToken("legacy", cookieToken), undefined);
  assert.equal(logoutRevocationToken(null, cookieToken), undefined);
  assert.equal(logoutRevocationToken("flask", undefined), undefined);
});
