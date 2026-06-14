"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { Ban, Camera, Upload } from "lucide-react";
import { apiGet, apiSend, apiUpload, validationError } from "@/lib/dashboard-api";
import { formatDateTime, formatDuration, maskLineUserId } from "@/lib/dashboard-formatters";
import type {
  BlacklistRow,
  Overview,
  PaperlessCaptureResult,
  PaperlessSummary,
} from "@/lib/dashboard-types";
import {
  EmptyState,
  InlineAlert,
  LoadingState,
  PageHeader,
  ServiceStatusBadge,
  Surface,
} from "@/components/ui/dashboard-ui";

const MAX_CAPTURE_BYTES = 6 * 1024 * 1024;
const ALLOWED_CAPTURE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

export function SystemSection() {
  const queryClient = useQueryClient();
  const [userId, setUserId] = useState("");
  const [reason, setReason] = useState("");
  const [captureFile, setCaptureFile] = useState<File | null>(null);
  const [captureResult, setCaptureResult] = useState<PaperlessCaptureResult | null>(null);
  const overview = useQuery({ queryKey: ["overview"], queryFn: () => apiGet<Overview>("overview") });
  const blacklist = useQuery({ queryKey: ["blacklist"], queryFn: () => apiGet<{ items: BlacklistRow[] }>("blacklist") });
  const paperless = useQuery({
    queryKey: ["paperless-summary"],
    queryFn: () => apiGet<PaperlessSummary>("paperless-captures/summary"),
  });
  const ban = useMutation({
    mutationFn: () => {
      if (!userId.trim()) throw validationError("กรุณากรอก LINE User ID");
      if (!reason.trim()) throw validationError("กรุณากรอกเหตุผล");
      return apiSend("blacklist", "POST", { user_id: userId.trim(), reason: reason.trim() });
    },
    onSuccess: () => {
      setUserId("");
      setReason("");
      void queryClient.invalidateQueries({ queryKey: ["blacklist"] });
    },
  });
  const unban = useMutation({
    mutationFn: (id: string) => apiSend(`blacklist/${encodeURIComponent(id)}`, "DELETE"),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["blacklist"] }),
  });
  const capture = useMutation({
    mutationFn: (file: File | null) => {
      if (!file) throw validationError("กรุณาเลือกภาพก่อนเริ่มวิเคราะห์");
      if (!ALLOWED_CAPTURE_TYPES.has(file.type)) throw validationError("รองรับเฉพาะไฟล์ PNG, JPEG และ WEBP");
      if (file.size > MAX_CAPTURE_BYTES) throw validationError("ไฟล์ภาพต้องมีขนาดไม่เกิน 6 MB");
      return apiUpload<PaperlessCaptureResult>("paperless-capture", file);
    },
    onSuccess: (result) => {
      setCaptureResult(result);
      void queryClient.invalidateQueries({ queryKey: ["paperless-summary"] });
    },
  });
  const metrics = overview.data?.metrics;
  return (
    <>
      <PageHeader title="ระบบ" description="สถานะบริการ ประสิทธิภาพ เครื่องมือทดลอง และการดูแลความปลอดภัย" context="ข้อมูลรวมทั้งระบบ" />
      <Surface title="สถานะระบบ">
        {overview.isError ? <InlineAlert title="ไม่สามารถโหลดสถานะระบบได้" error={overview.error}>กรุณาลองอัปเดตข้อมูลอีกครั้ง</InlineAlert> : null}
        <div className="service-grid">
          {(["line", "firebase", "gemini", "broadcast"] as const).map((key) => (
            <div key={key}>
              <strong>{key === "gemini" ? "AI" : key === "broadcast" ? "Broadcast" : key.toUpperCase()}</strong>
              <ServiceStatusBadge
                loading={overview.isLoading}
                error={overview.isError}
                available={overview.data?.services[key]}
              />
            </div>
          ))}
        </div>
      </Surface>
      <Surface title="ประสิทธิภาพ" description="ข้อมูลจริงจาก runtime ปัจจุบัน">
        <div className="metric-list">
          <Metric label="คำขอทั้งหมด" value={metrics?.total_requests ?? "…"} />
          <Metric label="ข้อผิดพลาดทั้งหมด" value={metrics?.total_errors ?? "…"} />
          <Metric label="เวลาตอบสนองเฉลี่ย" value={metrics ? `${metrics.avg_response_time_ms} ms` : "…"} />
          <Metric label="เวลาที่ระบบทำงาน" value={metrics ? formatDuration(metrics.uptime_seconds) : "…"} />
        </div>
      </Surface>
      <div className="two-column">
        <Surface title="AI อ่านภาพห้องเรียน" description="เครื่องมือทดลอง">
          <div className="paperless-summary">
            {paperless.isLoading ? <LoadingState rows={2} /> : null}
            {paperless.isError ? <InlineAlert title="ไม่สามารถโหลดประวัติการวิเคราะห์ได้" error={paperless.error}>กรุณาลองอีกครั้ง</InlineAlert> : null}
            {paperless.data ? (
              <>
                <strong>วิเคราะห์สำเร็จทั้งหมด {paperless.data.successful_capture_count} ครั้ง</strong>
                <p>วิเคราะห์ล่าสุด {formatDateTime(paperless.data.latest_success_at)}</p>
                <p>พบรายการที่อาจเป็นการบ้านในผลล่าสุด {paperless.data.recent[0]?.homework_candidate_count || 0} รายการ</p>
              </>
            ) : null}
          </div>
          <form onSubmit={(event) => { event.preventDefault(); capture.mutate(captureFile); }} className="form-stack">
            <label htmlFor="paperless-image">ภาพจากห้องเรียน</label>
            <label className="upload-field" htmlFor="paperless-image">
              <Camera size={22} />
              <span>{captureFile?.name || "เลือกภาพกระดาน ใบงาน หรือประกาศ"}</span>
            </label>
            <input
              id="paperless-image"
              type="file"
              accept="image/png,image/jpeg,image/webp"
              onChange={(event) => {
                setCaptureFile(event.target.files?.[0] || null);
                setCaptureResult(null);
                capture.reset();
              }}
              className="sr-only"
            />
            <button className="button primary" disabled={capture.isPending}><Upload size={17} />{capture.isPending ? "กำลังวิเคราะห์..." : "วิเคราะห์ภาพ"}</button>
            {capture.isError ? <InlineAlert title="ไม่สามารถวิเคราะห์ภาพได้" error={capture.error}>ไฟล์ที่เลือกยังอยู่ กรุณาตรวจสอบแล้วลองอีกครั้ง</InlineAlert> : null}
          </form>
          {captureResult ? (
            <div className="capture-result">
              <strong>{captureResult.analysis.title}</strong>
              <ul>{captureResult.analysis.summary.map((item) => <li key={item}>{item}</li>)}</ul>
            </div>
          ) : paperless.data?.successful_capture_count === 0 ? <EmptyState>ยังไม่มีประวัติการวิเคราะห์ภาพ</EmptyState> : null}
        </Surface>
        <Surface title="ความปลอดภัย" description="จัดการบัญชี LINE ที่ถูกระงับ">
          <form onSubmit={(event: FormEvent) => { event.preventDefault(); ban.mutate(); }} className="form-stack">
            <label htmlFor="ban-user-id">LINE User ID</label>
            <input id="ban-user-id" value={userId} onChange={(event) => setUserId(event.target.value)} required />
            <label htmlFor="ban-reason">เหตุผล</label>
            <input id="ban-reason" value={reason} onChange={(event) => setReason(event.target.value)} maxLength={240} required />
            <button className="button danger" disabled={ban.isPending}><Ban size={17} />ระงับการใช้งาน</button>
            {ban.isError ? <InlineAlert title="ไม่สามารถระงับการใช้งานได้" error={ban.error}>ข้อมูลที่กรอกยังอยู่ กรุณาลองอีกครั้ง</InlineAlert> : null}
          </form>
          <div className="blacklist-list">
            {blacklist.isLoading ? <LoadingState /> : null}
            {blacklist.data?.items.map((item) => (
              <div key={item.user_id}>
                <span><code>{maskLineUserId(item.user_id)}</code><small>{item.reason}</small></span>
                <button className="button secondary compact" onClick={() => unban.mutate(item.user_id)} disabled={unban.isPending}>ยกเลิกการระงับ</button>
              </div>
            ))}
            {blacklist.data?.items.length === 0 ? <EmptyState>ยังไม่มีบัญชีที่ถูกระงับ</EmptyState> : null}
          </div>
        </Surface>
      </div>
      <Surface title="รายละเอียดทางเทคนิค">
        <details>
          <summary>ดูข้อมูล runtime ที่ปลอดภัย</summary>
          <dl className="technical-details">
            <div><dt>อัตราข้อผิดพลาด</dt><dd>{metrics?.error_rate_percent ?? 0}%</dd></div>
            <div><dt>อัปเดตล่าสุด</dt><dd>{formatDateTime(overview.data?.generated_at)}</dd></div>
          </dl>
        </details>
      </Surface>
    </>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return <div><span>{label}</span><strong>{value}</strong></div>;
}
