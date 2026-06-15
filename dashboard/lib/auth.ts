import { createHmac, timingSafeEqual } from "node:crypto";
import { cookies } from "next/headers";
import "server-only";

import {
  LEGACY_MAX_AGE_SECONDS,
  LEGACY_SESSION_COOKIE_NAME,
  buildLegacySessionCookie,
} from "./auth-cookies.ts";

export { LEGACY_SESSION_COOKIE_NAME };

export type DashboardPrincipal = {
  adminId: string;
  role: "super_admin" | "class_admin";
  classIds: string[];
};

type SessionPayload = DashboardPrincipal & {
  issuedAt: number;
};

function legacySessionSecret() {
  return process.env.DASHBOARD_SESSION_SECRET || "";
}

function expectedLegacyPassword() {
  return process.env.DASHBOARD_PASSWORD || "";
}

function sign(value: string) {
  return createHmac("sha256", legacySessionSecret()).update(value).digest("hex");
}

function safeEqual(left: string, right: string) {
  const leftBuffer = Buffer.from(left);
  const rightBuffer = Buffer.from(right);
  return leftBuffer.length === rightBuffer.length && timingSafeEqual(leftBuffer, rightBuffer);
}

export function isLegacyAuthConfigured() {
  return Boolean(legacySessionSecret() && expectedLegacyPassword());
}

export function verifyLegacyPassword(password: string) {
  const configured = expectedLegacyPassword();
  return Boolean(configured) && safeEqual(password, configured);
}

function configuredPrincipal(): DashboardPrincipal {
  const configuredRole = process.env.DASHBOARD_ADMIN_ROLE;
  const role = configuredRole === "class_admin" ? "class_admin" : "super_admin";
  const classIds = (process.env.DASHBOARD_ALLOWED_CLASS_IDS || "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
  return {
    adminId: process.env.DASHBOARD_ADMIN_ID || "dashboard-admin",
    role,
    classIds,
  };
}

export function createLegacySessionCookie() {
  const payload: SessionPayload = {
    ...configuredPrincipal(),
    issuedAt: Date.now(),
  };
  const encoded = Buffer.from(JSON.stringify(payload)).toString("base64url");
  const value = `${encoded}.${sign(encoded)}`;
  return buildLegacySessionCookie(value);
}

export async function isLegacyAuthenticated() {
  return Boolean(await getLegacySessionPrincipal());
}

export async function getLegacySessionPrincipal(): Promise<DashboardPrincipal | null> {
  if (!isLegacyAuthConfigured()) {
    return null;
  }
  const cookieStore = await cookies();
  const raw = cookieStore.get(LEGACY_SESSION_COOKIE_NAME)?.value || "";
  const [encoded, signature] = raw.split(".");
  if (!encoded || !signature || !safeEqual(sign(encoded), signature)) {
    return null;
  }
  let payload: SessionPayload;
  try {
    payload = JSON.parse(Buffer.from(encoded, "base64url").toString("utf8")) as SessionPayload;
  } catch {
    return null;
  }
  const ageMs = Date.now() - Number(payload.issuedAt);
  if (!Number.isFinite(ageMs) || ageMs < 0 || ageMs > LEGACY_MAX_AGE_SECONDS * 1000) {
    return null;
  }
  if (
    !payload.adminId ||
    !["super_admin", "class_admin"].includes(payload.role) ||
    !Array.isArray(payload.classIds)
  ) {
    return null;
  }
  return {
    adminId: payload.adminId,
    role: payload.role,
    classIds: payload.classIds.filter((value) => typeof value === "string"),
  };
}
