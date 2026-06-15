export type DashboardRole =
  | "student"
  | "teacher"
  | "class_admin"
  | "super_admin"
  | "unknown";

export type DashboardPrincipal = {
  account_id: string;
  username: string;
  display_name: string | null;
  role: DashboardRole;
  class_ids: string[];
  capabilities: string[];
  session_expires_at: string;
};

export type PrincipalResult =
  | { status: "authenticated"; principal: DashboardPrincipal }
  | { status: "unauthenticated"; reason?: "missing" | "invalid" }
  | { status: "forbidden" }
  | { status: "unavailable" }
  | { status: "misconfigured" };

export type LoginResult =
  | {
      status: "authenticated";
      sessionToken: string;
      expiresAt: string;
      principal: DashboardPrincipal;
    }
  | { status: "unauthenticated" }
  | { status: "unavailable" };

export type LogoutResult =
  | { status: "signed_out" }
  | { status: "unauthenticated" }
  | { status: "unavailable" };
