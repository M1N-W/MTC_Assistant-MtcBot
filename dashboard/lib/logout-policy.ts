import "server-only";

import type { DashboardAuthMode } from "./auth-mode.ts";

export function logoutRevocationToken(
  mode: DashboardAuthMode | null,
  flaskCookieValue: string | undefined,
): string | undefined {
  return mode === "flask" && flaskCookieValue
    ? flaskCookieValue
    : undefined;
}
