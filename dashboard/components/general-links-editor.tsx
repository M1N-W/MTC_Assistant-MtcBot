"use client";

import { FormEvent, useState } from "react";
import { Link as LinkIcon, RefreshCcw, Save, Search } from "lucide-react";

type LinkKey = "worksheet_url" | "school_url" | "grade_url" | "absence_form_url";

type LinksPayload = Record<LinkKey, string>;

type LinksResponse = {
  class_id: string;
  term_id: string;
  links: LinksPayload;
  effective_links: Partial<LinksPayload>;
  updated_at?: string;
  updated_by?: string;
};

type ApiErrorPayload = {
  error?: {
    code?: unknown;
    message?: unknown;
  };
};

const DEFAULT_CLASS_ID = "mtc13";
const DEFAULT_TERM_ID = "2569-t1";
const LINK_FIELDS: { key: LinkKey; label: string; helper: string }[] = [
  { key: "worksheet_url", label: "ลิงก์ใบงาน", helper: "ใช้กับคำสั่ง งาน และ ใบงาน" },
  { key: "school_url", label: "เว็บไซต์โรงเรียน", helper: "ใช้กับคำสั่ง เว็บโรงเรียน" },
  { key: "grade_url", label: "ลิงก์ตรวจผลการเรียน", helper: "ใช้กับคำสั่ง เกรด" },
  { key: "absence_form_url", label: "แบบฟอร์มลา", helper: "ใช้กับคำสั่ง ลา" },
];

const EMPTY_LINKS: LinksPayload = {
  worksheet_url: "",
  school_url: "",
  grade_url: "",
  absence_form_url: "",
};

function getApiError(payload: unknown, fallback: string) {
  const apiError = isApiErrorPayload(payload) ? payload.error : undefined;
  return typeof apiError?.message === "string" && apiError.message.trim()
    ? apiError.message
    : fallback;
}

function isApiErrorPayload(payload: unknown): payload is ApiErrorPayload {
  return typeof payload === "object" && payload !== null && "error" in payload;
}

function linksPath(classId: string, termId: string) {
  return `/api/admin/classes/${encodeURIComponent(classId)}/terms/${encodeURIComponent(termId)}/config/links`;
}

async function readLinks(classId: string, termId: string) {
  const response = await fetch(linksPath(classId, termId), { cache: "no-store" });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(getApiError(payload, "ไม่สามารถโหลดลิงก์ได้ กรุณาลองอีกครั้ง"));
  }
  return (payload as { data: LinksResponse }).data;
}

async function writeLinks(classId: string, termId: string, links: LinksPayload) {
  const response = await fetch(linksPath(classId, termId), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(links),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(getApiError(payload, "ไม่สามารถบันทึกได้ ข้อมูลที่กรอกยังอยู่ กรุณาลองอีกครั้ง"));
  }
  return (payload as { data: LinksResponse }).data;
}

function validateClientLinks(classId: string, termId: string, links: LinksPayload) {
  if (!classId.trim()) {
    return "กรุณาระบุห้องเรียน";
  }
  if (!termId.trim()) {
    return "กรุณาระบุภาคเรียน";
  }
  for (const field of LINK_FIELDS) {
    const value = links[field.key].trim();
    if (value && !value.startsWith("https://")) {
      return `${field.label} ต้องเว้นว่างหรือขึ้นต้นด้วย https://`;
    }
  }
  return "";
}

export function GeneralLinksEditor() {
  const [classId, setClassId] = useState(DEFAULT_CLASS_ID);
  const [termId, setTermId] = useState(DEFAULT_TERM_ID);
  const [links, setLinks] = useState<LinksPayload>(EMPTY_LINKS);
  const [loaded, setLoaded] = useState<LinksResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function loadCurrentLinks() {
    setLoading(true);
    setError("");
    setSuccess("");
    try {
      const data = await readLinks(classId.trim(), termId.trim());
      setLinks(data.links);
      setLoaded(data);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "ไม่สามารถโหลดลิงก์ได้ กรุณาลองอีกครั้ง");
    } finally {
      setLoading(false);
    }
  }

  async function saveLinks(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSuccess("");
    const trimmedLinks = Object.fromEntries(
      LINK_FIELDS.map(({ key }) => [key, links[key].trim()]),
    ) as LinksPayload;
    const validationError = validateClientLinks(classId, termId, trimmedLinks);
    if (validationError) {
      setError(validationError);
      return;
    }

    setSaving(true);
    try {
      const data = await writeLinks(classId.trim(), termId.trim(), trimmedLinks);
      setLinks(data.links);
      setLoaded(data);
      setSuccess("บันทึกลิงก์เรียบร้อยแล้ว");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "ไม่สามารถบันทึกได้ ข้อมูลที่กรอกยังอยู่ กรุณาลองอีกครั้ง");
    } finally {
      setSaving(false);
    }
  }

  function updateLink(key: LinkKey, value: string) {
    setLinks((current) => ({ ...current, [key]: value }));
    setSuccess("");
  }

  return (
    <section className="glass-panel mt-6">
      <div className="mb-5 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex min-w-0 items-center gap-3">
          <span className="panel-icon">
            <LinkIcon size={18} strokeWidth={2.2} />
          </span>
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold text-emerald-950">ลิงก์ที่ใช้ในห้องเรียน</h2>
            <p className="mt-1 text-sm text-slate-600">จัดการลิงก์ที่นักเรียนเปิดผ่านคำสั่งใน LINE</p>
          </div>
        </div>
        {loaded?.updated_at ? (
          <span className="font-mono text-xs font-semibold text-slate-500">
            อัปเดต {new Date(loaded.updated_at).toLocaleString("th-TH")}
          </span>
        ) : null}
      </div>

      <form onSubmit={saveLinks} className="grid gap-4">
        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
          <label className="grid gap-2">
            <span className="field-label">ห้องเรียน</span>
            <input
              value={classId}
              onChange={(event) => setClassId(event.target.value)}
              className="mission-input h-12 px-4"
              autoComplete="off"
            />
          </label>
          <label className="grid gap-2">
            <span className="field-label">ภาคเรียน</span>
            <input
              value={termId}
              onChange={(event) => setTermId(event.target.value)}
              className="mission-input h-12 px-4"
              autoComplete="off"
            />
          </label>
          <div className="flex items-end gap-2">
            <button type="button" onClick={loadCurrentLinks} disabled={loading || saving} className="secondary-button h-12">
              <Search size={17} />
              {loading ? "กำลังโหลด..." : "โหลดข้อมูล"}
            </button>
            <button type="button" onClick={loadCurrentLinks} disabled={loading || saving} className="mini-button h-12">
              <RefreshCcw size={16} />
              โหลดใหม่
            </button>
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          {LINK_FIELDS.map((field) => (
            <label key={field.key} className="grid gap-2">
              <span className="field-label">{field.label}</span>
              <input
                value={links[field.key]}
                onChange={(event) => updateLink(field.key, event.target.value)}
                placeholder="https://..."
                className="mission-input h-12 px-4"
                autoComplete="off"
              />
              <span className="text-xs text-slate-500">{field.helper}</span>
            </label>
          ))}
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-h-6">
            {error ? <p className="text-sm font-semibold text-rose-700" role="alert">{error}</p> : null}
            {success ? <p className="text-sm font-semibold text-emerald-700" role="status">{success}</p> : null}
          </div>
          <button type="submit" disabled={saving || loading} className="primary-button">
            <Save size={17} />
            {saving ? "กำลังบันทึก..." : "บันทึกลิงก์"}
          </button>
        </div>
      </form>
    </section>
  );
}
