import "server-only";

export type DashboardAuthMode = "flask" | "legacy";

export class AuthConfigurationError extends Error {
  constructor() {
    super("Dashboard authentication configuration is invalid.");
    this.name = "AuthConfigurationError";
  }
}

export function parseDashboardAuthMode(
  configuredValue: string | undefined,
): DashboardAuthMode {
  if (configuredValue === undefined || configuredValue.trim() === "") {
    return "legacy";
  }
  const normalized = configuredValue.trim().toLowerCase();
  if (normalized === "flask" || normalized === "legacy") {
    return normalized;
  }
  throw new AuthConfigurationError();
}

export function getDashboardAuthMode(): DashboardAuthMode {
  return parseDashboardAuthMode(process.env.DASHBOARD_AUTH_MODE);
}
