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
      <section className="login-brand-panel">
        <div className="login-brand">
          <span><Bot size={24} /></span>
          <div>
            <strong>MTC Assistant</strong>
            <small>MTC Dashboard</small>
          </div>
        </div>
        <div className="login-brand-copy">
          <h2>พื้นที่จัดการงานห้องเรียน</h2>
          <p>ดูข้อมูลล่าสุด จัดการลิงก์ และดูแลเครื่องมือของ MTC Assistant ในที่เดียว</p>
        </div>
        <div className="login-pattern" aria-hidden="true" />
      </section>
      <section className="login-form-panel">
        <div className="login-form-wrap">
          <p className="login-product">MTC Assistant</p>
          <h1>เข้าสู่ระบบ MTC Dashboard</h1>
          <p className="login-description">จัดการข้อมูลและการใช้งานของห้องเรียน MTC Assistant</p>
          <form onSubmit={submit} className="login-form">
            <label htmlFor="password">
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
              aria-describedby={error ? "login-error" : "login-help"}
              required
            />
            {error ? (
              <p id="login-error" className="login-error" role="alert">
                {error}
              </p>
            ) : <p id="login-help" className="login-help">สำหรับผู้ดูแลระบบและผู้ที่ได้รับอนุญาต</p>}
            <button type="submit" disabled={loading} className="button primary">
              {loading ? "กำลังเข้าสู่ระบบ..." : "เข้าสู่แดชบอร์ด"}
              <ArrowRight size={17} />
            </button>
          </form>
        </div>
      </section>
    </main>
  );
}
