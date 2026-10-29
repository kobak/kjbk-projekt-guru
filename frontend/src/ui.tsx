import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { X, Check } from "lucide-react";
import type { Member, Status } from "./types";
export const statuses: { key: Status; label: string; color: string }[] = [
  { key: "todo", label: "Teendő", color: "#9a97a3" },
  { key: "doing", label: "Folyamatban", color: "#f5a623" },
  { key: "review", label: "Ellenőrzés", color: "#462773" },
  { key: "done", label: "Kész", color: "#1fa463" },
];
export const priorities = {
  low: "Alacsony",
  normal: "Normál",
  high: "Magas",
  urgent: "Sürgős",
};
export function Avatar({
  user,
  size = "normal",
}: {
  user?: Member;
  size?: string;
}) {
  return (
    <span
      title={user?.name || "Nincs felelős"}
      className={"avatar " + size + " avatar-" + ((user?.id || 0) % 5)}
    >
      {user?.name
        .split(/\s+/)
        .slice(0, 2)
        .map((s) => s[0])
        .join("") || "–"}
    </span>
  );
}
export function StatusMark({
  value,
  onClick,
}: {
  value: Status;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      className={"status-mark " + value}
      aria-label={value === "done" ? "Újranyitás" : "Készre jelölés"}
      onClick={(e) => {
        e.stopPropagation();
        onClick?.();
      }}
    >
      {value === "done" ? (
        <Check size={12} />
      ) : value === "doing" ? (
        <span />
      ) : null}
    </button>
  );
}
export function Modal({
  title,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null),
    closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const before = document.activeElement as HTMLElement;
    const listener = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        closeRef.current();
      }
      if (e.key === "Tab") {
        const els = ref.current?.querySelectorAll<HTMLElement>(
          "button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href]",
        );
        if (!els?.length) return;
        const first = els[0],
          last = els[els.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", listener);
    if (!ref.current?.contains(document.activeElement)) ref.current?.focus();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", listener);
      document.body.style.overflow = overflow;
      before?.focus();
    };
  }, []);
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className={"modal " + (wide ? "wide" : "")}
        ref={ref}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="modal-heading">
          <h2>{title}</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Bezárás">
            <X size={20} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
