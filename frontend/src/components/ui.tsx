import { forwardRef } from "react";
import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  LabelHTMLAttributes,
  PropsWithChildren,
  SelectHTMLAttributes,
} from "react";

function cn(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", className, ...rest },
  ref,
) {
  const base =
    "inline-flex items-center justify-center font-medium rounded-md transition-colors " +
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 " +
    "disabled:opacity-50 disabled:pointer-events-none";
  const sizeCls = size === "sm" ? "h-8 px-3 text-sm" : "h-10 px-4 text-sm";
  const variantCls = {
    primary: "bg-indigo-600 text-white hover:bg-indigo-500",
    secondary: "bg-slate-800 text-slate-100 hover:bg-slate-700 border border-slate-700",
    ghost: "text-slate-300 hover:text-white hover:bg-slate-800",
    danger: "bg-red-600 text-white hover:bg-red-500",
  }[variant];
  return <button ref={ref} className={cn(base, sizeCls, variantCls, className)} {...rest} />;
});

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...rest }, ref) {
    return (
      <input
        ref={ref}
        className={cn(
          "h-10 w-full rounded-md border border-slate-700 bg-slate-900 px-3 text-sm",
          "text-slate-100 placeholder:text-slate-500",
          "focus-visible:outline-none focus-visible:border-indigo-500 focus-visible:ring-1 focus-visible:ring-indigo-500",
          className,
        )}
        {...rest}
      />
    );
  },
);

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className, children, ...rest }, ref) {
    return (
      <select
        ref={ref}
        className={cn(
          "h-10 w-full rounded-md border border-slate-700 bg-slate-900 px-3 text-sm text-slate-100",
          "focus-visible:outline-none focus-visible:border-indigo-500 focus-visible:ring-1 focus-visible:ring-indigo-500",
          className,
        )}
        {...rest}
      >
        {children}
      </select>
    );
  },
);

export function Label({ className, ...rest }: LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label className={cn("text-xs font-medium text-slate-400 uppercase tracking-wide", className)} {...rest} />
  );
}

export function Card({ className, children }: PropsWithChildren<{ className?: string }>) {
  return (
    <div
      className={cn(
        "rounded-lg border border-slate-800 bg-slate-900/70 p-6 shadow-sm",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}) {
  return (
    <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-100">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-400">{subtitle}</p>}
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </header>
  );
}

export function StateChip({ state }: { state: string }) {
  const tone =
    {
      adopted: "bg-emerald-600/30 text-emerald-300 border-emerald-700",
      heartbeat: "bg-emerald-600/30 text-emerald-300 border-emerald-700",
      pending: "bg-amber-600/30 text-amber-300 border-amber-700",
      key_exchange: "bg-amber-600/30 text-amber-300 border-amber-700",
      config_apply: "bg-indigo-600/30 text-indigo-300 border-indigo-700",
      disconnected: "bg-slate-600/30 text-slate-300 border-slate-700",
      error: "bg-red-600/30 text-red-300 border-red-700",
      ok: "bg-emerald-600/30 text-emerald-300 border-emerald-700",
      unknown: "bg-slate-600/30 text-slate-300 border-slate-700",
    }[state] ?? "bg-slate-600/30 text-slate-300 border-slate-700";
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-mono",
        tone,
      )}
    >
      {state}
    </span>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-slate-800", className)} />;
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-800 bg-slate-900/40 p-10 text-center">
      <p className="text-slate-300">{title}</p>
      {hint && <p className="mt-2 text-sm text-slate-500">{hint}</p>}
    </div>
  );
}
