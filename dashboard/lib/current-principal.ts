import "server-only";

import { cookies } from "next/headers";

import {
  createFlaskAuthClient,
  FlaskAuthConfigurationError,
} from "./flask-auth-client.ts";
import type { PrincipalResult } from "./flask-auth-types.ts";
import { resolveFlaskPrincipal } from "./principal-resolution.ts";
import { FLASK_SESSION_COOKIE_NAME } from "./session-cookie.ts";

export async function getCurrentFlaskPrincipal(): Promise<PrincipalResult> {
  const cookieStore = await cookies();
  const sessionToken = cookieStore.get(FLASK_SESSION_COOKIE_NAME)?.value;
  try {
    return await resolveFlaskPrincipal(sessionToken, createFlaskAuthClient());
  } catch (error) {
    if (error instanceof FlaskAuthConfigurationError) {
      return { status: "misconfigured" };
    }
    return { status: "unavailable" };
  }
}
