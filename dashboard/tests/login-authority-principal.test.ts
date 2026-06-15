import assert from "node:assert/strict";
import test from "node:test";

import {
  authenticateDashboardLogin,
} from "../lib/login-authority.ts";
import {
  resolveFlaskPrincipal,
} from "../lib/principal-resolution.ts";
import type {
  DashboardPrincipal,
  LoginResult,
  PrincipalResult,
} from "../lib/flask-auth-types.ts";

const principal: DashboardPrincipal = {
  account_id: "account-fake",
  username: "fake.user",
  display_name: null,
  role: "super_admin",
  class_ids: [],
  capabilities: ["auth.session.read_self"],
  session_expires_at: "2026-06-15T12:00:00.000Z",
};

test("Flask mode never invokes legacy password authentication", async () => {
  let legacyCalls = 0;
  let flaskCalls = 0;
  const result = await authenticateDashboardLogin(
    {
      mode: "flask",
      username: "fake.user",
      password: "shared password",
    },
    {
      legacyConfigured: () => true,
      verifyLegacyPassword: () => {
        legacyCalls += 1;
        return true;
      },
      flaskLogin: async (): Promise<LoginResult> => {
        flaskCalls += 1;
        return { status: "unauthenticated" };
      },
    },
  );
  assert.deepEqual(result, { status: "unauthenticated" });
  assert.equal(legacyCalls, 0);
  assert.equal(flaskCalls, 1);
});

test("legacy mode remains isolated from Flask authentication", async () => {
  let flaskCalls = 0;
  const result = await authenticateDashboardLogin(
    { mode: "legacy", username: "", password: "shared password" },
    {
      legacyConfigured: () => true,
      verifyLegacyPassword: () => true,
      flaskLogin: async (): Promise<LoginResult> => {
        flaskCalls += 1;
        return { status: "unavailable" };
      },
    },
  );
  assert.deepEqual(result, { status: "legacy_authenticated" });
  assert.equal(flaskCalls, 0);
});

test("missing and invalid Flask sessions are distinguished without trusting cookie claims", async () => {
  let meCalls = 0;
  const fakeClient = {
    me: async (): Promise<PrincipalResult> => {
      meCalls += 1;
      return { status: "unauthenticated" };
    },
  };

  assert.deepEqual(
    await resolveFlaskPrincipal(undefined, fakeClient as never),
    { status: "unauthenticated", reason: "missing" },
  );
  assert.equal(meCalls, 0);
  assert.deepEqual(
    await resolveFlaskPrincipal("x".repeat(43), fakeClient as never),
    { status: "unauthenticated", reason: "invalid" },
  );
  assert.equal(meCalls, 1);
});

test("valid principal resolution returns only the Flask client result", async () => {
  const fakeClient = {
    me: async (): Promise<PrincipalResult> => ({
      status: "authenticated",
      principal,
    }),
  };
  assert.deepEqual(
    await resolveFlaskPrincipal("x".repeat(43), fakeClient as never),
    { status: "authenticated", principal },
  );
});
