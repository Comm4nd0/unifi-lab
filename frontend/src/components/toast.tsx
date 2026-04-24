import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { PropsWithChildren } from "react";
import { createPortal } from "react-dom";

type Variant = "success" | "error" | "info";
type ToastItem = { id: number; message: string; variant: Variant };
type ToastCtx = {
  success: (msg: string) => void;
  error: (msg: string) => void;
  info: (msg: string) => void;
};

const Ctx = createContext<ToastCtx | null>(null);
let _nextId = 0;

export function ToastProvider({ children }: PropsWithChildren) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const add = useCallback((message: string, variant: Variant) => {
    const id = ++_nextId;
    setItems((p) => [...p, { id, message, variant }]);
  }, []);

  const remove = useCallback((id: number) => {
    setItems((p) => p.filter((t) => t.id !== id));
  }, []);

  return (
    <Ctx.Provider
      value={{
        success: (m) => add(m, "success"),
        error: (m) => add(m, "error"),
        info: (m) => add(m, "info"),
      }}
    >
      {children}
      {createPortal(
        <div className="fixed bottom-4 right-4 z-[60] flex flex-col gap-2 pointer-events-none">
          {items.map((t) => (
            <ToastBubble key={t.id} item={t} onDismiss={remove} />
          ))}
        </div>,
        document.body,
      )}
    </Ctx.Provider>
  );
}

function ToastBubble({
  item,
  onDismiss,
}: {
  item: ToastItem;
  onDismiss: (id: number) => void;
}) {
  useEffect(() => {
    const h = window.setTimeout(() => onDismiss(item.id), 4000);
    return () => window.clearTimeout(h);
  }, [item.id, onDismiss]);

  const cls = {
    success: "bg-emerald-900 border-emerald-700 text-emerald-100",
    error: "bg-red-900 border-red-700 text-red-100",
    info: "bg-slate-800 border-slate-700 text-slate-100",
  }[item.variant];

  return (
    <div
      className={`pointer-events-auto flex items-start gap-3 rounded-lg border px-4 py-3 shadow-xl min-w-[16rem] max-w-xs text-sm ${cls}`}
      role="status"
      aria-live="polite"
    >
      <span className="flex-1">{item.message}</span>
      <button
        type="button"
        onClick={() => onDismiss(item.id)}
        className="shrink-0 opacity-50 hover:opacity-100 leading-none"
        aria-label="Dismiss"
      >
        ✕
      </button>
    </div>
  );
}

export function useToast(): ToastCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useToast must be used inside ToastProvider");
  return ctx;
}
