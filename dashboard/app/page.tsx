import { redirect } from "next/navigation";
import { isAuthenticated } from "@/lib/auth";
import { DashboardShell } from "@/components/dashboard-shell";

export default async function HomePage() {
  if (!(await isAuthenticated())) {
    redirect("/login");
  }

  return <DashboardShell />;
}
