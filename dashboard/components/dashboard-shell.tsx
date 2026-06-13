"use client";

import {
  Activity,
  AlertTriangle,
  Ban,
  BellRing,
  BookOpenCheck,
  Bot,
  Camera,
  Check,
  CheckCircle2,
  CircleGauge,
  Clock3,
  Copy,
  FileScan,
  Gauge,
  GraduationCap,
  Inbox,
  KeyRound,
  Leaf,
  LineChart as LineChartIcon,
  LogOut,
  MessageSquareText,
  Radar,
  RefreshCcw,
  Search,
  Send,
  ShieldAlert,
  Sparkles,
  Sprout,
  Users,
  Wifi,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { CSSProperties, FormEvent, useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { GeneralLinksEditor } from "@/components/general-links-editor";
import { AISettingsEditor } from "@/components/ai-settings-editor";
import {
  parseDashboardSection,
  type DashboardSection,
} from "@/lib/dashboard-sections";

type ServiceMap = {
  line: boolean;
  gemini: boolean;
  firebase: boolean;
  broadcast: boolean;
};

type Metrics = {
  uptime_seconds: number;
  total_requests: number;
  total_errors: number;
  error_rate_percent: number;
  avg_response_time_ms: number;
  total_users?: number;
  total_messages?: number;
  banned_users?: number;
};

type Homework = {
  id: string;
  subject?: string;
  detail?: string;
  due_date?: string;
  created_at?: string;
};

type BroadcastRecord = {
  id: string;
  message?: string;
  sent_count?: number;
  failed_count?: number;
  timestamp?: string;
  success?: boolean;
};

type SustainabilityImpact = {
  active_students: number;
  expected_class_size: number;
  homework_count: number;
  broadcast_count: number;
  broadcast_recipients: number;
  automated_request_count: number;
  paper_saved_sheets: number;
  admin_minutes_saved: number;
  admin_hours_saved: number;
  co2_saved_grams: number;
  equal_access_rate_percent: number;
  assumptions: Record<string, string | number>;
};

type PaperlessCaptureResult = {
  analysis: {
    title: string;
    summary: string[];
    homework_candidates: string[];
    keywords: string[];
    paperless_value: string;
    raw_text?: string;
  };
  image_size_bytes: number;
  mime_type: string;
};

type Overview = {
  generated_at: string;
  services: ServiceMap;
  metrics: Metrics;
  counts: {
    registered_users: number;
    rate_limit_tracked_users: number;
    active_homework_preview: number;
    banned_users: number;
    recent_broadcasts: number;
  };
  sustainability?: SustainabilityImpact;
  homework_preview: Homework[];
  recent_broadcasts: BroadcastRecord[];
};

type UserRow = {
  user_id: string;
};

type BlacklistRow = {
  user_id: string;
  banned_at: string;
  banned_by: string;
  reason: string;
  is_permanent: boolean;
};

type ApiErrorPayload = {
  error?: {
    code?: unknown;
    message?: unknown;
  };
};

type BanPayload = {
  userId: string;
  reason: string;
};

const MAX_CAPTURE_BYTES = 6 * 1024 * 1024;
const ALLOWED_CAPTURE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

const tooltipStyle: CSSProperties = {
  background: "rgba(7, 23, 19, 0.92)",
  border: "1px solid rgba(34, 211, 238, 0.22)",
  borderRadius: 6,
  boxShadow: "0 18px 45px rgba(7, 23, 19, 0.26)",
  fontVariantNumeric: "tabular-nums",
  color: "#ecfeff",
};

const tooltipLabelStyle: CSSProperties = {
  color: "#a3e635",
  fontWeight: 700,
};

class DashboardApiError extends Error {
  status: number;
  code: string;

  constructor(message: string, status: number, code: string) {
    super(message);
    this.name = "DashboardApiError";
    this.status = status;
    this.code = code;
  }
}

function isApiErrorPayload(payload: unknown): payload is ApiErrorPayload {
  return typeof payload === "object" && payload !== null && "error" in payload;
}

function getApiError(payload: unknown, status: number) {
  const apiError = isApiErrorPayload(payload) ? payload.error : undefined;
  const message =
    typeof apiError?.message === "string" && apiError.message.trim()
      ? apiError.message
      : "ไม่สามารถเชื่อมต่อระบบได้ กรุณาลองอีกครั้ง";
  const code =
    typeof apiError?.code === "string" && apiError.code.trim()
      ? apiError.code
      : `HTTP_${status}`;
  return new DashboardApiError(message, status, code);
}

function validationError(message: string) {
  return new DashboardApiError(message, 422, "VALIDATION_ERROR");
}

function validateCaptureFile(file: File | null) {
  if (!file) {
    throw validationError("กรุณาเลือกภาพก่อนเริ่มวิเคราะห์");
  }
  if (!ALLOWED_CAPTURE_TYPES.has(file.type)) {
    throw validationError("รองรับเฉพาะไฟล์ PNG, JPEG และ WEBP");
  }
  if (file.size > MAX_CAPTURE_BYTES) {
    throw validationError("ไฟล์ภาพต้องมีขนาดไม่เกิน 6 MB");
  }
  return file;
}

function getPayloadData<T>(payload: unknown, status: number): T {
  if (typeof payload === "object" && payload !== null && "data" in payload) {
    const data = (payload as { data?: unknown }).data;
    if (data !== undefined) {
      return data as T;
    }
  }
  throw new DashboardApiError(
    "ข้อมูลที่ได้รับไม่สมบูรณ์ กรุณาอัปเดตข้อมูลอีกครั้ง",
    status,
    "INVALID_API_RESPONSE",
  );
}

async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`/api/admin/${path}`, { cache: "no-store" });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw getApiError(payload, response.status);
  }
  return getPayloadData<T>(payload, response.status);
}

async function apiSend<T>(path: string, method: "POST" | "DELETE", body?: unknown): Promise<T> {
  const response = await fetch(`/api/admin/${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw getApiError(payload, response.status);
  }
  return getPayloadData<T>(payload, response.status);
}

async function apiUpload<T>(path: string, file: File): Promise<T> {
  const formData = new FormData();
  formData.set("image", file);
  const response = await fetch(`/api/admin/${path}`, {
    method: "POST",
    body: formData,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw getApiError(payload, response.status);
  }
  return getPayloadData<T>(payload, response.status);
}

export function DashboardShell() {
  const queryClient = useQueryClient();
  const [activeSection, setActiveSection] = useState<DashboardSection>("overview");
  const [broadcastMessage, setBroadcastMessage] = useState("");
  const [broadcastPreview, setBroadcastPreview] = useState(false);
  const [banUserId, setBanUserId] = useState("");
  const [banReason, setBanReason] = useState("");
  const [captureFile, setCaptureFile] = useState<File | null>(null);
  const [captureResult, setCaptureResult] = useState<PaperlessCaptureResult | null>(null);

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

  const overviewQuery = useQuery({
    queryKey: ["overview"],
    queryFn: () => apiGet<Overview>("overview"),
  });
  const usersQuery = useQuery({
    queryKey: ["users"],
    queryFn: () => apiGet<{ items: UserRow[]; page: { total: number } }>("users?limit=100"),
  });
  const blacklistQuery = useQuery({
    queryKey: ["blacklist"],
    queryFn: () => apiGet<{ items: BlacklistRow[]; total: number }>("blacklist"),
  });

  const broadcastMutation = useMutation({
    mutationFn: (message: string) => {
      if (!message) {
        throw validationError("กรุณากรอกข้อความประกาศ");
      }
      if (message.length > 1000) {
        throw validationError("ข้อความประกาศต้องไม่เกิน 1,000 ตัวอักษร");
      }
      return apiSend("broadcasts", "POST", { message });
    },
    onSuccess: () => {
      setBroadcastMessage("");
      setBroadcastPreview(false);
      void queryClient.invalidateQueries({ queryKey: ["overview"] });
    },
  });

  const banMutation = useMutation({
    mutationFn: ({ userId, reason }: BanPayload) => {
      if (!userId) {
        throw validationError("กรุณากรอก LINE User ID");
      }
      if (!reason) {
        throw validationError("กรุณากรอกเหตุผล");
      }
      if (reason.length > 240) {
        throw validationError("เหตุผลต้องไม่เกิน 240 ตัวอักษร");
      }
      return apiSend("blacklist", "POST", { user_id: userId, reason });
    },
    onSuccess: () => {
      setBanUserId("");
      setBanReason("");
      void queryClient.invalidateQueries({ queryKey: ["blacklist"] });
      void queryClient.invalidateQueries({ queryKey: ["overview"] });
    },
  });

  const captureMutation = useMutation({
    mutationFn: (file: File | null) =>
      apiUpload<PaperlessCaptureResult>("paperless-capture", validateCaptureFile(file)),
    onSuccess: (data) => {
      setCaptureResult(data);
      void queryClient.invalidateQueries({ queryKey: ["overview"] });
    },
  });

  const unbanMutation = useMutation({
    mutationFn: (userId: string) => apiSend(`blacklist/${encodeURIComponent(userId)}`, "DELETE"),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["blacklist"] });
      void queryClient.invalidateQueries({ queryKey: ["overview"] });
    },
  });

  const overview = overviewQuery.data;
  const metrics = overview?.metrics;
  const sustainability = overview?.sustainability;
  const isOverviewLoading = overviewQuery.isLoading || overviewQuery.isFetching;

  const chartData = useMemo(() => {
    const total = metrics?.total_requests || 0;
    const errors = metrics?.total_errors || 0;
    return [
      { label: "คำขอ", value: total },
      { label: "ข้อความ", value: metrics?.total_messages || 0 },
      { label: "ข้อผิดพลาด", value: errors },
      { label: "สมาชิก", value: overview?.counts.registered_users || 0 },
    ];
  }, [metrics, overview]);



  async function logout() {
    await fetch("/api/logout", { method: "POST" });
    window.location.href = "/login";
  }

  function submitBroadcast(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = broadcastMessage.trim();
    if (!message) {
      broadcastMutation.mutate(message);
      return;
    }
    setBroadcastPreview(true);
  }

  function confirmBroadcast() {
    broadcastMutation.mutate(broadcastMessage.trim());
  }

  function submitBan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const userId = banUserId.trim();
    const reason = banReason.trim();
    banMutation.mutate({ userId, reason });
  }

  function submitCapture(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    captureMutation.mutate(captureFile);
  }

  function navigateTo(section: DashboardSection) {
    setActiveSection(section);
    const nextHash = `#${section}`;
    if (window.location.hash !== nextHash) {
      window.history.pushState(null, "", nextHash);
    }
  }

  const navItems: [DashboardSection, string, LucideIcon][] = [
    ["overview", "ภาพรวม", Gauge],
    ["members", "สมาชิก", GraduationCap],
    ["homework", "การบ้าน", BookOpenCheck],
    ["announcements", "ประกาศ", MessageSquareText],
    ["resources", "ลิงก์และสื่อ", BellRing],
    ["system", "ระบบ", Radar],
    ["ai-settings", "การตั้งค่า AI", KeyRound],
  ];

  const sectionHeadings: Record<DashboardSection, { title: string; description: string }> = {
    overview: {
      title: "ภาพรวมการใช้งาน",
      description: "ข้อมูลสำคัญและงานประจำของห้องเรียนในที่เดียว",
    },
    members: {
      title: "สมาชิก",
      description: "ค้นหาและตรวจสอบสมาชิกที่เชื่อมต่อกับ MTC Assistant",
    },
    homework: {
      title: "การบ้าน",
      description: "ติดตามการบ้านล่าสุดที่นักเรียนได้รับผ่าน LINE",
    },
    announcements: {
      title: "ประกาศ",
      description: "เขียน ตรวจสอบ และส่งประกาศถึงผู้ใช้ทั้งหมดในระบบ",
    },
    resources: {
      title: "ลิงก์และสื่อ",
      description: "จัดการลิงก์ที่นักเรียนใช้สำหรับการเรียนและงานประจำ",
    },
    system: {
      title: "ระบบ",
      description: "ตรวจสอบสถานะ บันทึกการใช้งาน และเครื่องมือขั้นสูง",
    },
    "ai-settings": {
      title: "การตั้งค่า AI",
      description: "จัดการการเชื่อมต่อ AI สำหรับผู้ดูแลระบบ",
    },
  };

  const sectionHeading = sectionHeadings[activeSection];

  return (
    <main className="dashboard-shell min-h-screen">
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="mission-grid" />
      </div>

      <div className="relative grid min-h-screen grid-cols-1 lg:grid-cols-[248px_1fr]">
        <aside className="glass-sidebar sticky top-0 z-20 border-b border-white/10 px-4 py-4 lg:h-screen lg:border-b-0 lg:border-r lg:p-4">
          <div className="brand-card">
            <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-[var(--color-primary)] text-white shadow-green">
              <Bot size={23} strokeWidth={2.5} />
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-white">MTC Assistant</p>
              <p className="text-xs font-medium text-emerald-100/70">MTC Dashboard</p>
            </div>
          </div>

          <nav className="mt-5 grid gap-2" aria-label="เมนูหลัก">
            {navItems.map(([section, label, Icon]) => (
              <button
                key={section}
                type="button"
                onClick={() => navigateTo(section)}
                className={`nav-item ${activeSection === section ? "nav-item-active" : ""}`}
                aria-current={activeSection === section ? "page" : undefined}
              >
                <Icon size={18} strokeWidth={2.2} />
                <span>{label}</span>
              </button>
            ))}
          </nav>

          <div className="impact-card mt-5 rounded-lg border border-white/10 bg-white/[0.04] p-3">
            <div className="flex items-center gap-2 text-xs font-semibold text-lime-200">
              <Leaf size={14} />
              Classroom OS
            </div>
            <p className="mt-2 text-xs leading-5 text-cyan-50/62">
              พื้นที่จัดการข้อมูลและงานประจำของห้องเรียน MTC Assistant
            </p>
          </div>

          <button type="button" onClick={logout} className="secondary-button mt-5 w-full">
            <LogOut size={17} />
            ออกจากระบบ
          </button>
        </aside>

        <section className="relative px-4 py-5 sm:px-6 lg:px-8 lg:py-8">
          <header className="mission-hero">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2 text-xs font-semibold text-emerald-100">
                <span className="h-2 w-2 rounded-full bg-lime-300 shadow-[0_0_18px_rgba(163,230,53,0.72)]" />
                MTC Assistant Dashboard
              </div>
              <h1 className="mt-3 text-3xl font-semibold tracking-[-0.01em] text-white">
                {sectionHeading.title}
              </h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-cyan-50/68">
                {sectionHeading.description}
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                void queryClient.invalidateQueries();
              }}
              className="primary-button"
            >
              <RefreshCcw size={17} />
              อัปเดตข้อมูล
            </button>
          </header>

          {overviewQuery.isError ? (
            <StatusNotice
              tone="danger"
              title="ไม่สามารถโหลดข้อมูลได้"
              text="กรุณาลองอัปเดตข้อมูลอีกครั้ง ข้อมูลที่คุณกรอกไว้ยังไม่ถูกลบ"
              error={overviewQuery.error as Error}
            />
          ) : null}

          {activeSection === "overview" ? (
            <>
              <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <Metric label="สมาชิกในระบบ" value={overview?.counts.registered_users ?? "--"} icon={GraduationCap} trend="ผู้ใช้ที่ลงทะเบียนแล้ว" loading={isOverviewLoading} />
                <Metric label="การบ้านล่าสุด" value={overview?.counts.active_homework_preview ?? "--"} icon={BookOpenCheck} trend="รายการที่แสดงอยู่" loading={isOverviewLoading} />
                <Metric label="ประกาศล่าสุด" value={overview?.counts.recent_broadcasts ?? "--"} icon={BellRing} trend="รายการส่งล่าสุด" loading={isOverviewLoading} />
                <Metric label="สถานะระบบ" value={overview && Object.values(overview.services).every(Boolean) ? "ปกติ" : "--"} icon={Wifi} trend="การทำงานของระบบ" loading={isOverviewLoading} />
              </div>

              <div className="mt-6 grid gap-5 xl:grid-cols-2">
                <Panel title="การบ้านล่าสุด" icon={BookOpenCheck}>
                  <HomeworkList items={overview?.homework_preview || []} loaded={Boolean(overview)} />
                  <button type="button" className="mini-button mt-4" onClick={() => navigateTo("homework")}>ดูการบ้านทั้งหมด</button>
                </Panel>
                <Panel title="ประกาศล่าสุด" icon={MessageSquareText}>
                  <BroadcastList items={overview?.recent_broadcasts || []} loaded={Boolean(overview)} />
                  <button type="button" className="mini-button mt-4" onClick={() => navigateTo("announcements")}>ส่งประกาศ</button>
                </Panel>
              </div>

              <div className="mt-6 grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
                <Panel title="สถานะระบบ" icon={Wifi}>
                  <ServiceStatus services={overview?.services} />
                </Panel>
                <Panel title="งานที่ใช้บ่อย" icon={Sparkles}>
                  <div className="quick-actions">
                    <button type="button" onClick={() => navigateTo("announcements")}><MessageSquareText size={18} />ส่งประกาศถึงผู้ใช้ทั้งหมด</button>
                    <button type="button" onClick={() => navigateTo("resources")}><BellRing size={18} />จัดการลิงก์และสื่อ</button>
                    <button type="button" onClick={() => navigateTo("members")}><Users size={18} />ค้นหาสมาชิก</button>
                  </div>
                </Panel>
              </div>
            </>
          ) : null}

          {activeSection === "members" ? (
            <div className="mt-6">
              <Panel title="รายชื่อสมาชิก" icon={Users}>
                <UsersTable data={usersQuery.data?.items || []} loading={usersQuery.isLoading || usersQuery.isFetching} />
              </Panel>
            </div>
          ) : null}

          {activeSection === "homework" ? (
            <div className="mt-6">
              <Panel title="การบ้านล่าสุด" action="แสดงข้อมูลจากระบบปัจจุบัน" icon={BookOpenCheck}>
                <HomeworkList items={overview?.homework_preview || []} loaded={Boolean(overview)} />
              </Panel>
            </div>
          ) : null}

          {activeSection === "announcements" ? (
            <div className="mt-6 grid gap-5 xl:grid-cols-[1.05fr_0.95fr]">
              <Panel title="ส่งประกาศถึงผู้ใช้ทั้งหมด" icon={MessageSquareText}>
                <form onSubmit={submitBroadcast} className="grid gap-3">
                  <label className="field-label" htmlFor="broadcast">ข้อความประกาศ</label>
                  <textarea
                    id="broadcast"
                    value={broadcastMessage}
                    onChange={(event) => {
                      setBroadcastMessage(event.target.value);
                      setBroadcastPreview(false);
                      broadcastMutation.reset();
                    }}
                    className="mission-input min-h-36 resize-y p-4 leading-6"
                    maxLength={1000}
                    placeholder="พิมพ์ข้อความที่ต้องการส่งถึงผู้ใช้ทั้งหมด"
                    required
                  />
                  <p className="text-xs text-slate-500">ข้อความนี้จะถูกส่งให้ผู้ใช้ทั้งหมดที่ลงทะเบียนในระบบผ่าน LINE โปรดตรวจสอบก่อนยืนยัน</p>
                  {!broadcastPreview ? (
                    <button className="primary-button" disabled={broadcastMutation.isPending}>
                      <Search size={17} />
                      ดูตัวอย่าง
                    </button>
                  ) : (
                    <div className="announcement-preview">
                      <p className="text-xs font-semibold text-slate-500">ตัวอย่างประกาศ</p>
                      <p className="mt-2 text-sm font-semibold text-amber-800">
                        ผู้รับ: ผู้ใช้ทั้งหมดที่ลงทะเบียนในระบบ
                      </p>
                      <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-emerald-950">{broadcastMessage.trim()}</p>
                      <div className="mt-4 flex flex-wrap gap-2">
                        <button type="button" className="primary-button" onClick={confirmBroadcast} disabled={broadcastMutation.isPending}>
                          <Send size={17} />
                          {broadcastMutation.isPending ? "กำลังส่งประกาศ..." : "ยืนยันการส่ง"}
                        </button>
                        <button type="button" className="mini-button" onClick={() => setBroadcastPreview(false)} disabled={broadcastMutation.isPending}>
                          แก้ไขข้อความ
                        </button>
                      </div>
                    </div>
                  )}
                  {broadcastMutation.isSuccess ? <StatusNotice tone="success" title="ส่งประกาศเรียบร้อยแล้ว" text="ระบบกำลังส่งข้อความถึงผู้ใช้ทั้งหมดในระบบ" /> : null}
                  {broadcastMutation.isError ? <StatusNotice tone="danger" title="ไม่สามารถส่งประกาศได้" text="ข้อความที่กรอกยังอยู่ กรุณาลองอีกครั้ง" error={broadcastMutation.error as Error} /> : null}
                </form>
              </Panel>
              <Panel title="ประกาศล่าสุด" icon={BellRing}>
                <BroadcastList items={overview?.recent_broadcasts || []} loaded={Boolean(overview)} />
              </Panel>
            </div>
          ) : null}

          {activeSection === "resources" ? <GeneralLinksEditor /> : null}
          {activeSection === "ai-settings" ? <AISettingsEditor /> : null}

          {activeSection === "system" ? (
            <>
              <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <Metric label="คำขอทั้งหมด" value={metrics?.total_requests ?? "--"} icon={Activity} trend="สถิติการใช้งาน" loading={isOverviewLoading} />
                <Metric label="เวลาตอบสนองเฉลี่ย" value={metrics ? `${metrics.avg_response_time_ms}ms` : "--"} icon={CircleGauge} trend="ประสิทธิภาพระบบ" loading={isOverviewLoading} />
                <Metric label="ข้อผิดพลาด" value={metrics?.total_errors ?? "--"} icon={AlertTriangle} trend="รายการที่ระบบตรวจพบ" loading={isOverviewLoading} />
                <Metric label="สมาชิกที่ระงับ" value={overview?.counts.banned_users ?? "--"} icon={ShieldAlert} trend="การควบคุมความปลอดภัย" loading={isOverviewLoading} />
              </div>

              <div className="mt-6 grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
                <Panel title="สถิติการใช้งาน" action={overview?.generated_at ? `อัปเดต ${new Date(overview.generated_at).toLocaleTimeString("th-TH")}` : "กำลังโหลด"} icon={LineChartIcon}>
                  <div className="chart-frame">
                    {isOverviewLoading ? <div className="skeleton-block h-full min-h-[260px]" /> : null}
                    {!isOverviewLoading ? (
                      <ResponsiveContainer width="100%" height={280} minWidth={0} minHeight={280}>
                        <AreaChart data={chartData} margin={{ left: -10, right: 18, top: 18, bottom: 4 }}>
                          <defs>
                            <linearGradient id="trafficFill" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.18} />
                              <stop offset="100%" stopColor="#0a7c6e" stopOpacity={0.03} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid stroke="rgba(7,23,19,0.07)" vertical={false} />
                          <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fill: "#5b756e", fontSize: 12, fontWeight: 600 }} />
                          <YAxis tickLine={false} axisLine={false} tick={{ fill: "#5b756e", fontSize: 12 }} />
                          <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} cursor={{ stroke: "#22d3ee", strokeOpacity: 0.24 }} />
                          <Area type="monotone" dataKey="value" stroke="#0a7c6e" fill="url(#trafficFill)" strokeWidth={2.5} dot={{ r: 4, fill: "#22d3ee", stroke: "#071713", strokeWidth: 2 }} activeDot={{ r: 6, fill: "#a3e635", stroke: "#071713", strokeWidth: 2 }} />
                        </AreaChart>
                      </ResponsiveContainer>
                    ) : null}
                  </div>
                </Panel>
                <Panel title="สถานะบริการ" icon={Wifi}>
                  <ServiceStatus services={overview?.services} />
                </Panel>
              </div>

              <div className="mt-6 grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
                <Panel title="ผลลัพธ์การลดงานและกระดาษ" action="ค่าประมาณจากข้อมูลในระบบ" icon={Leaf}>
                  {sustainability ? (
                    <>
                      <div className="grid grid-cols-2 gap-3">
                        <DataTile value={sustainability.paper_saved_sheets} label="แผ่นกระดาษที่ลดลง" />
                        <DataTile value={`${sustainability.admin_hours_saved} ชม.`} label="เวลาผู้ดูแลที่ประหยัด" />
                        <DataTile value={`${sustainability.co2_saved_grams} กรัม`} label="คาร์บอนโดยประมาณ" />
                        <DataTile value={`${sustainability.equal_access_rate_percent}%`} label="การเข้าถึงข้อมูล" />
                      </div>
                      <div className="mt-4 grid gap-3 text-sm text-slate-600 sm:grid-cols-2">
                        <ImpactLine label="นักเรียนที่ใช้งาน" value={`${sustainability.active_students}/${sustainability.expected_class_size}`} />
                        <ImpactLine label="รายการการบ้าน" value={sustainability.homework_count} />
                        <ImpactLine label="ผู้รับประกาศ" value={sustainability.broadcast_recipients} />
                        <ImpactLine label="คำขออัตโนมัติ" value={sustainability.automated_request_count} />
                      </div>
                    </>
                  ) : <SkeletonRows count={3} />}
                </Panel>

                <Panel title="เครื่องมืออ่านภาพด้วย AI" action="Gemini Vision" icon={FileScan}>
                  <form onSubmit={submitCapture} className="grid gap-4">
                    <label className="field-label" htmlFor="paperless-image">ภาพจากห้องเรียน</label>
                    <label className="upload-zone" htmlFor="paperless-image">
                      <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-emerald-700/10 text-emerald-800"><Camera size={20} /></span>
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-semibold text-emerald-950">{captureFile ? captureFile.name : "เลือกภาพกระดาน ใบงาน หรือประกาศ"}</span>
                        <span className="mt-1 block text-xs text-slate-500">รองรับ PNG, JPEG และ WEBP ขนาดไม่เกิน 6 MB</span>
                      </span>
                    </label>
                    <input
                      id="paperless-image"
                      type="file"
                      accept="image/png,image/jpeg,image/webp"
                      onChange={(event) => {
                        const file = event.target.files?.[0] || null;
                        if (file && (!ALLOWED_CAPTURE_TYPES.has(file.type) || file.size > MAX_CAPTURE_BYTES)) {
                          event.currentTarget.value = "";
                          setCaptureFile(null);
                          setCaptureResult(null);
                          captureMutation.mutate(file);
                          return;
                        }
                        captureMutation.reset();
                        setCaptureFile(file);
                        setCaptureResult(null);
                      }}
                      className="sr-only"
                      required
                    />
                    <button className="primary-button h-12 justify-center" disabled={captureMutation.isPending}>
                      <Sparkles size={17} />
                      {captureMutation.isPending ? "กำลังวิเคราะห์..." : "วิเคราะห์ภาพ"}
                    </button>
                    {captureMutation.isError ? <StatusNotice tone="danger" title="ไม่สามารถวิเคราะห์ภาพได้" text="ไฟล์ที่เลือกยังอยู่ กรุณาตรวจสอบไฟล์แล้วลองอีกครั้ง" error={captureMutation.error as Error} /> : null}
                  </form>
                  {captureResult ? <CaptureResult result={captureResult} /> : null}
                </Panel>
              </div>

              <div className="mt-6">
                <Panel title="การระงับการใช้งาน" action="สำหรับผู้ดูแลระบบ" icon={ShieldAlert}>
                  <div className="grid gap-5 xl:grid-cols-[0.85fr_1.15fr]">
                    <form onSubmit={submitBan} className="grid gap-3">
                      <label className="field-label" htmlFor="ban-user">LINE User ID</label>
                      <input id="ban-user" value={banUserId} onChange={(event) => setBanUserId(event.target.value)} className="mission-input h-12 px-4" required />
                      <label className="field-label" htmlFor="ban-reason">เหตุผล</label>
                      <input id="ban-reason" value={banReason} onChange={(event) => setBanReason(event.target.value)} className="mission-input h-12 px-4" maxLength={240} required />
                      <button className="danger-button" disabled={banMutation.isPending}><Ban size={17} />{banMutation.isPending ? "กำลังดำเนินการ..." : "ระงับการใช้งาน"}</button>
                      {banMutation.isError ? <StatusNotice tone="danger" title="ไม่สามารถระงับการใช้งานได้" text="ข้อมูลที่กรอกยังอยู่ กรุณาลองอีกครั้ง" error={banMutation.error as Error} /> : null}
                    </form>
                    <div className="grid content-start gap-2">
                      {(blacklistQuery.data?.items || []).map((item) => (
                        <div key={item.user_id} className="blacklist-row">
                          <div className="min-w-0">
                            <p className="truncate font-mono text-sm font-semibold text-emerald-950">{maskLineUserId(item.user_id)}</p>
                            <p className="truncate text-xs text-slate-500">{item.reason}</p>
                          </div>
                          <button type="button" onClick={() => unbanMutation.mutate(item.user_id)} className="mini-button" disabled={unbanMutation.isPending}>
                            {unbanMutation.isPending ? "กำลังดำเนินการ..." : "ยกเลิกการระงับ"}
                          </button>
                        </div>
                      ))}
                      {blacklistQuery.isLoading || blacklistQuery.isFetching ? <SkeletonRows count={3} /> : null}
                      {blacklistQuery.data?.items.length === 0 ? <EmptyState text="ยังไม่มีสมาชิกที่ถูกระงับ" icon={ShieldAlert} /> : null}
                      {unbanMutation.isError ? <StatusNotice tone="danger" title="ไม่สามารถยกเลิกการระงับได้" text="กรุณาลองอีกครั้ง" error={unbanMutation.error as Error} /> : null}
                    </div>
                  </div>
                </Panel>
              </div>
            </>
          ) : null}
        </section>
      </div>
    </main>
  );
}

function HomeworkList({ items, loaded }: { items: Homework[]; loaded: boolean }) {
  if (!loaded) {
    return <SkeletonRows count={3} />;
  }
  if (!items.length) {
    return <EmptyState text="ยังไม่มีการบ้าน" icon={BookOpenCheck} />;
  }
  return (
    <div className="grid gap-3">
      {items.map((item) => (
        <div key={item.id} className="homework-row">
          <div className="flex items-center justify-between gap-3">
            <p className="font-semibold text-emerald-950">{item.subject || "ไม่ระบุวิชา"}</p>
            <span className="rounded-full bg-white/70 px-3 py-1 text-xs font-medium text-slate-500">
              {item.due_date || "ไม่ระบุกำหนดส่ง"}
            </span>
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-600">{item.detail || "ไม่มีรายละเอียด"}</p>
        </div>
      ))}
    </div>
  );
}

function BroadcastList({ items, loaded }: { items: BroadcastRecord[]; loaded: boolean }) {
  if (!loaded) {
    return <SkeletonRows count={3} />;
  }
  if (!items.length) {
    return <EmptyState text="ยังไม่มีประกาศ" icon={BellRing} />;
  }
  return (
    <div className="grid gap-3">
      {items.map((item) => (
        <div key={item.id} className="homework-row">
          <p className="whitespace-pre-wrap text-sm leading-6 text-emerald-950">{item.message || "ไม่มีข้อความ"}</p>
          <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-500">
            <span>ส่งสำเร็จ {item.sent_count ?? 0} คน</span>
            {item.failed_count ? <span className="text-rose-700">ส่งไม่สำเร็จ {item.failed_count} คน</span> : null}
            {item.timestamp ? <span>{new Date(item.timestamp).toLocaleString("th-TH")}</span> : null}
          </div>
        </div>
      ))}
    </div>
  );
}

function ServiceStatus({ services }: { services?: ServiceMap }) {
  if (!services) {
    return <SkeletonRows count={4} />;
  }
  return (
    <div className="grid gap-3">
      {Object.entries(services).map(([name, ok]) => (
        <div key={name} className="service-row">
          <div className="flex items-center gap-3">
            <span className={`service-dot ${ok ? "service-dot-ready" : "service-dot-degraded"}`} />
            <span className="font-mono text-sm font-semibold capitalize text-emerald-950">{name}</span>
          </div>
          <span className={`service-badge ${ok ? "service-badge-ready" : "service-badge-degraded"}`}>
            <CheckCircle2 size={15} />
            {ok ? "พร้อมใช้งาน" : "มีปัญหาชั่วคราว"}
          </span>
        </div>
      ))}
    </div>
  );
}

function DataTile({ value, label }: { value: string | number; label: string }) {
  return (
    <div className="data-tile">
      <p className="font-mono text-2xl font-semibold text-[var(--color-text-main)] tabular-nums">{value}</p>
      <p className="mt-1 text-xs font-medium text-[var(--color-text-muted)]">{label}</p>
    </div>
  );
}

function CaptureResult({ result }: { result: PaperlessCaptureResult }) {
  return (
    <div className="result-card">
      <div className="flex items-center gap-2 text-emerald-950">
        <Sparkles size={17} />
        <p className="text-sm font-semibold">{result.analysis.title}</p>
      </div>
      <ul className="mt-3 grid gap-2 text-sm leading-6 text-slate-700">
        {result.analysis.summary.map((item, index) => (
          <li key={`${item}-${index}`} className="flex gap-2">
            <Check size={15} className="mt-1 shrink-0 text-emerald-700" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
      {result.analysis.homework_candidates.length ? (
        <div className="mt-4 border-t border-emerald-900/10 pt-3">
          <p className="text-xs font-semibold text-emerald-700">รายการที่อาจเป็นการบ้าน</p>
          <p className="mt-2 text-sm text-emerald-950">{result.analysis.homework_candidates.join(" / ")}</p>
        </div>
      ) : null}
      {result.analysis.paperless_value ? <p className="mt-3 text-sm leading-6 text-slate-700">{result.analysis.paperless_value}</p> : null}
    </div>
  );
}

function maskLineUserId(userId: string) {
  if (userId.length <= 10) {
    return `${userId.slice(0, 3)}•••${userId.slice(-2)}`;
  }
  return `${userId.slice(0, 6)}••••••${userId.slice(-4)}`;
}

function Metric({
  label,
  value,
  icon: Icon,
  trend,
  loading,
}: {
  label: string;
  value: string | number;
  icon: LucideIcon;
  trend: string;
  loading?: boolean;
}) {
  if (loading) {
    return <SkeletonMetric label={label} icon={Icon} />;
  }

  return (
    <div className="metric-card">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium text-[var(--color-text-muted)]">{label}</p>
          <p className="mt-2 font-mono text-[32px] font-semibold leading-[1.1] text-[var(--color-text-main)] tabular-nums">{value}</p>
        </div>
        <span className="metric-icon">
          <Icon size={20} strokeWidth={2.2} />
        </span>
      </div>
      <div className="mt-5 flex items-center justify-between gap-3">
        <span className="text-xs font-medium text-[var(--color-text-muted)]">{trend}</span>
        <span className="metric-sparkline" aria-hidden="true">
          <i />
          <i />
          <i />
          <i />
        </span>
      </div>
    </div>
  );
}

function SkeletonMetric({ label, icon: Icon }: { label: string; icon: LucideIcon }) {
  return (
    <div className="metric-card" aria-busy="true">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium text-[var(--color-text-muted)]">{label}</p>
          <div className="skeleton-block mt-3 h-9 w-28" />
        </div>
        <span className="metric-icon">
          <Icon size={20} strokeWidth={2.2} />
        </span>
      </div>
      <div className="mt-5 flex items-center justify-between gap-3">
        <div className="skeleton-block h-3 w-32" />
        <span className="metric-sparkline" aria-hidden="true">
          <i />
          <i />
          <i />
          <i />
        </span>
      </div>
    </div>
  );
}

function Panel({
  title,
  action,
  icon: Icon,
  children,
}: {
  title: string;
  action?: string;
  icon?: LucideIcon;
  children: React.ReactNode;
}) {
  return (
    <section className="glass-panel">
      <div className="mb-5 flex items-center justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          {Icon ? (
            <span className="panel-icon">
              <Icon size={18} strokeWidth={2.2} />
            </span>
          ) : null}
          <h2 className="truncate text-base font-semibold text-emerald-950">{title}</h2>
        </div>
        {action ? <span className="hidden font-mono text-xs font-semibold text-slate-500 sm:inline">{action}</span> : null}
      </div>
      {children}
    </section>
  );
}

function ImpactLine({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="impact-line">
      <span>{label}</span>
      <span className="font-mono font-semibold text-emerald-950 tabular-nums">{value}</span>
    </div>
  );
}

function UsersTable({ data, loading }: { data: UserRow[]; loading?: boolean }) {
  const [globalFilter, setGlobalFilter] = useState("");
  const columns = useMemo<ColumnDef<UserRow>[]>(
    () => [
      {
        accessorKey: "user_id",
        header: "LINE User ID",
        cell: (info) => <MaskedUserId value={String(info.getValue())} />,
      },
    ],
    [],
  );
  // TanStack Table intentionally returns function properties; keep it isolated in this leaf component.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data,
    columns,
    state: { globalFilter },
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  return (
    <div>
      <div className="mission-search">
        <Search size={17} className="text-emerald-700" />
        <input
          value={globalFilter}
          onChange={(event) => setGlobalFilter(event.target.value)}
          placeholder="ค้นหาสมาชิกด้วย LINE User ID"
          className="h-full flex-1 border-0 bg-transparent text-sm text-emerald-950 outline-none placeholder:text-slate-400"
        />
      </div>
      <div className="mission-table-wrap">
        {loading ? (
          <div className="grid gap-2 p-3" aria-busy="true">
            <SkeletonRows count={5} />
          </div>
        ) : null}
        {!loading ? (
        <table className="w-full border-collapse text-left text-sm">
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th key={header.id} className="px-4 py-3 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
                    {flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id}>
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-4 py-3 text-slate-700">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        ) : null}
        {!loading && table.getRowModel().rows.length === 0 ? <EmptyState text="ไม่พบสมาชิก" icon={Users} /> : null}
      </div>
    </div>
  );
}

function StatusNotice({ tone, title, text, error }: { tone: "success" | "danger"; title: string; text?: string; error?: Error }) {
  const apiError = error instanceof DashboardApiError ? error : null;
  const displayText = text || error?.message || "";
  const code = apiError?.code || (apiError ? `HTTP_${apiError.status}` : "");
  const styles = tone === "success" ? "status-notice-success" : "status-notice-danger";
  return (
    <div className={`status-notice ${styles}`} role={tone === "danger" ? "alert" : "status"}>
      <span className="status-notice-icon">
        {tone === "danger" ? <AlertTriangle size={20} /> : <CheckCircle2 size={20} />}
      </span>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-semibold">{title}</p>
        </div>
        {displayText ? <p className="mt-1 text-sm leading-6 opacity-82">{displayText}</p> : null}
        {apiError ? (
          <details className="mt-2 text-xs opacity-72">
            <summary className="cursor-pointer font-semibold">รายละเอียดทางเทคนิค</summary>
            <p className="mt-2 font-mono">{code} · HTTP {apiError.status}</p>
          </details>
        ) : null}
      </div>
    </div>
  );
}

function EmptyState({ text, icon: Icon }: { text: string; icon?: LucideIcon }) {
  const EmptyIcon = Icon || Inbox;
  return (
    <div className="empty-widget" style={{ minHeight: 120 }}>
      <span className="empty-widget-icon">
        <EmptyIcon size={28} strokeWidth={1.7} />
      </span>
      <p className="text-sm font-semibold text-emerald-950">{text}</p>
    </div>
  );
}

function MaskedUserId({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);

  async function copyUserId() {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  return (
    <div className="flex items-center justify-between gap-3">
      <span className="font-mono text-xs tabular-nums">{maskLineUserId(value)}</span>
      <button type="button" className="mini-button" onClick={copyUserId} aria-label="คัดลอก LINE User ID">
        <Copy size={14} />
        {copied ? "คัดลอกแล้ว" : "คัดลอก"}
      </button>
    </div>
  );
}

function SkeletonRows({ count }: { count: number }) {
  return Array.from({ length: count }, (_, index) => (
    <div key={index} className="skeleton-block h-12" />
  ));
}
