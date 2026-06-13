import { createHmac, timingSafeEqual } from "node:crypto";
import { cookies } from "next/headers";

const COOKIE_NAME = "mtc_dashboard_session";
const MAX_AGE_SECONDS = 60 * 60 * 8;

export type DashboardPrincipal = {
  adminId: string;
  role: "super_admin" | "class_admin";
  classIds: string[];
};

type SessionPayload = DashboardPrincipal & {
  issuedAt: number;
};

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

export async function createSession() {
  const payload: SessionPayload = {
    ...configuredPrincipal(),
    issuedAt: Date.now(),
  };
  const encoded = Buffer.from(JSON.stringify(payload)).toString("base64url");
  const value = `${encoded}.${sign(encoded)}`;
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
  return Boolean(await getSessionPrincipal());
}

export async function getSessionPrincipal(): Promise<DashboardPrincipal | null> {
  if (!isAuthConfigured()) {
    return null;
  }
  const cookieStore = await cookies();
  const raw = cookieStore.get(COOKIE_NAME)?.value || "";
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
  if (!Number.isFinite(ageMs) || ageMs < 0 || ageMs > MAX_AGE_SECONDS * 1000) {
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
