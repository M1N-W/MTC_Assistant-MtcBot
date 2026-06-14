"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { apiGet, apiSend, validationError } from "@/lib/dashboard-api";
import type { BroadcastRecord } from "@/lib/dashboard-types";
import { BroadcastList } from "./section-content";
import { Dialog, InlineAlert, PageHeader, Surface } from "@/components/ui/dashboard-ui";

export function AnnouncementsSection() {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState("");
  const [previewOpen, setPreviewOpen] = useState(false);
  const history = useQuery({
    queryKey: ["broadcasts"],
    queryFn: () => apiGet<{ items: BroadcastRecord[] }>("broadcasts?limit=20"),
  });
  const send = useMutation({
    mutationFn: (value: string) => {
      if (!value) throw validationError("กรุณากรอกข้อความประกาศ");
      if (value.length > 1000) throw validationError("ข้อความประกาศต้องไม่เกิน 1,000 ตัวอักษร");
      return apiSend("broadcasts", "POST", { message: value });
    },
    onSuccess: () => {
      setMessage("");
      setPreviewOpen(false);
      void queryClient.invalidateQueries({ queryKey: ["broadcasts"] });
      void queryClient.invalidateQueries({ queryKey: ["overview"] });
    },
  });
  function preview(event: FormEvent) {
    event.preventDefault();
    const value = message.trim();
    if (!value) {
      send.mutate(value);
      return;
    }
    setPreviewOpen(true);
  }
  return (
    <>
      <PageHeader title="ประกาศ" description="เขียนและส่งข้อความผ่าน LINE ถึงผู้ใช้ทั้งหมดที่ลงทะเบียนในระบบ" context="ข้อมูลรวมทั้งระบบ" />
      <div className="two-column announcements-layout">
        <Surface title="ส่งประกาศถึงผู้ใช้ทั้งหมด">
          <form onSubmit={preview} className="form-stack">
            <label htmlFor="broadcast-message">ข้อความประกาศ</label>
            <textarea
              id="broadcast-message"
              value={message}
              onChange={(event) => {
                setMessage(event.target.value);
                send.reset();
              }}
              maxLength={1000}
              rows={8}
              placeholder="พิมพ์ข้อความประกาศ"
              required
            />
            <p className="field-help">ข้อความนี้จะถูกส่งให้ผู้ใช้ทั้งหมดที่ลงทะเบียนในระบบผ่าน LINE</p>
            <button className="button primary" disabled={send.isPending}>ดูตัวอย่าง</button>
            {send.isSuccess ? <InlineAlert tone="success" title="ส่งประกาศเรียบร้อยแล้ว">ระบบกำลังส่งข้อความถึงผู้ใช้ทั้งหมดในระบบ</InlineAlert> : null}
            {send.isError ? <InlineAlert title="ไม่สามารถส่งประกาศได้" error={send.error}>ข้อความที่กรอกยังอยู่ กรุณาลองอีกครั้ง</InlineAlert> : null}
          </form>
        </Surface>
        <Surface title="ประกาศล่าสุด" description="ประวัติการส่งล่าสุดสูงสุด 20 รายการ">
          {history.isError ? <InlineAlert title="ไม่สามารถโหลดประวัติประกาศได้" error={history.error}>กรุณาลองอีกครั้ง</InlineAlert> : null}
          <BroadcastList items={history.data?.items || []} loading={history.isLoading} />
        </Surface>
      </div>
      <Dialog
        open={previewOpen}
        title="ยืนยันการส่งถึงผู้ใช้ทั้งหมด"
        description="ประกาศนี้ไม่ได้จำกัดเฉพาะห้องที่เลือก"
        onClose={() => !send.isPending && setPreviewOpen(false)}
      >
        <div className="announcement-preview">
          <strong>ผู้รับ: ผู้ใช้ทั้งหมดที่ลงทะเบียนในระบบ</strong>
          <p>{message.trim()}</p>
        </div>
        <div className="dialog-actions">
          <button className="button secondary" type="button" onClick={() => setPreviewOpen(false)} disabled={send.isPending}>กลับไปแก้ไข</button>
          <button className="button primary" type="button" onClick={() => send.mutate(message.trim())} disabled={send.isPending}>
            {send.isPending ? "กำลังส่งถึงผู้ใช้ทั้งหมด..." : "ยืนยันการส่งถึงผู้ใช้ทั้งหมด"}
          </button>
        </div>
      </Dialog>
    </>
  );
}
