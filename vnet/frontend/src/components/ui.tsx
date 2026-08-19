/** Small presentational primitives shared by every page. */

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
} from "react";

import { CloseIcon } from "@/components/icons";
import type { Severity } from "@/types";

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

/* --------------------------------------------------------------- surfaces */

export function Panel({
  title,
  subtitle,
  action,
  children,
  className,
  bodyClassName,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section className={cx("panel flex flex-col min-h-0", className)}>
      {(title || action) && (
        <header className="flex items-center justify-between gap-3 px-4 py-3 border-b border-ink-800">
          <div className="min-w-0">
            {title && <h2 className="text-sm font-semibold text-ink-200 truncate">{title}</h2>}
            {subtitle && <p className="text-xs text-ink-400 mt-0.5 truncate">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      <div className={cx("min-h-0", bodyClassName ?? "p-4")}>{children}</div>
    </section>
  );
}

export function StatTile({
  label,
  value,
  unit,
  hint,
  tone = "default",
}: {
  label: string;
  value: ReactNode;
  unit?: string;
  hint?: ReactNode;
  tone?: "default" | "ok" | "warn" | "bad";
}) {
  const toneClass = {
    default: "text-ink-200",
    ok: "text-ok",
    warn: "text-warn",
    bad: "text-bad",
  }[tone];
  return (
    <div className="panel px-4 py-3">
      <div className="text-[11px] uppercase tracking-wider text-ink-400 font-semibold">
        {label}
      </div>
      <div className="mt-1.5 flex items-baseline gap-1.5">
        <span className={cx("text-2xl font-semibold tabular-nums", toneClass)}>{value}</span>
        {unit && <span className="text-xs text-ink-400">{unit}</span>}
      </div>
      {hint && <div className="mt-1 text-xs text-ink-400">{hint}</div>}
    </div>
  );
}

export function EmptyState({
  title,
  detail,
  action,
}: {
  title: string;
  detail?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-12 text-center">
      <p className="text-sm font-medium text-ink-300">{title}</p>
      {detail && <p className="text-xs text-ink-500 max-w-sm">{detail}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

/* ---------------------------------------------------------------- badges */

const SEVERITY_STYLE: Record<Severity, string> = {
  critical: "bg-bad/15 text-bad border-bad/30",
  warning: "bg-warn/15 text-warn border-warn/30",
  info: "bg-unifi-bright/15 text-unifi-bright border-unifi-bright/30",
};

export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: ReactNode;
  tone?: "neutral" | "ok" | "warn" | "bad" | "info" | Severity;
  className?: string;
}) {
  const styles: Record<string, string> = {
    neutral: "bg-ink-800 text-ink-300 border-ink-700",
    ok: "bg-ok/15 text-ok border-ok/30",
    warn: SEVERITY_STYLE.warning,
    bad: SEVERITY_STYLE.critical,
    info: SEVERITY_STYLE.info,
    critical: SEVERITY_STYLE.critical,
    warning: SEVERITY_STYLE.warning,
  };
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11px] font-medium",
        styles[tone] ?? styles.neutral,
        className,
      )}
    >
      {children}
    </span>
  );
}

export function StatusDot({ status }: { status: string }) {
  const tone =
    status === "online" || status === "ok" || status === "forwarding"
      ? "bg-ok"
      : status === "offline" || status === "down"
        ? "bg-ink-500"
        : status === "blocked" || status === "warning"
          ? "bg-warn"
          : "bg-bad";
  return <span className={cx("inline-block h-2 w-2 rounded-full shrink-0", tone)} />;
}

export function Meter({
  value,
  tone = "ok",
  className,
}: {
  value: number;
  tone?: "ok" | "warn" | "bad";
  className?: string;
}) {
  const fill = { ok: "bg-ok", warn: "bg-warn", bad: "bg-bad" }[tone];
  return (
    <div className={cx("h-1.5 w-full rounded-full bg-ink-800 overflow-hidden", className)}>
      <div
        className={cx("h-full rounded-full transition-all duration-500", fill)}
        style={{ width: `${Math.min(100, Math.max(0, value * 100))}%` }}
      />
    </div>
  );
}

/* --------------------------------------------------------------- controls */

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
};

export function Button({
  variant = "secondary",
  size = "md",
  className,
  ...rest
}: ButtonProps) {
  const variants = {
    primary: "bg-unifi hover:bg-unifi-bright text-white border-transparent",
    secondary: "bg-ink-800 hover:bg-ink-700 text-ink-200 border-ink-700",
    ghost: "bg-transparent hover:bg-ink-800 text-ink-300 border-transparent",
    danger: "bg-bad/15 hover:bg-bad/25 text-bad border-bad/30",
  };
  const sizes = { sm: "px-2 py-1 text-xs", md: "px-3 py-1.5 text-sm" };
  return (
    <button
      className={cx(
        "inline-flex items-center justify-center gap-1.5 rounded-md border font-medium transition",
        "disabled:opacity-40 disabled:pointer-events-none",
        variants[variant],
        sizes[size],
        className,
      )}
      {...rest}
    />
  );
}

export function Field({
  label,
  hint,
  children,
  className,
}: {
  label: string;
  hint?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={cx("block", className)}>
      <span className="block text-xs font-medium text-ink-300 mb-1">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-[11px] text-ink-500">{hint}</span>}
    </label>
  );
}

export const Input = (props: InputHTMLAttributes<HTMLInputElement>) => (
  <input {...props} className={cx("field", props.className)} />
);

export const Select = (props: SelectHTMLAttributes<HTMLSelectElement>) => (
  <select {...props} className={cx("field", props.className)} />
);

export function Toggle({
  checked,
  onChange,
  label,
  hint,
  disabled,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  label: string;
  hint?: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className="flex w-full items-start justify-between gap-3 py-1.5 text-left disabled:opacity-40"
    >
      <span>
        <span className="block text-sm text-ink-200">{label}</span>
        {hint && <span className="block text-[11px] text-ink-500">{hint}</span>}
      </span>
      <span
        className={cx(
          "mt-0.5 h-5 w-9 shrink-0 rounded-full p-0.5 transition",
          checked ? "bg-unifi" : "bg-ink-700",
        )}
      >
        <span
          className={cx(
            "block h-4 w-4 rounded-full bg-white transition-transform",
            checked && "translate-x-4",
          )}
        />
      </span>
    </button>
  );
}

/* ----------------------------------------------------------------- modal */

export function Modal({
  open,
  title,
  onClose,
  children,
  footer,
  width = "max-w-lg",
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  width?: string;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className={cx("relative w-full panel bg-ink-900", width)}>
        <header className="flex items-center justify-between border-b border-ink-800 px-4 py-3">
          <h2 className="text-sm font-semibold text-ink-100">{title}</h2>
          <button onClick={onClose} className="text-ink-400 hover:text-ink-200">
            <CloseIcon size={16} />
          </button>
        </header>
        <div className="max-h-[70vh] overflow-y-auto p-4">{children}</div>
        {footer && (
          <footer className="flex justify-end gap-2 border-t border-ink-800 px-4 py-3">
            {footer}
          </footer>
        )}
      </div>
    </div>
  );
}

/* ----------------------------------------------------------------- toasts */

interface Toast {
  id: number;
  message: string;
  tone: "ok" | "bad";
}

const ToastContext = createContext<(message: string, tone?: "ok" | "bad") => void>(() => {});

export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const push = (message: string, tone: "ok" | "bad" = "ok") => {
    const id = Date.now() + Math.random();
    setToasts((current) => [...current, { id, message, tone }]);
    setTimeout(() => setToasts((current) => current.filter((t) => t.id !== id)), 4500);
  };

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="fixed bottom-4 right-4 z-[60] flex flex-col gap-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={cx(
              "panel max-w-sm px-3 py-2 text-sm shadow-panel",
              toast.tone === "bad" ? "border-bad/40 text-bad" : "border-ok/40 text-ok",
            )}
          >
            {toast.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

/* ----------------------------------------------------------------- table */

export function Table({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cx("overflow-x-auto", className)}>
      <table className="w-full border-collapse">{children}</table>
    </div>
  );
}

export function Tr({
  children,
  onClick,
  active,
}: {
  children: ReactNode;
  onClick?: () => void;
  active?: boolean;
}) {
  return (
    <tr
      onClick={onClick}
      className={cx(
        "border-t border-ink-800/70",
        onClick && "cursor-pointer hover:bg-ink-850",
        active && "bg-unifi/10",
      )}
    >
      {children}
    </tr>
  );
}
