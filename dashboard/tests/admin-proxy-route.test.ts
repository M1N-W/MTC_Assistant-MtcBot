import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { isAdminProxyMutation } from "../lib/admin-proxy-policy.ts";
import type { DashboardPrincipal } from "../lib/flask-auth-types.ts";
import { executeVerifiedGlobalProxy } from "../lib/global-admin-gate.ts";
import {
  OriginValidationError,
  validateMutationOrigin,
} from "../lib/same-origin.ts";

function principal(role: DashboardPrincipal["role"]): DashboardPrincipal {
  return {
    account_id: `account-${role}`,
    username: `fake.${role}`,
    display_name: null,
    role,
    class_ids: role === "super_admin" ? [] : ["mtc13"],
    capabilities: ["auth.session.read_self"],
    session_expires_at: "2026-06-15T12:00:00.000Z",
  };
}

test("PATCH is a protected Admin proxy mutation", () => {
  assert.equal(isAdminProxyMutation("PATCH"), true);
  assert.equal(isAdminProxyMutation("GET"), false);
  assert.equal(isAdminProxyMutation("HEAD"), false);
});

test("Admin proxy exports PATCH through the shared proxy function", async () => {
  const source = await readFile(
    new URL("../app/api/admin/[...path]/route.ts", import.meta.url),
    "utf8",
  );
  assert.match(
    source,
    /export async function PATCH\([^]*?return proxy\(request, context\);[^]*?\}/,
  );
});

test("cross-origin PATCH is rejected by the mutation origin policy", () => {
  assert.equal(isAdminProxyMutation("PATCH"), true);
  assert.throws(
    () =>
      validateMutationOrigin({
        authMode: "flask",
        nodeEnv: "production",
        publicOrigin: "https://dashboard.example.test",
        requestOrigin: "https://attacker.example.test",
        requestUrl: "https://dashboard.example.test/api/admin/settings",
        secFetchSite: "cross-site",
      }),
    OriginValidationError,
  );
});

test("non-super-admin PATCH stops before the upstream callback", async () => {
  for (const role of ["teacher", "class_admin", "student"] as const) {
    let upstreamCalls = 0;
    const response = await executeVerifiedGlobalProxy(
      { status: "authenticated", principal: principal(role) },
      async () => {
        upstreamCalls += 1;
        return new Response(null, { status: 204 });
      },
    );
    assert.equal(response.status, 403);
    assert.equal(upstreamCalls, 0);
  }
});

test("verified super-admin PATCH can reach the upstream callback", async () => {
  let upstreamCalls = 0;
  const response = await executeVerifiedGlobalProxy(
    { status: "authenticated", principal: principal("super_admin") },
    async () => {
      upstreamCalls += 1;
      return new Response(null, { status: 204 });
    },
  );
  assert.equal(response.status, 204);
  assert.equal(upstreamCalls, 1);
});
