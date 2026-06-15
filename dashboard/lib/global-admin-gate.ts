import "server-only";

import type {
  DashboardPrincipal,
  PrincipalResult,
} from "./flask-auth-types.ts";

export type GlobalDashboardAccess = "allowed" | "limited" | "denied";

export function authorizeGlobalDashboard(
  principal: DashboardPrincipal,
): GlobalDashboardAccess {
  if (principal.role === "super_admin") return "allowed";
  if (["student", "teacher", "class_admin"].includes(principal.role)) {
    return "limited";
  }
  return "denied";
}

function safeError(status: number, code: string, message: string): Response {
  return Response.json(
    { error: { code, message } },
    { status, headers: { "Cache-Control": "no-store" } },
  );
}

export async function executeVerifiedGlobalProxy(
  auth: PrincipalResult,
  forward: (principal: DashboardPrincipal) => Promise<Response>,
): Promise<Response> {
  if (auth.status === "unavailable" || auth.status === "misconfigured") {
    return safeError(
      503,
      "AUTH_SERVICE_UNAVAILABLE",
      "ระบบยืนยันตัวตนไม่พร้อมใช้งานในขณะนี้",
    );
  }
  if (auth.status !== "authenticated") {
    return safeError(401, "UNAUTHORIZED", "Dashboard session is required.");
  }
  if (authorizeGlobalDashboard(auth.principal) !== "allowed") {
    return safeError(403, "FORBIDDEN", "บัญชีนี้ไม่มีสิทธิ์ใช้เครื่องมือส่วนกลาง");
  }
  return forward(auth.principal);
}
