import "server-only";

import {
  AuthConfigurationError,
  type DashboardAuthMode,
} from "./auth-mode.ts";

export class OriginValidationError extends Error {
  constructor() {
    super("The request origin is not allowed.");
    this.name = "OriginValidationError";
  }
}

type MutationOriginInput = {
  authMode: DashboardAuthMode;
  nodeEnv: string | undefined;
  publicOrigin: string | undefined;
  requestOrigin: string | null;
  requestUrl: string;
  requestHost?: string | null;
  forwardedHost?: string | null;
  forwardedProto?: string | null;
  secFetchSite: string | null;
};

type LogoutOriginInput = Omit<MutationOriginInput, "authMode">;

function parseOrigin(value: string): URL {
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    throw new OriginValidationError();
  }
  if (
    !["http:", "https:"].includes(parsed.protocol) ||
    parsed.username ||
    parsed.password ||
    parsed.pathname !== "/" ||
    parsed.search ||
    parsed.hash
  ) {
    throw new OriginValidationError();
  }
  return parsed;
}

function configuredPublicOrigin(
  value: string | undefined,
  productionFlaskMode: boolean,
): string | null {
  const trimmed = value?.trim() || "";
  if (!trimmed) {
    if (productionFlaskMode) throw new AuthConfigurationError();
    return null;
  }
  let parsed: URL;
  try {
    parsed = parseOrigin(trimmed);
  } catch {
    throw new AuthConfigurationError();
  }
  if (productionFlaskMode && parsed.protocol !== "https:") {
    throw new AuthConfigurationError();
  }
  return parsed.origin;
}

function optionalPublicOrigin(value: string | undefined): string | null {
  const trimmed = value?.trim() || "";
  if (!trimmed) return null;
  try {
    return parseOrigin(trimmed).origin;
  } catch {
    return null;
  }
}

function isLocalhost(hostname: string): boolean {
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "[::1]";
}

function firstForwardedValue(value: string | null | undefined): string {
  return value?.split(",")[0]?.trim() || "";
}

function activeRequestOrigin(input: MutationOriginInput, requestUrl: URL): URL {
  const host =
    firstForwardedValue(input.forwardedHost) ||
    firstForwardedValue(input.requestHost);
  const protocol =
    firstForwardedValue(input.forwardedProto) ||
    requestUrl.protocol.replace(":", "");
  if (!host || !["http", "https"].includes(protocol)) return requestUrl;
  try {
    return parseOrigin(`${protocol}://${host}`);
  } catch {
    throw new OriginValidationError();
  }
}

export function validateMutationOrigin(input: MutationOriginInput): void {
  const production = input.nodeEnv === "production";
  const trustedConfiguredOrigin = configuredPublicOrigin(
    input.publicOrigin,
    production && input.authMode === "flask",
  );
  if (!input.requestOrigin) throw new OriginValidationError();
  if (input.secFetchSite === "cross-site") throw new OriginValidationError();

  const requestOrigin = parseOrigin(input.requestOrigin).origin;
  let requestUrl: URL;
  try {
    requestUrl = new URL(input.requestUrl);
  } catch {
    throw new OriginValidationError();
  }

  const activeOrigin = activeRequestOrigin(input, requestUrl);
  const trustedOrigin = trustedConfiguredOrigin || activeOrigin.origin;
  if (!trustedConfiguredOrigin && !production && !isLocalhost(activeOrigin.hostname)) {
    throw new OriginValidationError();
  }
  if (requestOrigin !== trustedOrigin) throw new OriginValidationError();
}

export function validateLogoutOrigin(input: LogoutOriginInput): void {
  if (!input.requestOrigin) throw new OriginValidationError();
  if (input.secFetchSite === "cross-site") throw new OriginValidationError();
  const requestOrigin = parseOrigin(input.requestOrigin).origin;
  let requestUrl: URL;
  try {
    requestUrl = new URL(input.requestUrl);
  } catch {
    throw new OriginValidationError();
  }
  const trustedOrigin =
    optionalPublicOrigin(input.publicOrigin) ||
    activeRequestOrigin(input as MutationOriginInput, requestUrl).origin;
  if (requestOrigin !== trustedOrigin) throw new OriginValidationError();
}

export function requireSameOriginMutation(
  request: Request,
  authMode: DashboardAuthMode,
): void {
  validateMutationOrigin({
    authMode,
    nodeEnv: process.env.NODE_ENV,
    publicOrigin: process.env.DASHBOARD_PUBLIC_ORIGIN,
    requestOrigin: request.headers.get("Origin"),
    requestUrl: request.url,
    requestHost: request.headers.get("Host"),
    forwardedHost: request.headers.get("X-Forwarded-Host"),
    forwardedProto: request.headers.get("X-Forwarded-Proto"),
    secFetchSite: request.headers.get("Sec-Fetch-Site"),
  });
}

export function requireSameOriginLogout(request: Request): void {
  validateLogoutOrigin({
    nodeEnv: process.env.NODE_ENV,
    publicOrigin: process.env.DASHBOARD_PUBLIC_ORIGIN,
    requestOrigin: request.headers.get("Origin"),
    requestUrl: request.url,
    requestHost: request.headers.get("Host"),
    forwardedHost: request.headers.get("X-Forwarded-Host"),
    forwardedProto: request.headers.get("X-Forwarded-Proto"),
    secFetchSite: request.headers.get("Sec-Fetch-Site"),
  });
}
