"use client";

import { FormEvent, useState } from "react";
import { ArrowRight, LockKeyhole, UserRound } from "lucide-react";

import type { DashboardAuthMode } from "@/lib/auth-mode";

export function LoginForm({ mode }: { mode: DashboardAuthMode }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (loading) return;
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          mode === "flask" ? { username, password } : { password },
        ),
      });
      if (!response.ok) {
        setError(
          response.status === 503
            ? "ระบบยืนยันตัวตนไม่พร้อมใช้งานในขณะนี้ กรุณาลองใหม่ภายหลัง"
            : mode === "flask"
              ? "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"
              : "รหัสผ่านไม่ถูกต้อง กรุณาลองอีกครั้ง",
        );
        return;
      }
      window.location.assign("/");
    } catch {
      setError("ระบบยืนยันตัวตนไม่พร้อมใช้งานในขณะนี้ กรุณาลองใหม่ภายหลัง");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={submit} className="login-form">
      {mode === "flask" ? (
        <>
          <label htmlFor="username">
            <UserRound size={15} />
            ชื่อผู้ใช้
          </label>
          <input
            id="username"
            name="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            type="text"
            autoComplete="username"
            aria-describedby={error ? "login-error" : "login-help"}
            required
          />
        </>
      ) : (
        <input
          className="sr-only"
          type="text"
          name="username"
          autoComplete="username"
          value="mtc-dashboard-admin"
          readOnly
          tabIndex={-1}
        />
      )}
      <label htmlFor="password">
        <LockKeyhole size={15} />
        รหัสผ่าน
      </label>
      <input
        id="password"
        name="password"
        value={password}
        onChange={(event) => setPassword(event.target.value)}
        type="password"
        autoComplete="current-password"
        aria-describedby={error ? "login-error" : "login-help"}
        required
      />
      {error ? (
        <p id="login-error" className="login-error" role="alert">
          {error}
        </p>
      ) : (
        <p id="login-help" className="login-help">
          สำหรับผู้ใช้ที่ได้รับสิทธิ์จากผู้ดูแลระบบ
        </p>
      )}
      <button type="submit" disabled={loading} className="button primary">
        {loading ? "กำลังเข้าสู่ระบบ..." : "เข้าสู่แดชบอร์ด"}
        <ArrowRight size={17} />
      </button>
    </form>
  );
}
