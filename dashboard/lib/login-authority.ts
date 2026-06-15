import "server-only";

import type { DashboardAuthMode } from "./auth-mode.ts";
import type { LoginResult } from "./flask-auth-types.ts";

type LoginInput = {
  mode: DashboardAuthMode;
  username: string;
  password: string;
};

type LoginDependencies = {
  legacyConfigured: () => boolean;
  verifyLegacyPassword: (password: string) => boolean;
  flaskLogin: (username: string, password: string) => Promise<LoginResult>;
};

export type DashboardLoginAuthorityResult =
  | LoginResult
  | { status: "legacy_authenticated" }
  | { status: "misconfigured" };

export async function authenticateDashboardLogin(
  input: LoginInput,
  dependencies: LoginDependencies,
): Promise<DashboardLoginAuthorityResult> {
  if (input.mode === "legacy") {
    if (!dependencies.legacyConfigured()) return { status: "misconfigured" };
    return dependencies.verifyLegacyPassword(input.password)
      ? { status: "legacy_authenticated" }
      : { status: "unauthenticated" };
  }
  return dependencies.flaskLogin(input.username, input.password);
}
