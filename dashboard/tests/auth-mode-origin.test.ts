import assert from "node:assert/strict";
import test from "node:test";

import {
  AuthConfigurationError,
  parseDashboardAuthMode,
} from "../lib/auth-mode.ts";
import {
  OriginValidationError,
  validateLogoutOrigin,
  validateMutationOrigin,
} from "../lib/same-origin.ts";

test("auth mode defaults to legacy", () => {
  assert.equal(parseDashboardAuthMode(undefined), "legacy");
});

test("auth mode accepts normalized explicit values", () => {
  assert.equal(parseDashboardAuthMode(" FLASK "), "flask");
  assert.equal(parseDashboardAuthMode("LEGACY"), "legacy");
});

test("auth mode rejects unknown explicit values without fallback", () => {
  assert.throws(
    () => parseDashboardAuthMode("shared"),
    AuthConfigurationError,
  );
});

test("same-origin guard accepts the configured production origin", () => {
  assert.doesNotThrow(() =>
    validateMutationOrigin({
      authMode: "flask",
      nodeEnv: "production",
      publicOrigin: "https://dashboard.example.test",
      requestOrigin: "https://dashboard.example.test",
      requestUrl: "https://dashboard.example.test/api/login",
      secFetchSite: "same-origin",
    }),
  );
});

test("same-origin guard rejects cross-origin and malformed origins", () => {
  for (const requestOrigin of [
    "https://attacker.example.test",
    "not-an-origin",
    "https://dashboard.example.test.evil.invalid",
  ]) {
    assert.throws(
      () =>
        validateMutationOrigin({
          authMode: "flask",
          nodeEnv: "production",
          publicOrigin: "https://dashboard.example.test",
          requestOrigin,
          requestUrl: "https://dashboard.example.test/api/login",
          secFetchSite: "cross-site",
        }),
      OriginValidationError,
    );
  }
});

test("production Flask mode requires an explicit HTTPS public origin", () => {
  for (const publicOrigin of [undefined, "", "http://dashboard.example.test"]) {
    assert.throws(
      () =>
        validateMutationOrigin({
          authMode: "flask",
          nodeEnv: "production",
          publicOrigin,
          requestOrigin: "https://dashboard.example.test",
          requestUrl: "https://dashboard.example.test/api/login",
          secFetchSite: "same-origin",
        }),
      AuthConfigurationError,
    );
  }
});

test("local development accepts only the active localhost origin", () => {
  assert.doesNotThrow(() =>
    validateMutationOrigin({
      authMode: "flask",
      nodeEnv: "development",
      publicOrigin: undefined,
      requestOrigin: "http://localhost:3000",
      requestUrl: "http://localhost:3000/api/login",
      secFetchSite: "same-origin",
    }),
  );
  assert.throws(
    () =>
      validateMutationOrigin({
        authMode: "flask",
        nodeEnv: "development",
        publicOrigin: undefined,
        requestOrigin: "http://192.0.2.10:3000",
        requestUrl: "http://localhost:3000/api/login",
        secFetchSite: "same-site",
      }),
    OriginValidationError,
  );
});

test("legacy production fallback compares against the actual request host", () => {
  assert.doesNotThrow(() =>
    validateMutationOrigin({
      authMode: "legacy",
      nodeEnv: "production",
      publicOrigin: undefined,
      requestOrigin: "http://127.0.0.1:31988",
      requestUrl: "http://localhost:31988/api/login",
      requestHost: "127.0.0.1:31988",
      forwardedProto: "http",
      secFetchSite: "same-origin",
    }),
  );
});

test("invalid-mode logout accepts same-origin using a valid public origin", () => {
  assert.doesNotThrow(() =>
    validateLogoutOrigin({
      nodeEnv: "production",
      publicOrigin: "https://dashboard.example.test",
      requestOrigin: "https://dashboard.example.test",
      requestUrl: "https://internal.example.test/api/logout",
      requestHost: "internal.example.test",
      forwardedProto: "https",
      secFetchSite: "same-origin",
    }),
  );
});

test("invalid-mode logout falls back to active request origin when public origin is invalid", () => {
  assert.doesNotThrow(() =>
    validateLogoutOrigin({
      nodeEnv: "production",
      publicOrigin: "not-an-origin",
      requestOrigin: "https://dashboard.example.test",
      requestUrl: "http://localhost:3000/api/logout",
      forwardedHost: "dashboard.example.test",
      forwardedProto: "https",
      secFetchSite: "same-origin",
    }),
  );
});

test("invalid-mode logout rejects explicit cross-origin and malformed origins", () => {
  for (const requestOrigin of [
    "https://attacker.example.test",
    "not-an-origin",
  ]) {
    assert.throws(
      () =>
        validateLogoutOrigin({
          nodeEnv: "production",
          publicOrigin: "https://dashboard.example.test",
          requestOrigin,
          requestUrl: "https://dashboard.example.test/api/logout",
          requestHost: "dashboard.example.test",
          forwardedProto: "https",
          secFetchSite:
            requestOrigin === "not-an-origin" ? "same-origin" : "cross-site",
        }),
      OriginValidationError,
    );
  }
});
