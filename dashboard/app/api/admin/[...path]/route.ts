import { NextRequest } from "next/server";
import { isAdminProxyMutation } from "@/lib/admin-proxy-policy";
import { getLegacySessionPrincipal } from "@/lib/auth";
import {
  AuthConfigurationError,
  getDashboardAuthMode,
} from "@/lib/auth-mode";
import { getCurrentFlaskPrincipal } from "@/lib/current-principal";
import type { DashboardPrincipal as FlaskPrincipal } from "@/lib/flask-auth-types";
import { executeVerifiedGlobalProxy } from "@/lib/global-admin-gate";
import {
  OriginValidationError,
  requireSameOriginMutation,
} from "@/lib/same-origin";

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "content-encoding",
  "content-length",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

type TransitionalPrincipal = {
  adminId: string;
  role: "super_admin" | "class_admin";
  classIds: string[];
};

function safeError(status: number, code: string, message: string) {
  return Response.json(
    { error: { code, message } },
    { status, headers: { "Cache-Control": "no-store" } },
  );
}

async function forwardUpstream(
  request: NextRequest,
  context: RouteContext,
  principal: TransitionalPrincipal,
) {
  const apiBase = process.env.MTC_BOT_API_BASE_URL || "http://127.0.0.1:5000";
  const apiToken = process.env.MTC_DASHBOARD_API_TOKEN || "";
  if (!apiToken) {
    return safeError(503, "DASHBOARD_NOT_CONFIGURED", "ระบบข้อมูลยังตั้งค่าไม่สมบูรณ์");
  }

  const { path } = await context.params;
  let upstreamUrl: URL;
  try {
    upstreamUrl = new URL(`/api/admin/${path.join("/")}`, apiBase);
    if (!["http:", "https:"].includes(upstreamUrl.protocol)) throw new Error();
  } catch {
    return safeError(503, "DASHBOARD_NOT_CONFIGURED", "ระบบข้อมูลยังตั้งค่าไม่สมบูรณ์");
  }
  const upstreamTimeoutMs = path.join("/") === "paperless-capture" ? 35_000 : 8_000;
  request.nextUrl.searchParams.forEach((value, key) => upstreamUrl.searchParams.set(key, value));

  const headers = new Headers();
  headers.set("Authorization", `Bearer ${apiToken}`);
  headers.set("Accept", "application/json");
  headers.set("X-MTC-Admin-Id", principal.adminId);
  headers.set("X-MTC-Admin-Role", principal.role);
  headers.set("X-MTC-Admin-Classes", principal.classIds.join(","));
  if (request.headers.get("content-type")) {
    headers.set("Content-Type", request.headers.get("content-type") || "application/json");
  }

  const init: RequestInit = {
    method: request.method,
    headers,
    cache: "no-store",
  };
  if (isAdminProxyMutation(request.method)) {
    init.body = await request.arrayBuffer();
  }

  let upstream: Response;
  try {
    upstream = await fetch(upstreamUrl, {
      ...init,
      signal: AbortSignal.timeout(upstreamTimeoutMs),
    });
  } catch {
    return safeError(
      502,
      "BOT_API_UNREACHABLE",
      "ไม่สามารถเชื่อมต่อบริการข้อมูลได้ในขณะนี้ กรุณาลองอีกครั้ง",
    );
  }
  const responseHeaders = new Headers();
  upstream.headers.forEach((value, key) => {
    if (!HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
      responseHeaders.set(key, value);
    }
  });
  responseHeaders.set("Cache-Control", "no-store");

  const contentType = upstream.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    const payload = await upstream.json().catch(() => null);
    return Response.json(
      payload ?? { error: { code: "INVALID_UPSTREAM_JSON", message: "Bot API returned invalid JSON." } },
      {
        status: payload === null ? 502 : upstream.status,
        headers: responseHeaders,
      },
    );
  }

  return Response.json(
    { error: { code: "INVALID_UPSTREAM_RESPONSE", message: "Bot API did not return JSON." } },
    { status: 502, headers: responseHeaders },
  );
}

function transitionalPrincipal(principal: FlaskPrincipal): TransitionalPrincipal {
  return {
    adminId: principal.account_id,
    role: "super_admin",
    classIds: principal.class_ids,
  };
}

async function proxy(request: NextRequest, context: RouteContext) {
  let mode;
  try {
    mode = getDashboardAuthMode();
    if (isAdminProxyMutation(request.method)) {
      requireSameOriginMutation(request, mode);
    }
  } catch (caught) {
    if (caught instanceof OriginValidationError) {
      return safeError(403, "ORIGIN_NOT_ALLOWED", "คำขอนี้ไม่ได้มาจากเว็บไซต์ที่อนุญาต");
    }
    if (caught instanceof AuthConfigurationError) {
      return safeError(503, "AUTH_NOT_CONFIGURED", "ระบบเข้าสู่ระบบยังตั้งค่าไม่สมบูรณ์");
    }
    return safeError(503, "AUTH_SERVICE_UNAVAILABLE", "ระบบยืนยันตัวตนไม่พร้อมใช้งานในขณะนี้");
  }

  if (mode === "legacy") {
    const principal = await getLegacySessionPrincipal();
    if (!principal) {
      return safeError(401, "UNAUTHORIZED", "Dashboard session is required.");
    }
    return forwardUpstream(request, context, principal);
  }

  const auth = await getCurrentFlaskPrincipal();
  return executeVerifiedGlobalProxy(auth, (principal) =>
    forwardUpstream(request, context, transitionalPrincipal(principal)),
  );
}

export async function GET(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

export async function POST(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

export async function PUT(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}
