"use client";

import { LogOut, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";

import type { DashboardPrincipal, DashboardRole } from "@/lib/flask-auth-types";

const ROLE_LABELS: Record<DashboardRole, string> = {
  student: "นักเรียน",
  teacher: "ครู",
  class_admin: "ผู้ดูแลห้องเรียน",
  super_admin: "ผู้ดูแลระบบส่วนกลาง",
  unknown: "บทบาทที่ยังไม่รองรับ",
};

export function LimitedRoleState({
  principal,
}: {
  principal: DashboardPrincipal;
}) {
  const [signingOut, setSigningOut] = useState(false);

  async function logout() {
    if (signingOut) return;
    setSigningOut(true);
    try {
      await fetch("/api/logout", { method: "POST" });
    } finally {
      window.location.assign("/login");
    }
  }

  const identity = principal.display_name || principal.username;
  return (
    <main className="auth-state-shell">
      <section className="surface auth-state-card">
        <span className="auth-state-icon" aria-hidden="true">
          <ShieldCheck size={24} />
        </span>
        <p className="login-product">เข้าสู่ระบบแล้ว</p>
        <h1>พื้นที่ทำงานสำหรับบทบาทนี้ยังไม่เปิดใช้งาน</h1>
        <p>
          บัญชี <strong>{identity}</strong> เข้าสู่ระบบในบทบาท{" "}
          <strong>{ROLE_LABELS[principal.role]}</strong> สำเร็จแล้ว
        </p>
        <p>
          ขณะนี้เครื่องมือส่วนกลางเปิดให้เฉพาะผู้ดูแลระบบส่วนกลางเท่านั้น
          พื้นที่ทำงานเฉพาะบทบาทจะเพิ่มในระยะถัดไป
        </p>
        <button
          type="button"
          className="button secondary"
          onClick={logout}
          disabled={signingOut}
        >
          <LogOut size={17} />
          {signingOut ? "กำลังออกจากระบบ..." : "ออกจากระบบ"}
        </button>
      </section>
    </main>
  );
}

export function AuthUnavailableState() {
  return (
    <main className="auth-state-shell">
      <section className="surface auth-state-card">
        <p className="login-product">MTC Assistant</p>
        <h1>ระบบยืนยันตัวตนไม่พร้อมใช้งานชั่วคราว</h1>
        <p>
          ระบบยังไม่ยืนยันว่าคุณออกจากระบบ กรุณารอสักครู่แล้วโหลดหน้านี้ใหม่
        </p>
      </section>
    </main>
  );
}

export function InvalidSessionState() {
  const [message, setMessage] = useState("กำลังล้างข้อมูลการเข้าสู่ระบบ...");

  useEffect(() => {
    let active = true;
    async function clearAndRedirect() {
      try {
        await fetch("/api/logout", { method: "POST" });
      } finally {
        if (active) window.location.assign("/login");
      }
    }
    void clearAndRedirect();
    return () => {
      active = false;
    };
  }, []);

  async function retry() {
    try {
      await fetch("/api/logout", { method: "POST" });
    } finally {
      setMessage("กำลังกลับไปหน้าเข้าสู่ระบบ...");
      window.location.assign("/login");
    }
  }

  return (
    <main className="auth-state-shell">
      <section className="surface auth-state-card">
        <p>{message}</p>
        <button type="button" className="button secondary" onClick={retry}>
          กลับไปหน้าเข้าสู่ระบบ
        </button>
      </section>
    </main>
  );
}
