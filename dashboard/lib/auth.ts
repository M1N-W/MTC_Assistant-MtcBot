import { createHmac, timingSafeEqual } from "node:crypto";
import { cookies } from "next/headers";

const COOKIE_NAME = "mtc_dashboard_session";
const MAX_AGE_SECONDS = 60 * 60 * 8;

function sessionSecret() {
  return process.env.DASHBOARD_SESSION_SECRET || "";
}

function expectedPassword() {
  return process.env.DASHBOARD_PASSWORD || "";
}

function sign(value: string) {
  return createHmac("sha256", sessionSecret()).update(value).digest("hex");
}

function safeEqual(left: string, right: string) {
  const leftBuffer = Buffer.from(left);
  const rightBuffer = Buffer.from(right);
  return leftBuffer.length === rightBuffer.length && timingSafeEqual(leftBuffer, rightBuffer);
}

export function isAuthConfigured() {
  return Boolean(sessionSecret() && expectedPassword());
}

export function verifyPassword(password: string) {
  const configured = expectedPassword();
  return Boolean(configured) && safeEqual(password, configured);
}

export async function createSession() {
  const issuedAt = Date.now().toString();
  const value = `${issuedAt}.${sign(issuedAt)}`;
  const cookieStore = await cookies();
  cookieStore.set(COOKIE_NAME, value, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    maxAge: MAX_AGE_SECONDS,
    path: "/",
  });
}

export async function clearSession() {
  const cookieStore = await cookies();
  cookieStore.delete(COOKIE_NAME);
}

export async function isAuthenticated() {
  if (!isAuthConfigured()) {
    return false;
  }
  const cookieStore = await cookies();
  const raw = cookieStore.get(COOKIE_NAME)?.value || "";
  const [issuedAt, signature] = raw.split(".");
  if (!issuedAt || !signature || sign(issuedAt) !== signature) {
    return false;
  }
  const ageMs = Date.now() - Number(issuedAt);
  return Number.isFinite(ageMs) && ageMs >= 0 && ageMs <= MAX_AGE_SECONDS * 1000;
}
