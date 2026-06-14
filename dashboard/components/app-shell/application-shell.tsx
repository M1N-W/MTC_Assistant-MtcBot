"use client";

import {
  Bot,
  BookOpenCheck,
  BrainCircuit,
  Gauge,
  Link,
  LogOut,
  Menu,
  MessageSquareText,
  Settings,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { ReactNode, useRef, useState } from "react";
import type { DashboardSection } from "@/lib/dashboard-sections";
import type { Workspace } from "@/lib/dashboard-types";
import { Drawer, StatusBadge } from "@/components/ui/dashboard-ui";

const classroomItems: Array<[DashboardSection, string, LucideIcon]> = [
  ["overview", "ภาพรวม", Gauge],
  ["members", "บัญชี LINE", Users],
  ["homework", "การบ้าน", BookOpenCheck],
  ["announcements", "ประกาศ", MessageSquareText],
  ["resources", "ลิงก์และสื่อ", Link],
];

const systemItems: Array<[DashboardSection, string, LucideIcon]> = [
  ["system", "ระบบ", Settings],
  ["ai-settings", "การตั้งค่า AI", BrainCircuit],
];

export function ApplicationShell({
  activeSection,
  onNavigate,
  workspaces,
  selectedWorkspace,
  onWorkspaceChange,
  workspaceLoading,
  workspaceError,
  children,
}: {
  activeSection: DashboardSection;
  onNavigate: (section: DashboardSection) => void;
  workspaces: Workspace[];
  selectedWorkspace: Workspace | null;
  onWorkspaceChange: (classId: string) => void;
  workspaceLoading: boolean;
  workspaceError: boolean;
  children: ReactNode;
}) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const menuRef = useRef<HTMLButtonElement>(null);

  async function logout() {
    await fetch("/api/logout", { method: "POST" });
    window.location.href = "/login";
  }

  function navigate(section: DashboardSection) {
    onNavigate(section);
    setDrawerOpen(false);
  }

  function renderNavigation(idPrefix: string) {
    return (
      <>
      <WorkspaceSelector
        id={`${idPrefix}-workspace`}
        workspaces={workspaces}
        selected={selectedWorkspace}
        onChange={onWorkspaceChange}
        loading={workspaceLoading}
        error={workspaceError}
      />
      <NavigationGroup label="ห้องเรียน" items={classroomItems} active={activeSection} onNavigate={navigate} />
      <NavigationGroup label="การดูแลระบบ" items={systemItems} active={activeSection} onNavigate={navigate} />
      <button type="button" className="sidebar-logout" onClick={logout}>
        <LogOut size={18} />
        ออกจากระบบ
      </button>
      </>
    );
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <Brand />
        {renderNavigation("desktop")}
      </aside>
      <header className="mobile-app-bar">
        <Brand compact />
        <button ref={menuRef} type="button" className="icon-button mobile-menu-button" onClick={() => setDrawerOpen(true)} aria-label="เปิดเมนู">
          <Menu size={22} />
        </button>
      </header>
      <Drawer open={drawerOpen} title="เมนู MTC Dashboard" onClose={() => setDrawerOpen(false)} returnFocusRef={menuRef}>
        <div className="drawer-content">{renderNavigation("mobile")}</div>
      </Drawer>
      <div className="app-content">{children}</div>
    </main>
  );
}

function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`app-brand ${compact ? "app-brand-compact" : ""}`}>
      <span><Bot size={21} /></span>
      <div>
        <strong>MTC Assistant</strong>
        <small>MTC Dashboard</small>
      </div>
    </div>
  );
}

function WorkspaceSelector({
  id,
  workspaces,
  selected,
  onChange,
  loading,
  error,
}: {
  id: string;
  workspaces: Workspace[];
  selected: Workspace | null;
  onChange: (classId: string) => void;
  loading: boolean;
  error: boolean;
}) {
  return (
    <section className="workspace-selector" aria-label="ห้องสำหรับการตั้งค่า">
      <label htmlFor={id}>ห้องสำหรับการตั้งค่า</label>
      <p>ใช้กับลิงก์พื้นฐานและการตั้งค่า AI</p>
      <select
        id={id}
        value={selected?.class_id ?? ""}
        onChange={(event) => onChange(event.target.value)}
        disabled={loading || error || workspaces.length === 0}
      >
        <option value="">{loading ? "กำลังโหลด..." : error ? "ไม่สามารถโหลดได้" : "ไม่มีพื้นที่จัดการ"}</option>
        {workspaces.map((workspace) => (
          <option key={workspace.class_id} value={workspace.class_id}>
            {workspace.label}
          </option>
        ))}
      </select>
      {selected ? (
        <div className="workspace-term">
          <span>{selected.active_term_label}</span>
          <StatusBadge tone="success">กำลังใช้งาน</StatusBadge>
        </div>
      ) : null}
    </section>
  );
}

function NavigationGroup({
  label,
  items,
  active,
  onNavigate,
}: {
  label: string;
  items: Array<[DashboardSection, string, LucideIcon]>;
  active: DashboardSection;
  onNavigate: (section: DashboardSection) => void;
}) {
  return (
    <nav className="navigation-group" aria-label={label}>
      <p>{label}</p>
      {items.map(([section, text, Icon]) => (
        <button
          key={section}
          type="button"
          onClick={() => onNavigate(section)}
          className={active === section ? "navigation-item active" : "navigation-item"}
          aria-current={active === section ? "page" : undefined}
        >
          <Icon size={18} />
          {text}
        </button>
      ))}
    </nav>
  );
}
