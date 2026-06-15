import assert from "node:assert/strict";
import test from "node:test";

import {
  FlaskAuthClient,
  FlaskAuthConfigurationError,
} from "../lib/flask-auth-client.ts";

const principal = {
  account_id: "account-fake",
  username: "fake.user",
  display_name: "ผู้ใช้ทดสอบ",
  role: "teacher",
  class_ids: ["mtc13"],
  capabilities: ["auth.session.read_self"],
  session_expires_at: "2026-06-15T12:00:00.000Z",
} as const;

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

test("Flask login sends service bearer server-side and validates response", async () => {
  let captured: Request | undefined;
  const client = new FlaskAuthClient({
    baseUrl: "https://bot.example.test",
    serviceToken: "service-secret",
    fetcher: async (input, init) => {
      captured = new Request(input, init);
      return response({
        data: {
          session_token: "x".repeat(43),
          expires_at: "2026-06-15T12:00:00.000Z",
          principal,
        },
      });
    },
  });

  const result = await client.login("fake.user", "fake password");
  assert.equal(result.status, "authenticated");
  assert.equal(captured?.url, "https://bot.example.test/api/admin/auth/login");
  assert.equal(captured?.headers.get("Authorization"), "Bearer service-secret");
  assert.equal(captured?.headers.get("X-MTC-Dashboard-Session"), null);
});

test("Flask me and logout send the opaque session only in the expected header", async () => {
  const requests: Request[] = [];
  const client = new FlaskAuthClient({
    baseUrl: "https://bot.example.test",
    serviceToken: "service-secret",
    fetcher: async (input, init) => {
      requests.push(new Request(input, init));
      return requests.length === 1
        ? response({ data: { principal } })
        : response({ data: { status: "signed_out" } });
    },
  });

  await client.me("y".repeat(43));
  await client.logout("y".repeat(43));
  assert.deepEqual(
    requests.map((request) => [
      request.method,
      request.headers.get("X-MTC-Dashboard-Session"),
    ]),
    [
      ["GET", "y".repeat(43)],
      ["POST", "y".repeat(43)],
    ],
  );
});

test("Flask client normalizes credential rejection, unavailable, malformed JSON, and timeout", async () => {
  const unauthorized = new FlaskAuthClient({
    baseUrl: "https://bot.example.test",
    serviceToken: "service-secret",
    fetcher: async () => response({ internal: "do not forward" }, 401),
  });
  assert.deepEqual(await unauthorized.login("fake.user", "wrong"), {
    status: "unauthenticated",
  });

  const unavailable = new FlaskAuthClient({
    baseUrl: "https://bot.example.test",
    serviceToken: "service-secret",
    fetcher: async () => response({ internal: "do not forward" }, 503),
  });
  assert.deepEqual(await unavailable.me("z".repeat(43)), {
    status: "unavailable",
  });

  const malformed = new FlaskAuthClient({
    baseUrl: "https://bot.example.test",
    serviceToken: "service-secret",
    fetcher: async () =>
      new Response("{", {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
  });
  assert.deepEqual(await malformed.me("z".repeat(43)), {
    status: "unavailable",
  });

  const timedOut = new FlaskAuthClient({
    baseUrl: "https://bot.example.test",
    serviceToken: "service-secret",
    timeoutMs: 1,
    fetcher: async (_input, init) =>
      new Promise((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () =>
          reject(new DOMException("aborted", "AbortError")),
        );
      }),
  });
  assert.deepEqual(await timedOut.me("z".repeat(43)), {
    status: "unavailable",
  });
});

test("Flask client rejects invalid configuration without exposing values", () => {
  for (const baseUrl of [
    "",
    "not-a-url",
    "ftp://bot.example.test",
    "https://user:password@bot.example.test",
    "https://bot.example.test?target=internal",
  ]) {
    assert.throws(
      () =>
        new FlaskAuthClient({
          baseUrl,
          serviceToken: "service-secret",
          fetcher: async () => response({}),
        }),
      FlaskAuthConfigurationError,
    );
  }
  assert.throws(
    () =>
      new FlaskAuthClient({
        baseUrl: "https://bot.example.test",
        serviceToken: "",
        fetcher: async () => response({}),
      }),
    FlaskAuthConfigurationError,
  );
});
