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

const WORKSPACE_STORAGE_KEY = "mtc-dashboard:workspace:v2";

export function DashboardShell() {
  const [activeSection, setActiveSection] = useState<DashboardSection>("overview");
  const [selectedClassId, setSelectedClassId] = useState("");
  const workspacesQuery = useQuery({
    queryKey: ["workspaces"],
    queryFn: async () => {
      const data = await apiGet<{ workspaces: Workspace[] }>("workspaces");
      const stored = window.localStorage.getItem(WORKSPACE_STORAGE_KEY) || "";
      const validStored = data.workspaces.some((workspace) => workspace.class_id === stored);
      setSelectedClassId((current) => {
        const validCurrent = data.workspaces.some((workspace) => workspace.class_id === current);
        return validCurrent ? current : validStored ? stored : data.workspaces[0]?.class_id || "";
      });
      return data;
    },
  });
  const workspaces = useMemo(
    () => workspacesQuery.data?.workspaces || [],
    [workspacesQuery.data],
  );
  const selectedWorkspace = useMemo(
    () => workspaces.find((workspace) => workspace.class_id === selectedClassId) || workspaces[0] || null,
    [selectedClassId, workspaces],
  );

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
    setSelectedClassId(classId);
    window.localStorage.setItem(WORKSPACE_STORAGE_KEY, classId);
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
      {activeSection === "overview" ? <OverviewSection workspace={selectedWorkspace} onNavigate={navigate} /> : null}
      {activeSection === "members" ? <AccountsSection workspace={selectedWorkspace} /> : null}
      {activeSection === "homework" ? <HomeworkSection workspace={selectedWorkspace} /> : null}
      {activeSection === "announcements" ? <AnnouncementsSection workspace={selectedWorkspace} /> : null}
      {activeSection === "resources" ? <GeneralLinksEditor key={selectedWorkspace?.class_id} workspace={selectedWorkspace} /> : null}
      {activeSection === "system" ? <SystemSection workspace={selectedWorkspace} /> : null}
      {activeSection === "ai-settings" ? <AISettingsEditor key={selectedWorkspace?.class_id} workspace={selectedWorkspace} /> : null}
    </ApplicationShell>
  );
}
