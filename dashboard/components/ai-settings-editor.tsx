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
    throw new Error(message || "AI settings request failed.");
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
      setError(loadError instanceof Error ? loadError.message : "Could not load AI settings.");
    } finally {
      setBusy("");
    }
  }

  async function validateKey() {
    if (!apiKey.trim()) {
      setError("Enter a new API key before testing.");
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
      setSuccess("Connection validated. The key has not been saved yet.");
    } catch (validateError) {
      setError(validateError instanceof Error ? validateError.message : "Validation failed.");
    } finally {
      setBusy("");
    }
  }

  async function saveCredential(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!apiKey.trim()) {
      setError("Enter a new API key to save or replace this credential.");
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
      setSuccess("Credential encrypted and saved. The full key cannot be displayed again.");
      await loadCredentials();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Could not save credential.");
    } finally {
      setBusy("");
    }
  }

  async function deleteCredential() {
    if (!selected?.configured || !window.confirm(`Delete the ${selected.display_name} credential?`)) {
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
      setSuccess("Credential deleted. System fallback remains governed by class policy.");
      await loadCredentials();
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Could not delete credential.");
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
      setSuccess("Credential disabled. It will not be selected for new requests.");
    } catch (disableError) {
      setError(disableError instanceof Error ? disableError.message : "Could not disable credential.");
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
      setSuccess("Class AI policy saved.");
    } catch (settingsError) {
      setError(settingsError instanceof Error ? settingsError.message : "Could not save policy.");
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
            <h2 className="mt-1 text-xl font-semibold text-[#12372A]">Class AI credentials</h2>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-600">
              Super-admin managed class provider keys. Keys are encrypted by Flask and are never returned after submission.
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <input
            aria-label="Class ID"
            className="field-input w-32"
            value={classId}
            onChange={(event) => setClassId(event.target.value)}
          />
          <button className="secondary-button" type="button" onClick={loadCredentials} disabled={Boolean(busy)}>
            <RefreshCcw size={16} /> Load
          </button>
        </div>
      </div>

      {error ? <p role="alert" className="mt-4 rounded-md bg-rose-50 p-3 text-sm font-semibold text-rose-700">{error}</p> : null}
      {success ? <p className="mt-4 rounded-md bg-emerald-50 p-3 text-sm font-semibold text-emerald-800">{success}</p> : null}

      {!data ? (
        <div className="mt-5 rounded-lg border border-dashed border-[#12372A]/25 bg-white/45 p-6 text-center text-sm text-slate-600">
          Load a class to inspect credentials and fallback policy.
        </div>
      ) : (
        <div className="mt-5 grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
          <form onSubmit={saveCredential} className="rounded-lg border border-[#12372A]/15 bg-white/70 p-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="grid gap-2">
                <span className="field-label">Provider</span>
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
                <span className="field-label">Allowed model</span>
                <select className="field-input" value={model} onChange={(event) => setModel(event.target.value)}>
                  {(selected?.allowed_models || []).map((allowedModel) => <option key={allowedModel}>{allowedModel}</option>)}
                </select>
              </label>
            </div>

            <div className="mt-4 rounded-md border border-[#F4B942]/35 bg-[#FFF8E7] p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="flex items-center gap-2 text-sm font-semibold text-[#12372A]">
                  <ShieldCheck size={17} /> {selected?.masked_key || "No key configured"}
                </span>
                <span className="rounded-full bg-white px-2.5 py-1 font-mono text-[11px] font-bold uppercase text-[#12372A]">
                  {selected?.status || "not_configured"}
                </span>
              </div>
              {selected?.last_error_type ? <p className="mt-2 text-xs text-rose-700">Last safe error: {selected.last_error_type}</p> : null}
            </div>

            <label className="mt-4 grid gap-2">
              <span className="field-label">New API key</span>
              <input
                className="field-input font-mono"
                type="password"
                autoComplete="new-password"
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                placeholder={selected?.configured ? "Enter a replacement key" : "Enter provider API key"}
              />
              <span className="text-xs text-slate-500">No reveal action. Replacing a key requires entering it again.</span>
            </label>

            <div className="mt-4 flex flex-wrap gap-2">
              <button className="secondary-button" type="button" onClick={validateKey} disabled={Boolean(busy)}>
                {busy === "validate" ? <LoaderCircle className="animate-spin" size={16} /> : <CheckCircle2 size={16} />} Test connection
              </button>
              <button className="primary-button" type="submit" disabled={Boolean(busy)}>
                <Save size={16} /> {selected?.configured ? "Replace key" : "Save key"}
              </button>
              <button className="secondary-button" type="button" onClick={disableCredential} disabled={Boolean(busy) || !selected?.configured || selected.status === "disabled"}>
                <ShieldCheck size={16} /> Disable
              </button>
              <button className="danger-button" type="button" onClick={deleteCredential} disabled={Boolean(busy) || !selected?.configured}>
                <Trash2 size={16} /> Delete
              </button>
            </div>
          </form>

          <div className="rounded-lg border border-[#12372A]/15 bg-white/70 p-4">
            <h3 className="font-semibold text-[#12372A]">Fallback and usage budget</h3>
            <label className="mt-4 flex items-center justify-between gap-4 rounded-md bg-[#FFF8E7] p-3 text-sm font-semibold text-[#12372A]">
              System fallback
              <input type="checkbox" checked={fallbackEnabled} onChange={(event) => setFallbackEnabled(event.target.checked)} />
            </label>
            <label className="mt-4 grid gap-2">
              <span className="field-label">Daily fallback requests</span>
              <input className="field-input" type="number" min={0} max={1000} value={requestBudget} onChange={(event) => setRequestBudget(Number(event.target.value))} />
            </label>
            <label className="mt-4 grid gap-2">
              <span className="field-label">Daily fallback tokens</span>
              <input className="field-input" type="number" min={0} max={10000000} value={tokenBudget} onChange={(event) => setTokenBudget(Number(event.target.value))} />
            </label>
            <button className="primary-button mt-4 w-full" type="button" onClick={saveSettings} disabled={Boolean(busy)}>
              <Save size={16} /> Save class policy
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
