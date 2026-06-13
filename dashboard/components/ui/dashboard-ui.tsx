"use client";

import { X } from "lucide-react";
import {
  ReactNode,
  RefObject,
  useEffect,
  useRef,
} from "react";
import type { Workspace } from "@/lib/dashboard-types";

export function Surface({
  title,
  description,
  action,
  children,
  className = "",
}: {
  title?: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`surface ${className}`}>
      {title || action ? (
        <header className="surface-header">
          <div>
            {title ? <h2>{title}</h2> : null}
            {description ? <p>{description}</p> : null}
          </div>
          {action}
        </header>
      ) : null}
      {children}
    </section>
  );
}

export function PageHeader({
  title,
  description,
  workspace,
  action,
}: {
  title: string;
  description: string;
  workspace?: Workspace | null;
  action?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <div className="page-context">
          {workspace ? (
            <>
              <span>{workspace.label}</span>
              <span aria-hidden="true">·</span>
              <span>{workspace.active_term_label}</span>
            </>
          ) : (
            <span>พื้นที่ผู้ดูแลระบบ</span>
          )}
        </div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action ? <div className="page-header-action">{action}</div> : null}
    </header>
  );
}

export function StatusBadge({
  tone,
  children,
}: {
  tone: "success" | "warning" | "danger" | "neutral" | "information";
  children: ReactNode;
}) {
  return <span className={`status-badge status-${tone}`}>{children}</span>;
}

export function InlineAlert({
  tone = "danger",
  title,
  children,
  error,
}: {
  tone?: "danger" | "success" | "warning";
  title: string;
  children?: ReactNode;
  error?: Error | null;
}) {
  return (
    <div className={`inline-alert alert-${tone}`} role={tone === "danger" ? "alert" : "status"}>
      <strong>{title}</strong>
      {children ? <div>{children}</div> : null}
      {error ? (
        <details>
          <summary>รายละเอียดทางเทคนิค</summary>
          <code>{error.message}</code>
        </details>
      ) : null}
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <div className="empty-state">{children}</div>;
}

export function LoadingState({ rows = 3 }: { rows?: number }) {
  return (
    <div className="loading-state" aria-label="กำลังโหลด">
      {Array.from({ length: rows }).map((_, index) => (
        <span key={index} />
      ))}
    </div>
  );
}

export function Dialog({
  open,
  title,
  description,
  onClose,
  children,
}: {
  open: boolean;
  title: string;
  description?: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  useEscapeClose(open, onClose);
  useEffect(() => {
    if (open) {
      returnFocusRef.current = document.activeElement as HTMLElement | null;
      closeRef.current?.focus();
    } else {
      returnFocusRef.current?.focus();
      returnFocusRef.current = null;
    }
  }, [open]);
  if (!open) return null;
  return (
    <div className="overlay" role="presentation" onMouseDown={onClose}>
      <section
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <h2 id="dialog-title">{title}</h2>
            {description ? <p>{description}</p> : null}
          </div>
          <button ref={closeRef} type="button" className="icon-button" onClick={onClose} aria-label="ปิดหน้าต่าง">
            <X size={20} />
          </button>
        </header>
        {children}
      </section>
    </div>
  );
}

export function Drawer({
  open,
  title,
  onClose,
  returnFocusRef,
  children,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  returnFocusRef: RefObject<HTMLButtonElement | null>;
  children: ReactNode;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEscapeClose(open, onClose);
  useEffect(() => {
    if (open) closeRef.current?.focus();
    if (!open) returnFocusRef.current?.focus();
  }, [open, returnFocusRef]);
  if (!open) return null;
  return (
    <div className="overlay drawer-overlay" role="presentation" onMouseDown={onClose}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title" onMouseDown={(event) => event.stopPropagation()}>
        <header>
          <h2 id="drawer-title">{title}</h2>
          <button ref={closeRef} type="button" className="icon-button" onClick={onClose} aria-label="ปิดเมนู">
            <X size={20} />
          </button>
        </header>
        {children}
      </aside>
    </div>
  );
}

function useEscapeClose(open: boolean, onClose: () => void) {
  useEffect(() => {
    if (!open) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);
}
