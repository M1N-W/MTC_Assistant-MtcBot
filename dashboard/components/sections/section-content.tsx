"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";
import type { BroadcastRecord, Homework } from "@/lib/dashboard-types";
import { formatDateTime, maskLineUserId } from "@/lib/dashboard-formatters";
import { EmptyState, LoadingState, StatusBadge } from "@/components/ui/dashboard-ui";

export function HomeworkList({
  items,
  loading,
}: {
  items: Homework[];
  loading?: boolean;
}) {
  if (loading) return <LoadingState />;
  if (!items.length) return <EmptyState>ยังไม่มีการบ้าน</EmptyState>;
  return (
    <div className="record-list">
      {items.map((item) => (
        <article key={item.id}>
          <div>
            <strong>{item.subject || "การบ้าน"}</strong>
            <p>{item.detail || "ไม่มีรายละเอียดเพิ่มเติม"}</p>
          </div>
          <small>{item.due_date || formatDateTime(item.created_at)}</small>
        </article>
      ))}
    </div>
  );
}

export function BroadcastList({
  items,
  loading,
}: {
  items: BroadcastRecord[];
  loading?: boolean;
}) {
  if (loading) return <LoadingState />;
  if (!items.length) return <EmptyState>ยังไม่มีประกาศ</EmptyState>;
  return (
    <div className="record-list">
      {items.map((item) => (
        <article key={item.id}>
          <div>
            <strong>{item.message || "ประกาศ"}</strong>
            <p>
              ส่งสำเร็จ {item.sent_count || 0} · ส่งไม่สำเร็จ {item.failed_count || 0}
            </p>
          </div>
          <StatusBadge tone={item.success === false ? "warning" : "success"}>
            {item.success === false ? "มีบางรายการไม่สำเร็จ" : "ส่งแล้ว"}
          </StatusBadge>
        </article>
      ))}
    </div>
  );
}

export function MaskedLineId({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }
  return (
    <div className="masked-id">
      <code>{maskLineUserId(value)}</code>
      <button type="button" className="icon-button" onClick={copy} aria-label="คัดลอก LINE User ID">
        {copied ? <Check size={17} /> : <Copy size={17} />}
      </button>
      <span className="sr-only" role="status">{copied ? "คัดลอกแล้ว" : ""}</span>
    </div>
  );
}
