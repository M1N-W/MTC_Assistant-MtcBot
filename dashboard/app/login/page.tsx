import { Bot } from "lucide-react";

import {
  AuthConfigurationError,
  getDashboardAuthMode,
} from "@/lib/auth-mode";
import { LoginForm } from "@/components/login-form";

export default function LoginPage() {
  let mode;
  try {
    mode = getDashboardAuthMode();
  } catch (caught) {
    if (caught instanceof AuthConfigurationError) {
      return (
        <main className="auth-state-shell">
          <section className="surface auth-state-card">
            <p className="login-product">MTC Assistant</p>
            <h1>ระบบเข้าสู่ระบบยังตั้งค่าไม่สมบูรณ์</h1>
            <p>กรุณาติดต่อผู้ดูแลระบบเพื่อตรวจสอบการตั้งค่าการยืนยันตัวตน</p>
          </section>
        </main>
      );
    }
    throw caught;
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
          <LoginForm mode={mode} />
        </div>
      </section>
    </main>
  );
}

export const dynamic = "force-dynamic";
export const revalidate = 0;
