import "server-only";

import type {
  DashboardPrincipal,
  DashboardRole,
  LoginResult,
  LogoutResult,
  PrincipalResult,
} from "./flask-auth-types.ts";

const SESSION_PATTERN = /^[A-Za-z0-9_-]{43}$/;
const DEFAULT_TIMEOUT_MS = 5_000;

export class FlaskAuthConfigurationError extends Error {
  constructor() {
    super("Flask authentication service is not configured.");
    this.name = "FlaskAuthConfigurationError";
  }
}

type FlaskAuthClientOptions = {
  baseUrl: string | undefined;
  serviceToken: string | undefined;
  fetcher?: typeof fetch;
  timeoutMs?: number;
};

function configuredBaseUrl(value: string | undefined): URL {
  try {
    const url = new URL(value || "");
    if (
      !["http:", "https:"].includes(url.protocol) ||
      url.username ||
      url.password ||
      url.search ||
      url.hash
    ) {
      throw new Error("unsupported protocol");
    }
    return url;
  } catch {
    throw new FlaskAuthConfigurationError();
  }
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null
    ? (value as Record<string, unknown>)
    : null;
}

function parsePrincipal(value: unknown): DashboardPrincipal | null {
  const record = asRecord(value);
  if (!record) return null;
  const roleValue = record.role;
  const role: DashboardRole =
    typeof roleValue === "string" &&
    ["student", "teacher", "class_admin", "super_admin"].includes(roleValue)
      ? (roleValue as DashboardRole)
      : "unknown";
  if (
    typeof record.account_id !== "string" ||
    !record.account_id ||
    typeof record.username !== "string" ||
    !record.username ||
    (record.display_name !== null && typeof record.display_name !== "string") ||
    !Array.isArray(record.class_ids) ||
    !record.class_ids.every((item) => typeof item === "string") ||
    !Array.isArray(record.capabilities) ||
    !record.capabilities.every((item) => typeof item === "string") ||
    typeof record.session_expires_at !== "string"
  ) {
    return null;
  }
  return {
    account_id: record.account_id,
    username: record.username,
    display_name: record.display_name,
    role,
    class_ids: record.class_ids,
    capabilities: record.capabilities,
    session_expires_at: record.session_expires_at,
  };
}

async function safeJson(response: Response): Promise<Record<string, unknown> | null> {
  try {
    return asRecord(await response.json());
  } catch {
    return null;
  }
}

export class FlaskAuthClient {
  private readonly baseUrl: URL;
  private readonly serviceToken: string;
  private readonly fetcher: typeof fetch;
  private readonly timeoutMs: number;

  constructor(options: FlaskAuthClientOptions) {
    this.baseUrl = configuredBaseUrl(options.baseUrl);
    if (!options.serviceToken) throw new FlaskAuthConfigurationError();
    this.serviceToken = options.serviceToken;
    this.fetcher = options.fetcher || fetch;
    this.timeoutMs = options.timeoutMs || DEFAULT_TIMEOUT_MS;
  }

  async login(username: string, password: string): Promise<LoginResult> {
    const response = await this.request("/api/admin/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
      headers: { "Content-Type": "application/json" },
    });
    if (!response) return { status: "unavailable" };
    if (response.status === 401 || response.status === 403) {
      return { status: "unauthenticated" };
    }
    if (!response.ok) return { status: "unavailable" };
    const payload = await safeJson(response);
    const data = asRecord(payload?.data);
    const principal = parsePrincipal(data?.principal);
    if (
      !data ||
      typeof data.session_token !== "string" ||
      !SESSION_PATTERN.test(data.session_token) ||
      typeof data.expires_at !== "string" ||
      !principal
    ) {
      return { status: "unavailable" };
    }
    return {
      status: "authenticated",
      sessionToken: data.session_token,
      expiresAt: data.expires_at,
      principal,
    };
  }

  async me(sessionToken: string): Promise<PrincipalResult> {
    if (!SESSION_PATTERN.test(sessionToken)) return { status: "unauthenticated" };
    const response = await this.request("/api/admin/auth/me", {
      method: "GET",
      headers: { "X-MTC-Dashboard-Session": sessionToken },
    });
    if (!response) return { status: "unavailable" };
    if (response.status === 401) return { status: "unauthenticated" };
    if (response.status === 403) return { status: "forbidden" };
    if (!response.ok) return { status: "unavailable" };
    const payload = await safeJson(response);
    const data = asRecord(payload?.data);
    const principal = parsePrincipal(data?.principal);
    return principal
      ? { status: "authenticated", principal }
      : { status: "unavailable" };
  }

  async logout(sessionToken: string): Promise<LogoutResult> {
    if (!SESSION_PATTERN.test(sessionToken)) return { status: "unauthenticated" };
    const response = await this.request("/api/admin/auth/logout", {
      method: "POST",
      headers: { "X-MTC-Dashboard-Session": sessionToken },
    });
    if (!response) return { status: "unavailable" };
    if (response.status === 401) return { status: "unauthenticated" };
    return response.ok ? { status: "signed_out" } : { status: "unavailable" };
  }

  private async request(path: string, init: RequestInit): Promise<Response | null> {
    const headers = new Headers(init.headers);
    headers.set("Authorization", `Bearer ${this.serviceToken}`);
    headers.set("Accept", "application/json");
    try {
      return await this.fetcher(new URL(path, this.baseUrl), {
        ...init,
        headers,
        cache: "no-store",
        signal: AbortSignal.timeout(this.timeoutMs),
      });
    } catch {
      return null;
    }
  }
}

export function createFlaskAuthClient(): FlaskAuthClient {
  return new FlaskAuthClient({
    baseUrl: process.env.MTC_BOT_API_BASE_URL,
    serviceToken: process.env.MTC_DASHBOARD_API_TOKEN,
  });
}
