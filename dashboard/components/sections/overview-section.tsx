"use client";

import { useQuery } from "@tanstack/react-query";
import { BookOpenCheck, Link, MessageSquareText, Users } from "lucide-react";
import { apiGet } from "@/lib/dashboard-api";
import type { DashboardSection } from "@/lib/dashboard-sections";
import type { Overview } from "@/lib/dashboard-types";
import { BroadcastList, HomeworkList } from "./section-content";
import { InlineAlert, PageHeader, ServiceStatusBadge, Surface } from "@/components/ui/dashboard-ui";

export function OverviewSection({
  onNavigate,
}: {
  onNavigate: (section: DashboardSection) => void;
}) {
  const query = useQuery({
    queryKey: ["overview"],
    queryFn: () => apiGet<Overview>("overview"),
  });
  const overview = query.data;
  return (
    <>
      <PageHeader
        title="ภาพรวม"
        description="งานประจำและข้อมูลล่าสุดที่ควรตรวจสอบ"
        context="ข้อมูลรวมทั้งระบบ"
        action={<button className="button secondary" onClick={() => query.refetch()}>อัปเดตข้อมูล</button>}
      />
      {query.isError ? (
        <InlineAlert title="ไม่สามารถโหลดภาพรวมได้" error={query.error}>
          กรุณาอัปเดตข้อมูลอีกครั้ง
        </InlineAlert>
      ) : null}
      <section className="quick-actions-section" aria-labelledby="quick-actions-title">
        <h2 id="quick-actions-title">งานที่ใช้บ่อย</h2>
        <div className="quick-actions">
          <button onClick={() => onNavigate("announcements")}><MessageSquareText size={19} /><span>ส่งประกาศถึงผู้ใช้ทั้งหมด</span></button>
          <button onClick={() => onNavigate("resources")}><Link size={19} /><span>จัดการลิงก์พื้นฐาน</span></button>
          <button onClick={() => onNavigate("members")}><Users size={19} /><span>ค้นหาบัญชี LINE</span></button>
        </div>
      </section>
      <div className="summary-grid">
        <Summary label="บัญชี LINE ที่เชื่อมต่อ" value={overview?.counts.registered_users} icon={Users} loading={query.isLoading} />
        <Summary label="การบ้านที่แสดงล่าสุด" value={overview?.counts.active_homework_preview} icon={BookOpenCheck} loading={query.isLoading} />
        <Summary label="ประกาศล่าสุด" value={overview?.counts.recent_broadcasts} icon={MessageSquareText} loading={query.isLoading} />
        <Surface title="สถานะบริการหลัก" className="service-summary">
          <div className="service-inline">
            {(["line", "firebase", "gemini", "broadcast"] as const).map((key) => (
              <span key={key}>
                {key === "gemini" ? "AI" : key === "broadcast" ? "Broadcast" : key.toUpperCase()}
                <ServiceStatusBadge
                  loading={query.isLoading}
                  error={query.isError}
                  available={overview?.services[key]}
                />
              </span>
            ))}
          </div>
        </Surface>
      </div>
      <div className="two-column">
        <Surface title="การบ้านล่าสุด" action={<button className="text-button" onClick={() => onNavigate("homework")}>ดูเพิ่มเติม</button>}>
          <HomeworkList items={overview?.homework_preview || []} loading={query.isLoading} />
        </Surface>
        <Surface title="ประกาศล่าสุด" action={<button className="text-button" onClick={() => onNavigate("announcements")}>ส่งประกาศ</button>}>
          <BroadcastList items={overview?.recent_broadcasts || []} loading={query.isLoading} />
        </Surface>
      </div>
    </>
  );
}

function Summary({
  label,
  value,
  icon: Icon,
  loading,
}: {
  label: string;
  value?: number;
  icon: typeof Users;
  loading: boolean;
}) {
  return (
    <Surface className="summary-card">
      <Icon size={20} />
      <strong>{loading ? "…" : value ?? 0}</strong>
      <span>{label}</span>
    </Surface>
  );
}
