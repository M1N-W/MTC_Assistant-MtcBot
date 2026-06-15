import "server-only";

import type { FlaskAuthClient } from "./flask-auth-client.ts";
import type { PrincipalResult } from "./flask-auth-types.ts";

export async function resolveFlaskPrincipal(
  sessionToken: string | undefined,
  client: FlaskAuthClient,
): Promise<PrincipalResult> {
  if (!sessionToken) return { status: "unauthenticated", reason: "missing" };
  const result = await client.me(sessionToken);
  return result.status === "unauthenticated"
    ? { status: "unauthenticated", reason: "invalid" }
    : result;
}
