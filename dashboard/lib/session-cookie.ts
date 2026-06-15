import "server-only";

export const FLASK_SESSION_COOKIE_NAME = "mtc_dashboard_flask_session";
export const MAX_FLASK_SESSION_AGE_SECONDS = 12 * 60 * 60;
const ISO_EXPIRY_PATTERN =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/;

type CookieOptions = {
  httpOnly: true;
  sameSite: "lax";
  secure: boolean;
  path: "/";
  maxAge: number;
};

export type SessionCookie = {
  name: typeof FLASK_SESSION_COOKIE_NAME;
  value: string;
  options: CookieOptions;
};

export function sessionMaxAgeSeconds(expiresAt: string, now = new Date()): number {
  if (
    typeof expiresAt !== "string" ||
    !ISO_EXPIRY_PATTERN.test(expiresAt.trim())
  ) {
    throw new Error("Session expiry is invalid.");
  }
  const expiryMs = Date.parse(expiresAt);
  const nowMs = now.getTime();
  if (!Number.isFinite(expiryMs) || !Number.isFinite(nowMs) || expiryMs <= nowMs) {
    throw new Error("Session expiry is invalid.");
  }
  const remainingSeconds = Math.floor((expiryMs - nowMs) / 1000);
  if (remainingSeconds < 1) throw new Error("Session expiry is invalid.");
  return Math.min(remainingSeconds, MAX_FLASK_SESSION_AGE_SECONDS);
}

function cookieOptions(production: boolean, maxAge: number): CookieOptions {
  return {
    httpOnly: true,
    sameSite: "lax",
    secure: production,
    path: "/",
    maxAge,
  };
}

export function buildFlaskSessionCookie(
  value: string,
  expiresAt: string,
  {
    now = new Date(),
    production = process.env.NODE_ENV === "production",
  }: { now?: Date; production?: boolean } = {},
): SessionCookie {
  if (typeof value !== "string" || !value) {
    throw new Error("Session value is invalid.");
  }
  return {
    name: FLASK_SESSION_COOKIE_NAME,
    value,
    options: cookieOptions(production, sessionMaxAgeSeconds(expiresAt, now)),
  };
}

export function buildFlaskSessionDeletionCookie(
  production = process.env.NODE_ENV === "production",
): SessionCookie {
  return {
    name: FLASK_SESSION_COOKIE_NAME,
    value: "",
    options: cookieOptions(production, 0),
  };
}
