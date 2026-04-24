import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { PropsWithChildren } from "react";
import { createPortal } from "react-dom";

import { Button } from "./ui";

export type ConfirmOpts = {
  title: string;
  message?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "primary";
};

type Pending = { opts: ConfirmOpts; resolve: (ok: boolean) => void };
type ConfirmCtx = { openConfirm: (opts: ConfirmOpts) => Promise<boolean> };

const Ctx = createContext<ConfirmCtx | null>(null);

export function ConfirmProvider({ children }: PropsWithChildren) {
  const [pending, setPending] = useState<Pending | null>(null);
  const pendingRef = useRef(pending);
  pendingRef.current = pending;

  const openConfirm = useCallback((opts: ConfirmOpts): Promise<boolean> => {
    return new Promise((resolve) => {
      setPending({ opts, resolve });
    });
  }, []);

  const respond = useCallback((ok: boolean) => {
    pendingRef.current?.resolve(ok);
    setPending(null);
  }, []);

  useEffect(() => {
    if (!pending) return;
    const h = (e: KeyboardEvent) => {
      if (e.key === "Escape") respond(false);
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [pending, respond]);

  return (
    <Ctx.Provider value={{ openConfirm }}>
      {children}
      {pending &&
        createPortal(
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
            onClick={(e) => {
              if (e.target === e.currentTarget) respond(false);
            }}
          >
            <div
              className="w-full max-w-sm rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-2xl"
              role="alertdialog"
              aria-modal="true"
              aria-labelledby="confirm-dlg-title"
            >
              <h2
                id="confirm-dlg-title"
                className="text-base font-semibold text-slate-100"
              >
                {pending.opts.title}
              </h2>
              {pending.opts.message && (
                <p className="mt-2 text-sm text-slate-400">{pending.opts.message}</p>
              )}
              <div className="mt-6 flex justify-end gap-2">
                <Button variant="ghost" size="sm" onClick={() => respond(false)}>
                  {pending.opts.cancelLabel ?? "Cancel"}
                </Button>
                {/* autoFocus means Enter confirms naturally */}
                <Button
                  variant={pending.opts.variant === "danger" ? "danger" : "primary"}
                  size="sm"
                  autoFocus
                  onClick={() => respond(true)}
                >
                  {pending.opts.confirmLabel ?? "Confirm"}
                </Button>
              </div>
            </div>
          </div>,
          document.body,
        )}
    </Ctx.Provider>
  );
}

export function useConfirm(): ConfirmCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useConfirm must be used inside ConfirmProvider");
  return ctx;
}
