import "server-only";

import type { DashboardAuthMode } from "./auth-mode.ts";
import { buildFlaskSessionDeletionCookie } from "./session-cookie.ts";

export const LEGACY_SESSION_COOKIE_NAME = "mtc_dashboard_session";
export const LEGACY_MAX_AGE_SECONDS = 8 * 60 * 60;

type CookieOptions = {
  httpOnly: true;
  sameSite: "lax";
  secure: boolean;
  path: "/";
  maxAge: number;
};

export type AuthCookie = {
  name: string;
  value: string;
  options: CookieOptions;
};

export type AuthCookieStore = {
  set(name: string, value: string, options: CookieOptions): unknown;
};

export type LoginCookieTransition = {
  mode: DashboardAuthMode;
  cookie: AuthCookie;
};

function legacyCookieOptions(production: boolean, maxAge: number): CookieOptions {
  return {
    httpOnly: true,
    sameSite: "lax",
    secure: production,
    path: "/",
    maxAge,
  };
}

export function buildLegacySessionCookie(value: string): AuthCookie {
  if (!value) throw new Error("Legacy session value is invalid.");
  return {
    name: LEGACY_SESSION_COOKIE_NAME,
    value,
    options: legacyCookieOptions(
      process.env.NODE_ENV === "production",
      LEGACY_MAX_AGE_SECONDS,
    ),
  };
}

export function buildLegacySessionDeletionCookie(
  production = process.env.NODE_ENV === "production",
): AuthCookie {
  return {
    name: LEGACY_SESSION_COOKIE_NAME,
    value: "",
    options: legacyCookieOptions(production, 0),
  };
}

function writeCookie(store: AuthCookieStore, cookie: AuthCookie): void {
  store.set(cookie.name, cookie.value, cookie.options);
}

export function applyLoginCookieTransition(
  store: AuthCookieStore,
  transition: LoginCookieTransition | null,
  production = process.env.NODE_ENV === "production",
): void {
  if (!transition) return;
  writeCookie(store, transition.cookie);
  writeCookie(
    store,
    transition.mode === "flask"
      ? buildLegacySessionDeletionCookie(production)
      : buildFlaskSessionDeletionCookie(production),
  );
}

export function clearAllAuthCookies(
  store: AuthCookieStore,
  production = process.env.NODE_ENV === "production",
): void {
  writeCookie(store, buildLegacySessionDeletionCookie(production));
  writeCookie(store, buildFlaskSessionDeletionCookie(production));
}
