"use client";

import { X } from "lucide-react";
import {
  ReactNode,
  RefObject,
  useEffect,
  useId,
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
  context,
  action,
}: {
  title: string;
  description: string;
  workspace?: Workspace | null;
  context?: string;
  action?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <div className="page-context">
          {context ? (
            <span>{context}</span>
          ) : workspace ? (
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

export function ServiceStatusBadge({
  loading,
  error,
  available,
}: {
  loading: boolean;
  error: boolean;
  available?: boolean;
}) {
  if (loading) return <StatusBadge tone="neutral">กำลังตรวจสอบ</StatusBadge>;
  if (error) return <StatusBadge tone="information">ไม่สามารถตรวจสอบได้</StatusBadge>;
  return available
    ? <StatusBadge tone="success">พร้อมใช้งาน</StatusBadge>
    : <StatusBadge tone="warning">มีปัญหาชั่วคราว</StatusBadge>;
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
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  useModalBehavior({
    open,
    onClose,
    containerRef: dialogRef,
    initialFocusRef: closeRef,
  });
  if (!open) return null;
  return (
    <div className="overlay" role="presentation" onMouseDown={onClose}>
      <section
        ref={dialogRef}
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <h2 id={titleId}>{title}</h2>
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
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);
  const drawerRef = useRef<HTMLElement>(null);
  useModalBehavior({
    open,
    onClose,
    containerRef: drawerRef,
    initialFocusRef: closeRef,
    returnFocusRef,
  });
  if (!open) return null;
  return (
    <div className="overlay drawer-overlay" role="presentation" onMouseDown={onClose}>
      <aside ref={drawerRef} className="drawer" role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1} onMouseDown={(event) => event.stopPropagation()}>
        <header>
          <h2 id={titleId}>{title}</h2>
          <button ref={closeRef} type="button" className="icon-button" onClick={onClose} aria-label="ปิดเมนู">
            <X size={20} />
          </button>
        </header>
        {children}
      </aside>
    </div>
  );
}

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

function useModalBehavior({
  open,
  onClose,
  containerRef,
  initialFocusRef,
  returnFocusRef,
}: {
  open: boolean;
  onClose: () => void;
  containerRef: RefObject<HTMLElement | null>;
  initialFocusRef: RefObject<HTMLElement | null>;
  returnFocusRef?: RefObject<HTMLElement | null>;
}) {
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!open) return;
    const body = document.body;
    const previousOverflow = body.style.overflow;
    const returnTarget = returnFocusRef?.current
      ?? (document.activeElement instanceof HTMLElement ? document.activeElement : null);
    body.style.overflow = "hidden";
    initialFocusRef.current?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab") return;

      const container = containerRef.current;
      if (!container) return;
      const focusable = Array.from(
        container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
      ).filter((element) => element.getAttribute("aria-hidden") !== "true");
      if (focusable.length === 0) {
        event.preventDefault();
        container.focus();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && (active === first || !container.contains(active))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (active === last || !container.contains(active))) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      body.style.overflow = previousOverflow;
      returnTarget?.focus();
    };
  }, [containerRef, initialFocusRef, open, returnFocusRef]);
}
