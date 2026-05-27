import { NextRequest } from "next/server";
import { createSession, isAuthConfigured, verifyPassword } from "@/lib/auth";

export async function POST(request: NextRequest) {
  if (!isAuthConfigured()) {
    return Response.json(
      { error: { code: "AUTH_NOT_CONFIGURED", message: "Dashboard auth is not configured." } },
      { status: 503 },
    );
  }

  const body = await request.json().catch(() => null);
  const password = typeof body?.password === "string" ? body.password : "";
  if (!verifyPassword(password)) {
    return Response.json(
      { error: { code: "UNAUTHORIZED", message: "Invalid dashboard password." } },
      { status: 401 },
    );
  }

  await createSession();
  return Response.json({ data: { status: "authenticated" } }, { status: 200 });
}
