import assert from "node:assert/strict";
import test from "node:test";

import {
  authorizeGlobalDashboard,
  executeVerifiedGlobalProxy,
} from "../lib/global-admin-gate.ts";
import type { DashboardPrincipal } from "../lib/flask-auth-types.ts";

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

test("only a verified super admin receives the current global Dashboard", () => {
  assert.equal(authorizeGlobalDashboard(principal("super_admin")), "allowed");
  assert.equal(authorizeGlobalDashboard(principal("teacher")), "limited");
  assert.equal(authorizeGlobalDashboard(principal("class_admin")), "limited");
  assert.equal(authorizeGlobalDashboard(principal("student")), "limited");
  assert.equal(
    authorizeGlobalDashboard({ ...principal("teacher"), role: "unknown" }),
    "denied",
  );
});

test("teacher, class admin, and student stop before global Admin upstream fetch", async () => {
  for (const role of ["teacher", "class_admin", "student"] as const) {
    let upstreamCalls = 0;
    const result = await executeVerifiedGlobalProxy(
      { status: "authenticated", principal: principal(role) },
      async () => {
        upstreamCalls += 1;
        return new Response(null, { status: 200 });
      },
    );
    assert.equal(result.status, 403);
    assert.equal(upstreamCalls, 0);
  }
});

test("unauthenticated and unavailable requests stop before upstream fetch", async () => {
  for (const auth of [
    { status: "unauthenticated" } as const,
    { status: "unavailable" } as const,
  ]) {
    let upstreamCalls = 0;
    const result = await executeVerifiedGlobalProxy(auth, async () => {
      upstreamCalls += 1;
      return new Response(null, { status: 200 });
    });
    assert.equal(result.status, auth.status === "unavailable" ? 503 : 401);
    assert.equal(upstreamCalls, 0);
  }
});

test("verified super admin headers derive only from the Flask principal", async () => {
  let forwarded: DashboardPrincipal | undefined;
  const expected = principal("super_admin");
  const result = await executeVerifiedGlobalProxy(
    { status: "authenticated", principal: expected },
    async (verified) => {
      forwarded = verified;
      return new Response(null, { status: 204 });
    },
  );
  assert.equal(result.status, 204);
  assert.deepEqual(forwarded, expected);
});
