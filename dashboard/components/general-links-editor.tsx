"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { ExternalLink, Pencil } from "lucide-react";
import { apiGet, apiSend, validationError } from "@/lib/dashboard-api";
import { formatDateTime, safeHostname } from "@/lib/dashboard-formatters";
import type { Workspace } from "@/lib/dashboard-types";
import {
  Dialog,
  EmptyState,
  InlineAlert,
  LoadingState,
  PageHeader,
  StatusBadge,
  Surface,
} from "@/components/ui/dashboard-ui";

type LinkKey = "worksheet_url" | "school_url" | "grade_url" | "absence_form_url";
type LinksPayload = Record<LinkKey, string>;
type LinksResponse = {
  links: LinksPayload;
  effective_links: Partial<LinksPayload>;
  updated_at?: string;
};

const LINK_FIELDS: Array<{ key: LinkKey; label: string; commands: string }> = [
  { key: "worksheet_url", label: "ใบงาน", commands: "งาน, ใบงาน" },
  { key: "school_url", label: "เว็บไซต์โรงเรียน", commands: "เว็บโรงเรียน" },
  { key: "grade_url", label: "ผลการเรียน", commands: "เกรด" },
  { key: "absence_form_url", label: "แบบฟอร์มลา", commands: "ลา" },
];

function pathFor(workspace: Workspace) {
  return `classes/${encodeURIComponent(workspace.class_id)}/terms/${encodeURIComponent(workspace.active_term_id)}/config/links`;
}

export function GeneralLinksEditor({ workspace }: { workspace: Workspace | null }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<(typeof LINK_FIELDS)[number] | null>(null);
  const [value, setValue] = useState("");
  const [success, setSuccess] = useState("");
  const query = useQuery({
    queryKey: ["links", workspace?.class_id, workspace?.active_term_id],
    queryFn: () => apiGet<LinksResponse>(pathFor(workspace as Workspace)),
    enabled: Boolean(workspace),
  });
  const save = useMutation({
    mutationFn: () => {
      if (!workspace || !editing || !query.data) throw validationError("ไม่พบพื้นที่จัดการที่เลือก");
      const nextValue = value.trim();
      if (nextValue && !nextValue.startsWith("https://")) {
        throw validationError("URL ต้องเว้นว่างหรือขึ้นต้นด้วย https://");
      }
      return apiSend<LinksResponse>(pathFor(workspace), "PUT", {
        ...query.data.links,
        [editing.key]: nextValue,
      });
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["links", workspace?.class_id, workspace?.active_term_id], data);
      setEditing(null);
      setSuccess("บันทึกลิงก์เรียบร้อยแล้ว");
    },
  });
  function openEditor(field: (typeof LINK_FIELDS)[number]) {
    setSuccess("");
    setEditing(field);
    setValue(query.data?.links[field.key] || "");
    save.reset();
  }

  return (
    <>
      <PageHeader
        title="ลิงก์และสื่อ"
        description="จัดการลิงก์พื้นฐานที่ใช้โดยคำสั่งหลักใน LINE ของห้องที่เลือก"
        workspace={workspace}
        action={<button className="button secondary" onClick={() => query.refetch()} disabled={!workspace || query.isFetching}>อัปเดตข้อมูล</button>}
      />
      {!workspace ? <InlineAlert tone="warning" title="ยังไม่มีพื้นที่จัดการ">ไม่สามารถโหลดลิงก์ได้ กรุณาตรวจสอบการเชื่อมต่อพื้นที่จัดการ</InlineAlert> : null}
      {query.isError ? <InlineAlert title="ไม่สามารถโหลดลิงก์พื้นฐานได้" error={query.error}>กรุณาลองอัปเดตข้อมูลอีกครั้ง</InlineAlert> : null}
      {success ? <InlineAlert tone="success" title={success} /> : null}
      <Surface title="ลิงก์พื้นฐาน" description="รองรับเฉพาะลิงก์ที่ระบบ LINE ใช้งานจริง 4 รายการ">
        {query.isLoading ? <LoadingState rows={4} /> : null}
        {query.data ? (
          <div className="links-list">
            {LINK_FIELDS.map((field) => {
              const configured = query.data.links[field.key];
              const effective = configured || query.data.effective_links[field.key] || "";
              return (
                <article key={field.key}>
                  <div className="link-main">
                    <strong>{field.label}</strong>
                    <span>คำสั่ง: {field.commands}</span>
                  </div>
                  <div className="link-status">
                    <StatusBadge tone={configured ? "success" : "neutral"}>
                      {configured ? "ตั้งค่าแล้ว" : "ยังไม่ได้ตั้งค่า"}
                    </StatusBadge>
                    <span>{safeHostname(effective) || "ไม่มี URL"}</span>
                  </div>
                  <button className="button secondary compact" type="button" onClick={() => openEditor(field)}>
                    <Pencil size={16} />แก้ไข
                  </button>
                </article>
              );
            })}
          </div>
        ) : !query.isLoading && !query.isError ? <EmptyState>ยังไม่ได้ตั้งค่าลิงก์</EmptyState> : null}
        {query.data?.updated_at ? <p className="updated-note">อัปเดตล่าสุด {formatDateTime(query.data.updated_at)}</p> : null}
      </Surface>
      <Dialog
        open={Boolean(editing)}
        title={editing ? `แก้ไขลิงก์${editing.label}` : "แก้ไขลิงก์"}
        description={editing ? `ใช้กับคำสั่ง ${editing.commands}` : undefined}
        onClose={() => !save.isPending && setEditing(null)}
      >
        <form onSubmit={(event: FormEvent) => { event.preventDefault(); save.mutate(); }} className="form-stack">
          <label htmlFor="link-url">URL</label>
          <div className="input-with-icon">
            <ExternalLink size={17} />
            <input id="link-url" value={value} onChange={(event) => setValue(event.target.value)} placeholder="https://..." autoFocus />
          </div>
          <p className="field-help">เว้นว่างได้เมื่อต้องการใช้ค่าพื้นฐานของระบบ</p>
          {save.isError ? <InlineAlert title="ไม่สามารถบันทึกลิงก์ได้" error={save.error}>ข้อมูลที่กรอกยังอยู่ กรุณาลองอีกครั้ง</InlineAlert> : null}
          <div className="dialog-actions">
            <button type="button" className="button secondary" onClick={() => setEditing(null)} disabled={save.isPending}>ยกเลิก</button>
            <button type="submit" className="button primary" disabled={save.isPending}>{save.isPending ? "กำลังบันทึก..." : "บันทึกลิงก์"}</button>
          </div>
        </form>
      </Dialog>
    </>
  );
}
