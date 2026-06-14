"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { ApplicationShell } from "@/components/app-shell/application-shell";
import { AccountsSection } from "@/components/sections/accounts-section";
import { AnnouncementsSection } from "@/components/sections/announcements-section";
import { HomeworkSection } from "@/components/sections/homework-section";
import { OverviewSection } from "@/components/sections/overview-section";
import { SystemSection } from "@/components/sections/system-section";
import { GeneralLinksEditor } from "@/components/general-links-editor";
import { AISettingsEditor } from "@/components/ai-settings-editor";
import { apiGet } from "@/lib/dashboard-api";
import {
  parseDashboardSection,
  type DashboardSection,
} from "@/lib/dashboard-sections";
import type { Workspace } from "@/lib/dashboard-types";
import {
  storeWorkspaceId,
  useStoredWorkspaceId,
} from "@/lib/dashboard-workspaces";

export function DashboardShell() {
  const [activeSection, setActiveSection] = useState<DashboardSection>("overview");
  const storedWorkspaceId = useStoredWorkspaceId();
  const workspacesQuery = useQuery({
    queryKey: ["workspaces"],
    queryFn: () => apiGet<{ workspaces: Workspace[] }>("workspaces"),
  });
  const workspaces = useMemo(
    () => workspacesQuery.data?.workspaces || [],
    [workspacesQuery.data],
  );
  const selectedWorkspace = useMemo(
    () => workspaces.find((workspace) => workspace.class_id === storedWorkspaceId) || workspaces[0] || null,
    [storedWorkspaceId, workspaces],
  );

  useEffect(() => {
    if (!workspacesQuery.isSuccess || storedWorkspaceId === null) return;
    const nextWorkspaceId = selectedWorkspace?.class_id || "";
    if (storedWorkspaceId !== nextWorkspaceId) storeWorkspaceId(nextWorkspaceId);
  }, [selectedWorkspace, storedWorkspaceId, workspacesQuery.isSuccess]);

  useEffect(() => {
    function syncSectionFromHash() {
      const section = parseDashboardSection(window.location.hash);
      setActiveSection(section);
      if (window.location.hash !== `#${section}`) {
        window.history.replaceState(null, "", `#${section}`);
      }
    }
    syncSectionFromHash();
    window.addEventListener("hashchange", syncSectionFromHash);
    window.addEventListener("popstate", syncSectionFromHash);
    return () => {
      window.removeEventListener("hashchange", syncSectionFromHash);
      window.removeEventListener("popstate", syncSectionFromHash);
    };
  }, []);

  function navigate(section: DashboardSection) {
    setActiveSection(section);
    const nextHash = `#${section}`;
    if (window.location.hash !== nextHash) {
      window.history.pushState(null, "", nextHash);
    }
  }

  function selectWorkspace(classId: string) {
    if (workspaces.some((workspace) => workspace.class_id === classId)) {
      storeWorkspaceId(classId);
    }
  }

  return (
    <ApplicationShell
      activeSection={activeSection}
      onNavigate={navigate}
      workspaces={workspaces}
      selectedWorkspace={selectedWorkspace}
      onWorkspaceChange={selectWorkspace}
      workspaceLoading={workspacesQuery.isLoading}
      workspaceError={workspacesQuery.isError}
    >
      {activeSection === "overview" ? <OverviewSection onNavigate={navigate} /> : null}
      {activeSection === "members" ? <AccountsSection /> : null}
      {activeSection === "homework" ? <HomeworkSection /> : null}
      {activeSection === "announcements" ? <AnnouncementsSection /> : null}
      {activeSection === "resources" ? <GeneralLinksEditor key={selectedWorkspace?.class_id} workspace={selectedWorkspace} /> : null}
      {activeSection === "system" ? <SystemSection /> : null}
      {activeSection === "ai-settings" ? <AISettingsEditor key={selectedWorkspace?.class_id} workspace={selectedWorkspace} /> : null}
    </ApplicationShell>
  );
}
