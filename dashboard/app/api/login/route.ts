import { NextRequest } from "next/server";
import {
  createLegacySessionCookie,
  isLegacyAuthConfigured,
  verifyLegacyPassword,
} from "@/lib/auth";
import { applyLoginCookieTransition } from "@/lib/auth-cookies";
import {
  AuthConfigurationError,
  getDashboardAuthMode,
} from "@/lib/auth-mode";
import {
  createFlaskAuthClient,
  FlaskAuthConfigurationError,
} from "@/lib/flask-auth-client";
import { authenticateDashboardLogin } from "@/lib/login-authority";
import {
  buildFlaskSessionCookie,
} from "@/lib/session-cookie";
import {
  OriginValidationError,
  requireSameOriginMutation,
} from "@/lib/same-origin";
import { cookies } from "next/headers";

const NO_STORE_HEADERS = { "Cache-Control": "no-store" };
const MAX_LOGIN_BODY_BYTES = 8 * 1024;

function error(status: number, code: string, message: string) {
  return Response.json(
    { error: { code, message } },
    { status, headers: NO_STORE_HEADERS },
  );
}

export async function POST(request: NextRequest) {
  let mode;
  try {
    mode = getDashboardAuthMode();
    requireSameOriginMutation(request, mode);
  } catch (caught) {
    if (caught instanceof AuthConfigurationError) {
      return error(503, "AUTH_NOT_CONFIGURED", "ระบบเข้าสู่ระบบยังตั้งค่าไม่สมบูรณ์");
    }
    if (caught instanceof OriginValidationError) {
      return error(403, "ORIGIN_NOT_ALLOWED", "คำขอนี้ไม่ได้มาจากเว็บไซต์ที่อนุญาต");
    }
    return error(503, "AUTH_UNAVAILABLE", "ระบบเข้าสู่ระบบไม่พร้อมใช้งานในขณะนี้");
  }

  const contentLength = Number(request.headers.get("Content-Length") || "0");
  if (!Number.isFinite(contentLength) || contentLength > MAX_LOGIN_BODY_BYTES) {
    return error(413, "REQUEST_TOO_LARGE", "ข้อมูลเข้าสู่ระบบมีขนาดไม่ถูกต้อง");
  }
  const contentType = request.headers.get("Content-Type") || "";
  if (!contentType.toLowerCase().startsWith("application/json")) {
    return error(415, "UNSUPPORTED_MEDIA_TYPE", "รูปแบบข้อมูลเข้าสู่ระบบไม่ถูกต้อง");
  }

  const body = await request.json().catch(() => null);
  if (!body || typeof body !== "object") {
    return error(401, "UNAUTHORIZED", "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง");
  }

  const password =
    "password" in body && typeof body.password === "string" ? body.password : "";

  const username =
    "username" in body && typeof body.username === "string"
      ? body.username.trim()
      : "";
  if (
    !password ||
    password.length > 256 ||
    (mode === "flask" && (!username || username.length > 64))
  ) {
    return error(401, "UNAUTHORIZED", "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง");
  }

  try {
    const result = await authenticateDashboardLogin(
      { mode, username, password },
      {
        legacyConfigured: isLegacyAuthConfigured,
        verifyLegacyPassword,
        flaskLogin: (loginUsername, loginPassword) =>
          createFlaskAuthClient().login(loginUsername, loginPassword),
      },
    );
    if (result.status === "misconfigured") {
      return error(503, "AUTH_NOT_CONFIGURED", "ระบบเข้าสู่ระบบยังตั้งค่าไม่สมบูรณ์");
    }
    if (result.status === "unauthenticated") {
      return error(
        401,
        "UNAUTHORIZED",
        mode === "flask"
          ? "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"
          : "รหัสผ่านไม่ถูกต้อง กรุณาลองอีกครั้ง",
      );
    }
    if (result.status === "unavailable") {
      return error(
        503,
        "AUTH_SERVICE_UNAVAILABLE",
        "ระบบยืนยันตัวตนไม่พร้อมใช้งานในขณะนี้ กรุณาลองใหม่ภายหลัง",
      );
    }
    if (result.status === "legacy_authenticated") {
      const cookieStore = await cookies();
      applyLoginCookieTransition(cookieStore, {
        mode: "legacy",
        cookie: createLegacySessionCookie(),
      });
      return Response.json(
        { data: { status: "authenticated" } },
        { status: 200, headers: NO_STORE_HEADERS },
      );
    }
    const sessionCookie = buildFlaskSessionCookie(
      result.sessionToken,
      result.expiresAt,
    );
    const cookieStore = await cookies();
    applyLoginCookieTransition(cookieStore, {
      mode: "flask",
      cookie: sessionCookie,
    });
    return Response.json(
      {
        data: {
          status: "authenticated",
          principal: result.principal,
          redirectTo: "/",
        },
      },
      { status: 200, headers: NO_STORE_HEADERS },
    );
  } catch (caught) {
    if (caught instanceof FlaskAuthConfigurationError) {
      return error(503, "AUTH_NOT_CONFIGURED", "ระบบเข้าสู่ระบบยังตั้งค่าไม่สมบูรณ์");
    }
    return error(
      503,
      "AUTH_SERVICE_UNAVAILABLE",
      "ระบบยืนยันตัวตนไม่พร้อมใช้งานในขณะนี้ กรุณาลองใหม่ภายหลัง",
    );
  }
}
