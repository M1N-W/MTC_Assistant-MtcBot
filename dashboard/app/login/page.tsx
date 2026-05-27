"use client";

import { FormEvent, useState } from "react";
import { ArrowRight, Bot, LockKeyhole } from "lucide-react";

export default function LoginPage() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    const response = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    setLoading(false);
    if (!response.ok) {
      setError(response.status === 503 ? "Dashboard auth is not configured." : "Password is incorrect.");
      return;
    }
    window.location.href = "/";
  }

  return (
    <main className="login-shell">
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="mission-grid" />
        <div className="login-ambient login-ambient-cyan" />
        <div className="login-ambient login-ambient-lime" />
      </div>

      <div className="relative mx-auto flex min-h-[calc(100svh-3rem)] items-center justify-center">
        <section className="login-card w-full">
          <div className="flex flex-col items-center text-center">
            <div className="login-mark">
              <Bot size={26} strokeWidth={2.5} />
            </div>
            <p className="mt-6 font-mono text-[11px] font-semibold uppercase tracking-[0.22em] text-cyan-100/76">
              [ SYSTEM AUTHENTICATION ]
            </p>
            <h1 className="mt-3 text-2xl font-semibold tracking-[-0.01em] text-white">
              MTC Assistant
            </h1>
            <p className="mt-2 text-sm leading-6 text-cyan-50/62">
              Secure access to the NSC operations console.
            </p>
          </div>

          <form onSubmit={submit} className="mt-8 grid gap-4">
            <label className="login-field-label" htmlFor="password">
              <LockKeyhole size={15} />
              Dashboard password
            </label>
            <input
              className="sr-only"
              type="text"
              name="username"
              autoComplete="username"
              value="mtc-dashboard-admin"
              readOnly
              tabIndex={-1}
            />
            <input
              id="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              autoComplete="current-password"
              className="mission-input login-password-input h-12 px-4 text-base"
              required
            />
            {error ? (
              <p className="login-error" role="alert">
                {error}
              </p>
            ) : null}
            <button type="submit" disabled={loading} className="primary-button h-12 justify-center">
              {loading ? "Signing in..." : "Open dashboard"}
              <ArrowRight size={17} />
            </button>
          </form>
        </section>
      </div>
    </main>
  );
}
