"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { apiGet } from "@/lib/dashboard-api";
import type { UserRow, Workspace } from "@/lib/dashboard-types";
import { MaskedLineId } from "./section-content";
import { EmptyState, InlineAlert, LoadingState, PageHeader, Surface } from "@/components/ui/dashboard-ui";

export function AccountsSection({ workspace }: { workspace: Workspace | null }) {
  const [search, setSearch] = useState("");
  const query = useQuery({
    queryKey: ["users"],
    queryFn: () => apiGet<{ items: UserRow[]; page: { total: number } }>("users?limit=100"),
  });
  const rows = useMemo(
    () => (query.data?.items || []).filter((item) => item.user_id.toLowerCase().includes(search.trim().toLowerCase())),
    [query.data, search],
  );
  return (
    <>
      <PageHeader
        title="บัญชี LINE ที่เชื่อมต่อ"
        description="บัญชี LINE ที่เชื่อมต่อกับ MTC Assistant ในระบบปัจจุบัน"
        workspace={workspace}
      />
      <Surface
        title="บัญชีที่พบ"
        action={
          <label className="search-field">
            <Search size={17} />
            <span className="sr-only">ค้นหา LINE User ID</span>
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="ค้นหา LINE User ID" />
          </label>
        }
      >
        {query.isError ? <InlineAlert title="ไม่สามารถโหลดบัญชี LINE ได้" error={query.error}>กรุณาลองอัปเดตข้อมูลอีกครั้ง</InlineAlert> : null}
        {query.isLoading ? <LoadingState rows={5} /> : null}
        {!query.isLoading && rows.length === 0 ? <EmptyState>ยังไม่มีบัญชี LINE ที่เชื่อมต่อ</EmptyState> : null}
        {rows.length ? (
          <div className="accounts-list">
            {rows.map((row) => <MaskedLineId key={row.user_id} value={row.user_id} />)}
          </div>
        ) : null}
      </Surface>
    </>
  );
}
