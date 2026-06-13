export const DASHBOARD_SECTIONS = [
  "overview",
  "members",
  "homework",
  "announcements",
  "resources",
  "system",
  "ai-settings",
] as const;

export type DashboardSection = (typeof DASHBOARD_SECTIONS)[number];

export function parseDashboardSection(hash: string): DashboardSection {
  const section = hash.replace(/^#/, "");
  return DASHBOARD_SECTIONS.includes(section as DashboardSection)
    ? (section as DashboardSection)
    : "overview";
}
