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
  FileScan,
  Gauge,
  GraduationCap,
  Inbox,
  Leaf,
  LineChart as LineChartIcon,
  LogOut,
  MessageSquareText,
  Network,
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
import { CSSProperties, FormEvent, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

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
      : "Dashboard API request failed.";
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
    throw validationError("Choose an image first.");
  }
  if (!ALLOWED_CAPTURE_TYPES.has(file.type)) {
    throw validationError("Only PNG, JPEG, and WebP images are supported.");
  }
  if (file.size > MAX_CAPTURE_BYTES) {
    throw validationError("Image must be 6 MB or smaller.");
  }
  return file;
}

async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`/api/admin/${path}`, { cache: "no-store" });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw getApiError(payload, response.status);
  }
  return payload.data as T;
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
  return payload.data as T;
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
  return payload.data as T;
}

export function DashboardShell() {
  const queryClient = useQueryClient();
  const [activeSection, setActiveSection] = useState("Overview");
  const [broadcastMessage, setBroadcastMessage] = useState("");
  const [banUserId, setBanUserId] = useState("");
  const [banReason, setBanReason] = useState("");
  const [captureFile, setCaptureFile] = useState<File | null>(null);
  const [captureResult, setCaptureResult] = useState<PaperlessCaptureResult | null>(null);

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
        throw validationError("Broadcast message is required.");
      }
      if (message.length > 1000) {
        throw validationError("Broadcast message must be 1000 characters or fewer.");
      }
      return apiSend("broadcasts", "POST", { message });
    },
    onSuccess: () => {
      setBroadcastMessage("");
      void queryClient.invalidateQueries({ queryKey: ["overview"] });
    },
  });

  const banMutation = useMutation({
    mutationFn: ({ userId, reason }: BanPayload) => {
      if (!userId) {
        throw validationError("LINE user ID is required.");
      }
      if (!reason) {
        throw validationError("Reason is required.");
      }
      if (reason.length > 240) {
        throw validationError("Reason must be 240 characters or fewer.");
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
      { label: "Requests", value: total },
      { label: "Messages", value: metrics?.total_messages || 0 },
      { label: "Errors", value: errors },
      { label: "Users", value: overview?.counts.registered_users || 0 },
    ];
  }, [metrics, overview]);



  async function logout() {
    await fetch("/api/logout", { method: "POST" });
    window.location.href = "/login";
  }

  function submitBroadcast(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
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

  const navItems: [string, LucideIcon][] = [
    ["Overview", Gauge],
    ["Users", GraduationCap],
    ["Homework", BookOpenCheck],
    ["Broadcast", MessageSquareText],
    ["Blacklist", ShieldAlert],
    ["System", Radar],
  ];

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
              <p className="font-mono text-[11px] font-medium uppercase tracking-[0.12em] text-cyan-100/60">NSC Console</p>
            </div>
          </div>

          <nav className="mt-5 grid gap-2">
            {navItems.map(([label, Icon]) => (
              <button
                key={label}
                type="button"
                onClick={() => setActiveSection(label)}
                className={`nav-item ${activeSection === label ? "nav-item-active" : ""}`}
              >
                <Icon size={18} strokeWidth={2.2} />
                <span>{label}</span>
              </button>
            ))}
          </nav>

          <div className="impact-card mt-5 rounded-lg border border-white/10 bg-white/[0.04] p-3">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-lime-200">
              <Leaf size={14} />
              Impact Lens
            </div>
            <p className="mt-2 text-xs leading-5 text-cyan-50/62">
              Paperless capture, digital notices, and classroom access in one secured workspace.
            </p>
          </div>

          <button type="button" onClick={logout} className="secondary-button mt-5 w-full">
            <LogOut size={17} />
            Sign out
          </button>
        </aside>

        <section className="relative px-4 py-5 sm:px-6 lg:px-8 lg:py-8">
          <header className="mission-hero">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2 font-mono text-xs font-semibold uppercase tracking-[0.16em] text-cyan-200">
                <span className="h-2 w-2 rounded-full bg-lime-300 shadow-[0_0_18px_rgba(163,230,53,0.72)]" />
                Smart Classroom Command Center
              </div>
              <h1 className="mt-3 text-3xl font-semibold tracking-[-0.01em] text-white md:text-4xl">
                Live operations
              </h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-cyan-50/68">
                Monitor LINE bot health, paperless workflows, classroom notices, and access controls without touching webhook delivery.
              </p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <div className="status-pill">
                <Network size={16} />
                Token-proxied API
              </div>
              <button
                type="button"
                onClick={() => {
                  void queryClient.invalidateQueries();
                }}
                className="primary-button"
              >
                <RefreshCcw size={17} />
                Refresh
              </button>
            </div>
          </header>

          {overviewQuery.isError ? (
            <StatusNotice tone="danger" title="Dashboard API unavailable" error={overviewQuery.error as Error} />
          ) : null}

          <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Metric label="Registered users" value={overview?.counts.registered_users ?? "--"} icon={GraduationCap} trend="Class roster reach" loading={isOverviewLoading} />
            <Metric label="Total requests" value={metrics?.total_requests ?? "--"} icon={Activity} trend="Automation load" loading={isOverviewLoading} />
            <Metric label="Avg response" value={metrics ? `${metrics.avg_response_time_ms}ms` : "--"} icon={CircleGauge} trend="Response budget" loading={isOverviewLoading} />
            <Metric label="Banned users" value={overview?.counts.banned_users ?? "--"} icon={ShieldAlert} trend="Safety controls" loading={isOverviewLoading} />
          </div>

          <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Metric label="Sheets saved" value={sustainability?.paper_saved_sheets ?? "--"} icon={FileScan} trend="Paperless estimate" loading={isOverviewLoading} />
            <Metric label="Admin hours saved" value={sustainability ? `${sustainability.admin_hours_saved}h` : "--"} icon={Clock3} trend="Teacher time" loading={isOverviewLoading} />
            <Metric label="Equal access" value={sustainability ? `${sustainability.equal_access_rate_percent}%` : "--"} icon={Sprout} trend="Classroom inclusion" loading={isOverviewLoading} />
            <Metric label="Digital notices" value={sustainability?.broadcast_count ?? "--"} icon={BellRing} trend="Paper-free sends" loading={isOverviewLoading} />
          </div>

          <div className="mt-6 grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
            <Panel title="Sustainability impact" action="Conservative classroom estimate" icon={Leaf}>
              {sustainability ? (
                <div className="grid grid-cols-2 gap-3">
                  <div className="data-tile">
                    <p className="font-mono text-2xl font-semibold text-[var(--color-text-main)] tabular-nums">{sustainability.paper_saved_sheets}</p>
                    <p className="mt-1 text-[11px] font-medium uppercase tracking-[0.08em] text-[var(--color-text-muted)]">Sheets saved</p>
                  </div>
                  <div className="data-tile">
                    <p className="font-mono text-2xl font-semibold text-[var(--color-text-main)] tabular-nums">{sustainability.admin_hours_saved}h</p>
                    <p className="mt-1 text-[11px] font-medium uppercase tracking-[0.08em] text-[var(--color-text-muted)]">Admin time saved</p>
                  </div>
                  <div className="data-tile">
                    <p className="font-mono text-2xl font-semibold text-[var(--color-text-main)] tabular-nums">{sustainability.co2_saved_grams}g</p>
                    <p className="mt-1 text-[11px] font-medium uppercase tracking-[0.08em] text-[var(--color-text-muted)]">CO₂ saved</p>
                  </div>
                  <div className="data-tile">
                    <p className="font-mono text-2xl font-semibold text-[var(--color-text-main)] tabular-nums">{sustainability.equal_access_rate_percent}%</p>
                    <p className="mt-1 text-[11px] font-medium uppercase tracking-[0.08em] text-[var(--color-text-muted)]">Equal access</p>
                  </div>
                </div>
              ) : (
                <SkeletonRows count={3} />
              )}
              {sustainability ? (
                <div className="mt-4 grid gap-3 text-sm text-slate-600 sm:grid-cols-2">
                  <ImpactLine label="Active students" value={`${sustainability.active_students}/${sustainability.expected_class_size}`} />
                  <ImpactLine label="Homework records" value={sustainability.homework_count} />
                  <ImpactLine label="Broadcast recipients" value={sustainability.broadcast_recipients} />
                  <ImpactLine label="CO2 estimate" value={`${sustainability.co2_saved_grams}g`} />
                </div>
              ) : (
                <SkeletonRows count={3} />
              )}
            </Panel>

            <Panel title="Paperless Capture AI" action="Gemini Vision PoC" icon={FileScan}>
              <form onSubmit={submitCapture} className="grid gap-4">
                <label className="field-label" htmlFor="paperless-image">
                  Classroom image
                </label>
                <label className="upload-zone" htmlFor="paperless-image">
                    <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-emerald-700/10 text-emerald-800">
                    <Camera size={20} />
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-semibold text-emerald-950">
                      {captureFile ? captureFile.name : "Upload board, worksheet, or class notice"}
                    </span>
                    <span className="mt-1 block text-xs text-slate-500">PNG, JPEG, or WEBP. The analysis stays behind the admin API.</span>
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
                  {captureMutation.isPending ? "Analyzing..." : "Analyze image"}
                </button>
                {captureMutation.isError ? <StatusNotice tone="danger" title="Capture failed" error={captureMutation.error as Error} /> : null}
              </form>

              {captureResult ? (
                <div className="result-card">
                  <div className="flex items-center gap-2 text-emerald-950">
                    <Sparkles size={17} />
                    <p className="text-sm font-semibold">{captureResult.analysis.title}</p>
                  </div>
                  <ul className="mt-3 grid gap-2 text-sm leading-6 text-slate-700">
                    {captureResult.analysis.summary.map((item, index) => (
                      <li key={`${item}-${index}`} className="flex gap-2">
                        <Check size={15} className="mt-1 shrink-0 text-emerald-700" />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                  {captureResult.analysis.homework_candidates.length ? (
                    <div className="mt-4 border-t border-emerald-900/10 pt-3">
                      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-emerald-700">Homework candidates</p>
                      <p className="mt-2 text-sm text-emerald-950">{captureResult.analysis.homework_candidates.join(" / ")}</p>
                    </div>
                  ) : null}
                  {captureResult.analysis.paperless_value ? (
                    <p className="mt-3 text-sm leading-6 text-slate-700">{captureResult.analysis.paperless_value}</p>
                  ) : null}
                </div>
              ) : null}
            </Panel>
          </div>

          <div className="mt-6 grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
            <Panel title="Traffic shape" action={overview?.generated_at ? `Updated ${new Date(overview.generated_at).toLocaleTimeString()}` : "Loading"} icon={LineChartIcon}>
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

            <Panel title="Service status" icon={Wifi}>
              <div className="grid gap-3">
                {overview ? (
                  Object.entries(overview.services).map(([name, ok]) => (
                    <div key={name} className="service-row">
                      <div className="flex items-center gap-3">
                        <span className={`service-dot ${ok ? "service-dot-ready" : "service-dot-degraded"}`} />
                        <span className="font-mono text-sm font-semibold capitalize text-emerald-950">{name}</span>
                      </div>
                      <span className={`service-badge ${ok ? "service-badge-ready" : "service-badge-degraded"}`}>
                        <CheckCircle2 size={15} />
                        {ok ? "Ready" : "Degraded"}
                      </span>
                    </div>
                  ))
                ) : (
                  <SkeletonRows count={4} />
                )}
              </div>
            </Panel>
          </div>

          <div className="mt-6 grid gap-5 xl:grid-cols-2">
            <Panel title="Recent homework" icon={BookOpenCheck}>
              <div className="grid gap-3">
                {(overview?.homework_preview || []).map((item) => (
                  <div key={item.id} className="homework-row">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-semibold text-emerald-950">{item.subject || "ไม่ระบุวิชา"}</p>
                      <span className="rounded-full bg-white/70 px-3 py-1 text-xs font-medium text-slate-500">{item.due_date || "ไม่ระบุกำหนดส่ง"}</span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{item.detail || "ไม่มีรายละเอียด"}</p>
                  </div>
                ))}
                {overview && overview.homework_preview.length === 0 ? <EmptyState text="No homework records are available." icon={BookOpenCheck} /> : null}
              </div>
            </Panel>

            <Panel title="Broadcast console" icon={MessageSquareText}>
              <form onSubmit={submitBroadcast} className="grid gap-3">
                <label className="field-label" htmlFor="broadcast">
                  Message
                </label>
                <textarea
                  id="broadcast"
                  value={broadcastMessage}
                  onChange={(event) => setBroadcastMessage(event.target.value)}
                  className="mission-input min-h-36 resize-y p-4 leading-6"
                  maxLength={1000}
                  required
                />
                <button className="primary-button" disabled={broadcastMutation.isPending}>
                  <Send size={17} />
                  {broadcastMutation.isPending ? "Queueing..." : "Queue broadcast"}
                </button>
                {broadcastMutation.isSuccess ? <StatusNotice tone="success" title="Queued" text="Broadcast is running in the backend." /> : null}
                {broadcastMutation.isError ? <StatusNotice tone="danger" title="Could not queue broadcast" error={broadcastMutation.error as Error} /> : null}
              </form>
            </Panel>
          </div>

          <div className="mt-6 grid gap-5 xl:grid-cols-[1.15fr_0.85fr]">
            <Panel title="Users" icon={Users}>
              <UsersTable data={usersQuery.data?.items || []} loading={usersQuery.isLoading || usersQuery.isFetching} />
            </Panel>
            <Panel title="Blacklist control" icon={ShieldAlert}>
              <form onSubmit={submitBan} className="grid gap-3">
                <label className="field-label" htmlFor="ban-user">
                  LINE user ID
                </label>
                <input
                  id="ban-user"
                  value={banUserId}
                  onChange={(event) => setBanUserId(event.target.value)}
                  className="mission-input h-12 px-4"
                  required
                />
                <label className="field-label" htmlFor="ban-reason">
                  Reason
                </label>
                <input
                  id="ban-reason"
                  value={banReason}
                  onChange={(event) => setBanReason(event.target.value)}
                  className="mission-input h-12 px-4"
                  maxLength={240}
                  required
                />
                <button className="danger-button" disabled={banMutation.isPending}>
                  <Ban size={17} />
                  Ban user
                </button>
              </form>
              <div className="mt-5 grid gap-2">
                {(blacklistQuery.data?.items || []).map((item) => (
                  <div key={item.user_id} className="blacklist-row">
                    <div className="min-w-0">
                      <p className="truncate font-mono text-sm font-semibold text-emerald-950">{item.user_id}</p>
                      <p className="truncate text-xs text-slate-500">{item.reason}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        unbanMutation.mutate(item.user_id);
                      }}
                      className="mini-button"
                      disabled={unbanMutation.isPending}
                    >
                      {unbanMutation.isPending ? "Working..." : "Unban"}
                    </button>
                  </div>
                ))}
                {blacklistQuery.isLoading || blacklistQuery.isFetching ? <SkeletonRows count={3} /> : null}
                {blacklistQuery.data?.items.length === 0 ? <EmptyState text="Blacklist is empty." icon={ShieldAlert} /> : null}
                {unbanMutation.isError ? <StatusNotice tone="danger" title="Could not unban user" error={unbanMutation.error as Error} /> : null}
              </div>
            </Panel>
          </div>
        </section>
      </div>
    </main>
  );
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
          <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-[var(--color-text-muted)]">{label}</p>
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
          <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-[var(--color-text-muted)]">{label}</p>
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
        header: "User ID",
        cell: (info) => <span className="font-mono text-xs tabular-nums">{String(info.getValue())}</span>,
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
          placeholder="Search users"
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
        {!loading && table.getRowModel().rows.length === 0 ? <EmptyState text="No users found." icon={Users} /> : null}
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
          {code ? <span className="status-code">{code}</span> : null}
        </div>
        {displayText ? <p className="mt-1 text-sm leading-6 opacity-82">{displayText}</p> : null}
        {apiError ? <p className="mt-2 font-mono text-xs uppercase tracking-[0.12em] opacity-62">Status {apiError.status}</p> : null}
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
      <p className="mt-1 font-mono text-xs uppercase tracking-[0.10em] text-[var(--color-text-muted)]">Awaiting signal</p>
    </div>
  );
}

function SkeletonRows({ count }: { count: number }) {
  return Array.from({ length: count }, (_, index) => (
    <div key={index} className="skeleton-block h-12" />
  ));
}
