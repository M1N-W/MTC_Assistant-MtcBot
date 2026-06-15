import { cookies } from "next/headers";
import { NextRequest } from "next/server";

import { getDashboardAuthMode } from "@/lib/auth-mode";
import { clearAllAuthCookies } from "@/lib/auth-cookies";
import {
  createFlaskAuthClient,
  FlaskAuthConfigurationError,
} from "@/lib/flask-auth-client";
import { logoutRevocationToken } from "@/lib/logout-policy";
import { FLASK_SESSION_COOKIE_NAME } from "@/lib/session-cookie";
import {
  OriginValidationError,
  requireSameOriginLogout,
} from "@/lib/same-origin";

const NO_STORE_HEADERS = { "Cache-Control": "no-store" };

export async function POST(request: NextRequest) {
  try {
    requireSameOriginLogout(request);
  } catch (caught) {
    if (caught instanceof OriginValidationError) {
      return Response.json(
        { error: { code: "ORIGIN_NOT_ALLOWED", message: "คำขอนี้ไม่ได้มาจากเว็บไซต์ที่อนุญาต" } },
        { status: 403, headers: NO_STORE_HEADERS },
      );
    }
    return Response.json(
      { error: { code: "ORIGIN_NOT_ALLOWED", message: "คำขอนี้ไม่ได้มาจากเว็บไซต์ที่อนุญาต" } },
      { status: 403, headers: NO_STORE_HEADERS },
    );
  }

  let mode = null;
  try {
    mode = getDashboardAuthMode();
  } catch {
    mode = null;
  }
  const cookieStore = await cookies();
  const sessionToken = logoutRevocationToken(
    mode,
    cookieStore.get(FLASK_SESSION_COOKIE_NAME)?.value,
  );
  let revocationConfirmed = false;
  if (sessionToken) {
    try {
      const result = await createFlaskAuthClient().logout(sessionToken);
      revocationConfirmed =
        result.status === "signed_out" || result.status === "unauthenticated";
    } catch (caught) {
      if (!(caught instanceof FlaskAuthConfigurationError)) {
        revocationConfirmed = false;
      }
    }
  }
  clearAllAuthCookies(cookieStore);
  return Response.json(
    {
      data: {
        status: "signed_out",
        redirectTo: "/login",
        revocationConfirmed,
      },
    },
    { status: 200, headers: NO_STORE_HEADERS },
  );
}
