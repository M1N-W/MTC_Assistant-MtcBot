"use client";

import { FormEvent, useMemo, useState } from "react";
import {
  CheckCircle2,
  KeyRound,
  LoaderCircle,
  RefreshCcw,
  Save,
  ShieldCheck,
  Trash2,
} from "lucide-react";

type Provider = {
  provider_id: "gemini" | "openai" | "anthropic";
  display_name: string;
  configured: boolean;
  status: string;
  masked_key: string;
  model: string;
  allowed_models: string[];
  updated_at?: string | null;
  last_validated_at?: string | null;
  last_error_type?: string | null;
  cooldown_until?: string | null;
};

type Settings = {
  selected_provider?: Provider["provider_id"];
  selected_model?: string;
  system_fallback_enabled?: boolean;
  daily_fallback_request_budget?: number;
  daily_fallback_token_budget?: number;
};

type CredentialsResponse = {
  class_id: string;
  providers: Provider[];
  settings: Settings;
};

const DEFAULT_CLASS_ID = "mtc13";

function apiPath(classId: string, suffix = "") {
  return `/api/admin/classes/${encodeURIComponent(classId)}/ai${suffix}`;
}

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    cache: "no-store",
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = (payload as { error?: { message?: string } }).error?.message;
    throw new Error(message || "ไม่สามารถโหลดการตั้งค่า AI ได้ กรุณาลองอีกครั้ง");
  }
  return (payload as { data: T }).data;
}

export function AISettingsEditor() {
  const [classId, setClassId] = useState(DEFAULT_CLASS_ID);
  const [data, setData] = useState<CredentialsResponse | null>(null);
  const [providerId, setProviderId] = useState<Provider["provider_id"]>("gemini");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [fallbackEnabled, setFallbackEnabled] = useState(true);
  const [requestBudget, setRequestBudget] = useState(20);
  const [tokenBudget, setTokenBudget] = useState(30000);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const selected = useMemo(
    () => data?.providers.find((provider) => provider.provider_id === providerId),
    [data, providerId],
  );

  async function loadCredentials() {
    setBusy("load");
    setError("");
    setSuccess("");
    try {
      const loaded = await apiRequest<CredentialsResponse>(
        apiPath(classId.trim(), "/credentials"),
      );
      setData(loaded);
      const nextProvider = loaded.settings.selected_provider || loaded.providers[0]?.provider_id;
      if (nextProvider) {
        const nextDefinition = loaded.providers.find((provider) => provider.provider_id === nextProvider);
        setProviderId(nextProvider);
        setModel(
          loaded.settings.selected_model
          || nextDefinition?.model
          || nextDefinition?.allowed_models[0]
          || "",
        );
      }
      setFallbackEnabled(loaded.settings.system_fallback_enabled ?? true);
      setRequestBudget(loaded.settings.daily_fallback_request_budget ?? 20);
      setTokenBudget(loaded.settings.daily_fallback_token_budget ?? 30000);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "ไม่สามารถโหลดการตั้งค่า AI ได้ กรุณาลองอีกครั้ง");
    } finally {
      setBusy("");
    }
  }

  async function validateKey() {
    if (!apiKey.trim()) {
      setError("กรุณากรอก API key ก่อนทดสอบการเชื่อมต่อ");
      return;
    }
    setBusy("validate");
    setError("");
    setSuccess("");
    try {
      await apiRequest(
        apiPath(classId.trim(), `/credentials/${providerId}/validate`),
        {
          method: "POST",
          body: JSON.stringify({ api_key: apiKey.trim(), model }),
        },
      );
      setSuccess("เชื่อมต่อสำเร็จ API key นี้ยังไม่ได้ถูกบันทึก");
    } catch (validateError) {
      setError(validateError instanceof Error ? validateError.message : "ไม่สามารถทดสอบการเชื่อมต่อได้ กรุณาลองอีกครั้ง");
    } finally {
      setBusy("");
    }
  }

  async function saveCredential(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!apiKey.trim()) {
      setError("กรุณากรอก API key ใหม่ก่อนบันทึก");
      return;
    }
    setBusy("save");
    setError("");
    setSuccess("");
    try {
      await apiRequest(
        apiPath(classId.trim(), `/credentials/${providerId}`),
        {
          method: "PUT",
          body: JSON.stringify({ api_key: apiKey.trim(), model }),
        },
      );
      setApiKey("");
      setSuccess("บันทึก API key แบบเข้ารหัสแล้ว ระบบจะไม่แสดง key ฉบับเต็มอีก");
      await loadCredentials();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "ไม่สามารถบันทึกได้ ข้อมูลที่กรอกยังอยู่ กรุณาลองอีกครั้ง");
    } finally {
      setBusy("");
    }
  }

  async function deleteCredential() {
    if (!selected?.configured || !window.confirm(`ลบ API key ของ ${selected.display_name} หรือไม่`)) {
      return;
    }
    setBusy("delete");
    setError("");
    setSuccess("");
    try {
      await apiRequest(
        apiPath(classId.trim(), `/credentials/${providerId}`),
        { method: "DELETE" },
      );
      setApiKey("");
      setSuccess("ลบ API key เรียบร้อยแล้ว");
      await loadCredentials();
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "ไม่สามารถลบ API key ได้ กรุณาลองอีกครั้ง");
    } finally {
      setBusy("");
    }
  }

  async function disableCredential() {
    if (!selected?.configured) return;
    setBusy("disable");
    setError("");
    setSuccess("");
    try {
      await apiRequest(
        apiPath(classId.trim(), `/credentials/${providerId}`),
        {
          method: "PUT",
          body: JSON.stringify({ status: "disabled" }),
        },
      );
      await loadCredentials();
      setSuccess("ปิดการใช้งาน API key นี้แล้ว");
    } catch (disableError) {
      setError(disableError instanceof Error ? disableError.message : "ไม่สามารถปิดการใช้งานได้ กรุณาลองอีกครั้ง");
    } finally {
      setBusy("");
    }
  }

  async function saveSettings() {
    setBusy("settings");
    setError("");
    setSuccess("");
    try {
      const settings = await apiRequest<Settings>(
        apiPath(classId.trim(), "/settings"),
        {
          method: "PATCH",
          body: JSON.stringify({
            selected_provider: providerId,
            selected_model: model,
            system_fallback_enabled: fallbackEnabled,
            daily_fallback_request_budget: requestBudget,
            daily_fallback_token_budget: tokenBudget,
          }),
        },
      );
      setData((current) => current ? { ...current, settings } : current);
      setSuccess("บันทึกการตั้งค่า AI เรียบร้อยแล้ว");
    } catch (settingsError) {
      setError(settingsError instanceof Error ? settingsError.message : "ไม่สามารถบันทึกได้ กรุณาลองอีกครั้ง");
    } finally {
      setBusy("");
    }
  }

  return (
    <section id="ai-settings" className="ai-settings-panel mt-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex items-start gap-3">
          <span className="ai-settings-icon"><KeyRound size={20} /></span>
          <div>
            <p className="font-mono text-xs font-bold uppercase tracking-[0.14em] text-[#F4B942]">
              Classroom OS
            </p>
            <h2 className="mt-1 text-xl font-semibold text-[#12372A]">การเชื่อมต่อ AI ของห้องเรียน</h2>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-600">
              สำหรับผู้ดูแลระบบ ใช้เชื่อมต่อ Gemini หรือผู้ให้บริการ AI ที่ห้องเรียนเลือก
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <input
            aria-label="ห้องเรียน"
            className="field-input w-32"
            value={classId}
            onChange={(event) => setClassId(event.target.value)}
          />
          <button className="secondary-button" type="button" onClick={loadCredentials} disabled={Boolean(busy)}>
            <RefreshCcw size={16} /> โหลดข้อมูล
          </button>
        </div>
      </div>

      {error ? <p role="alert" className="mt-4 rounded-md bg-rose-50 p-3 text-sm font-semibold text-rose-700">{error}</p> : null}
      {success ? <p className="mt-4 rounded-md bg-emerald-50 p-3 text-sm font-semibold text-emerald-800">{success}</p> : null}

      {!data ? (
        <div className="mt-5 rounded-lg border border-dashed border-[#12372A]/25 bg-white/45 p-6 text-center text-sm text-slate-600">
          เลือกห้องเรียนแล้วกดโหลดข้อมูลเพื่อดูสถานะการเชื่อมต่อ AI
        </div>
      ) : (
        <div className="mt-5 grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
          <form onSubmit={saveCredential} className="rounded-lg border border-[#12372A]/15 bg-white/70 p-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="grid gap-2">
                <span className="field-label">ผู้ให้บริการ AI</span>
                <select
                  className="field-input"
                  value={providerId}
                  onChange={(event) => {
                    const nextProviderId = event.target.value as Provider["provider_id"];
                    const nextProvider = data.providers.find((provider) => provider.provider_id === nextProviderId);
                    setProviderId(nextProviderId);
                    setModel(nextProvider?.model || nextProvider?.allowed_models[0] || "");
                    setApiKey("");
                  }}
                >
                  {data.providers.map((provider) => <option key={provider.provider_id} value={provider.provider_id}>{provider.display_name}</option>)}
                </select>
              </label>
              <label className="grid gap-2">
                <span className="field-label">โมเดลที่ใช้งาน</span>
                <select className="field-input" value={model} onChange={(event) => setModel(event.target.value)}>
                  {(selected?.allowed_models || []).map((allowedModel) => <option key={allowedModel}>{allowedModel}</option>)}
                </select>
              </label>
            </div>

            <div className="mt-4 rounded-md border border-[#F4B942]/35 bg-[#FFF8E7] p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="flex items-center gap-2 text-sm font-semibold text-[#12372A]">
                  <ShieldCheck size={17} /> {selected?.masked_key || "ยังไม่ได้ตั้งค่า API key"}
                </span>
                <span className="rounded-full bg-white px-2.5 py-1 font-mono text-[11px] font-bold uppercase text-[#12372A]">
                  {selected?.status || "not_configured"}
                </span>
              </div>
              {selected?.last_error_type ? (
                <details className="mt-2 text-xs text-rose-700">
                  <summary className="cursor-pointer font-semibold">รายละเอียดทางเทคนิค</summary>
                  <p className="mt-1 font-mono">{selected.last_error_type}</p>
                </details>
              ) : null}
            </div>

            <label className="mt-4 grid gap-2">
              <span className="field-label">API key ใหม่</span>
              <input
                className="field-input font-mono"
                type="password"
                autoComplete="new-password"
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                placeholder={selected?.configured ? "กรอก key ใหม่เพื่อแทนที่" : "กรอก API key"}
              />
              <span className="text-xs text-slate-500">ระบบจะไม่แสดง key ฉบับเต็มหลังบันทึก</span>
            </label>

            <div className="mt-4 flex flex-wrap gap-2">
              <button className="secondary-button" type="button" onClick={validateKey} disabled={Boolean(busy)}>
                {busy === "validate" ? <LoaderCircle className="animate-spin" size={16} /> : <CheckCircle2 size={16} />} ทดสอบการเชื่อมต่อ
              </button>
              <button className="primary-button" type="submit" disabled={Boolean(busy)}>
                <Save size={16} /> {selected?.configured ? "เปลี่ยน API key" : "บันทึก API key"}
              </button>
              <button className="secondary-button" type="button" onClick={disableCredential} disabled={Boolean(busy) || !selected?.configured || selected.status === "disabled"}>
                <ShieldCheck size={16} /> ปิดใช้งาน
              </button>
              <button className="danger-button" type="button" onClick={deleteCredential} disabled={Boolean(busy) || !selected?.configured}>
                <Trash2 size={16} /> ลบ
              </button>
            </div>
          </form>

          <div className="rounded-lg border border-[#12372A]/15 bg-white/70 p-4">
            <h3 className="font-semibold text-[#12372A]">การใช้งานสำรองและขีดจำกัด</h3>
            <label className="mt-4 flex items-center justify-between gap-4 rounded-md bg-[#FFF8E7] p-3 text-sm font-semibold text-[#12372A]">
              อนุญาตให้ใช้ระบบ AI สำรอง
              <input type="checkbox" checked={fallbackEnabled} onChange={(event) => setFallbackEnabled(event.target.checked)} />
            </label>
            <label className="mt-4 grid gap-2">
              <span className="field-label">จำนวนคำขอสำรองต่อวัน</span>
              <input className="field-input" type="number" min={0} max={1000} value={requestBudget} onChange={(event) => setRequestBudget(Number(event.target.value))} />
            </label>
            <label className="mt-4 grid gap-2">
              <span className="field-label">จำนวน token สำรองต่อวัน</span>
              <input className="field-input" type="number" min={0} max={10000000} value={tokenBudget} onChange={(event) => setTokenBudget(Number(event.target.value))} />
            </label>
            <button className="primary-button mt-4 w-full" type="button" onClick={saveSettings} disabled={Boolean(busy)}>
              <Save size={16} /> บันทึกการตั้งค่า
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
