import { redirect } from "next/navigation";
import { isLegacyAuthenticated } from "@/lib/auth";
import {
  AuthConfigurationError,
  getDashboardAuthMode,
} from "@/lib/auth-mode";
import { getCurrentFlaskPrincipal } from "@/lib/current-principal";
import { authorizeGlobalDashboard } from "@/lib/global-admin-gate";
import { DashboardShell } from "@/components/dashboard-shell";
import {
  AuthUnavailableState,
  InvalidSessionState,
  LimitedRoleState,
} from "@/components/auth-state";

export default async function HomePage() {
  let mode;
  try {
    mode = getDashboardAuthMode();
  } catch (caught) {
    if (caught instanceof AuthConfigurationError) {
      return <AuthUnavailableState />;
    }
    throw caught;
  }

  if (mode === "legacy") {
    if (!(await isLegacyAuthenticated())) redirect("/login");
    return <DashboardShell />;
  }

  const auth = await getCurrentFlaskPrincipal();
  if (auth.status === "unavailable" || auth.status === "misconfigured") {
    return <AuthUnavailableState />;
  }
  if (auth.status === "unauthenticated" && auth.reason === "missing") {
    redirect("/login");
  }
  if (auth.status !== "authenticated") {
    return <InvalidSessionState />;
  }
  const access = authorizeGlobalDashboard(auth.principal);
  if (access === "allowed") {
    return <DashboardShell />;
  }
  if (access === "limited") {
    return <LimitedRoleState principal={auth.principal} />;
  }
  return <InvalidSessionState />;
}

export const dynamic = "force-dynamic";
export const revalidate = 0;
