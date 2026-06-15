import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("logout reads revocation material only from the Flask cookie and clears both cookies", async () => {
  const source = await readFile(
    new URL("../app/api/logout/route.ts", import.meta.url),
    "utf8",
  );
  assert.match(
    source,
    /cookieStore\.get\(FLASK_SESSION_COOKIE_NAME\)\?\.value/,
  );
  assert.match(source, /clearAllAuthCookies\(cookieStore\)/);
  assert.doesNotMatch(source, /request\.json\(/);
  assert.doesNotMatch(source, /request\.nextUrl\.searchParams/);
  assert.doesNotMatch(source, /X-MTC-Dashboard-Session/);
});

test("logout treats invalid auth mode as local sign-out without fallback", async () => {
  const source = await readFile(
    new URL("../app/api/logout/route.ts", import.meta.url),
    "utf8",
  );
  assert.match(source, /mode = getDashboardAuthMode\(\)/);
  assert.match(source, /catch \{\s*mode = null;\s*\}/);
  assert.match(source, /logoutRevocationToken\(\s*mode,/);
  assert.doesNotMatch(source, /mode = "legacy"/);
  assert.doesNotMatch(source, /mode = "flask"/);
});
