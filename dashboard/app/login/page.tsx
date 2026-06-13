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
      setError(
        response.status === 503
          ? "ระบบเข้าสู่ระบบยังไม่พร้อมใช้งาน กรุณาติดต่อผู้ดูแลระบบ"
          : "รหัสผ่านไม่ถูกต้อง กรุณาลองอีกครั้ง",
      );
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
            <p className="mt-6 text-sm font-semibold text-emerald-700">
              MTC Assistant
            </p>
            <h1 className="mt-2 text-2xl font-semibold tracking-[-0.01em] text-emerald-950">
              เข้าสู่ระบบ MTC Dashboard
            </h1>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              จัดการข้อมูลและการใช้งานของห้องเรียน MTC Assistant
            </p>
          </div>

          <form onSubmit={submit} className="mt-8 grid gap-4">
            <label className="login-field-label" htmlFor="password">
              <LockKeyhole size={15} />
              รหัสผ่าน
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
              {loading ? "กำลังเข้าสู่ระบบ..." : "เข้าสู่แดชบอร์ด"}
              <ArrowRight size={17} />
            </button>
          </form>
        </section>
      </div>
    </main>
  );
}
