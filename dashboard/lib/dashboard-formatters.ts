export function formatDateTime(value?: string | null) {
  if (!value) return "ยังไม่มีข้อมูล";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "ไม่ทราบเวลา";
  return new Intl.DateTimeFormat("th-TH", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function formatDuration(seconds?: number) {
  if (!seconds || seconds < 0) return "0 นาที";
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return hours ? `${hours} ชม. ${minutes} นาที` : `${minutes} นาที`;
}

export function maskLineUserId(userId: string) {
  if (userId.length <= 8) return "••••••••";
  return `${userId.slice(0, 4)}••••••${userId.slice(-4)}`;
}

export function safeHostname(value: string) {
  if (!value) return "";
  try {
    return new URL(value).hostname;
  } catch {
    return "";
  }
}
