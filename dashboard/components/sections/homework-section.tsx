"use client";

import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/dashboard-api";
import type { Homework } from "@/lib/dashboard-types";
import { HomeworkList } from "./section-content";
import { InlineAlert, PageHeader, Surface } from "@/components/ui/dashboard-ui";

export function HomeworkSection() {
  const query = useQuery({
    queryKey: ["homeworks"],
    queryFn: () => apiGet<{ items: Homework[] }>("homeworks?limit=30"),
  });
  return (
    <>
      <PageHeader title="การบ้าน" description="รายการการบ้านล่าสุดที่บันทึกในระบบ" context="ข้อมูลรวมทั้งระบบ" action={<button className="button secondary" onClick={() => query.refetch()}>อัปเดตข้อมูล</button>} />
      {query.isError ? <InlineAlert title="ไม่สามารถโหลดการบ้านได้" error={query.error}>กรุณาลองอัปเดตข้อมูลอีกครั้ง</InlineAlert> : null}
      <Surface title="การบ้านล่าสุด" description="แสดงรายการล่าสุดสูงสุด 30 รายการ">
        <HomeworkList items={query.data?.items || []} loading={query.isLoading} />
      </Surface>
    </>
  );
}
