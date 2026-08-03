"use client";
import { createContext, forwardRef, useCallback, useContext, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import Button from "@/components/ui/Button";
import { useI18n } from "@/lib/i18n";

type ConfirmOptions = {
  title: string;
  body?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  onConfirm: () => void | Promise<void>;
};

type ConfirmContextValue = {
  confirm: (opts: ConfirmOptions) => Promise<boolean>;
};

const ConfirmContext = createContext<ConfirmContextValue | null>(null);

type Pending = ConfirmOptions & { resolve: (v: boolean) => void };

export function ConfirmDialogProvider({ children }: { children: React.ReactNode }) {
  const [pending, setPending] = useState<Pending | null>(null);
  const [loading, setLoading] = useState(false);
  const [mounted, setMounted] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => setMounted(true), []);

  const confirm = useCallback((opts: ConfirmOptions) => {
    return new Promise<boolean>((resolve) => {
      setPending({ ...opts, resolve });
    });
  }, []);

  const close = useCallback(
    (result: boolean) => {
      if (loading) return;
      pending?.resolve(result);
      setPending(null);
    },
    [loading, pending]
  );

  useEffect(() => {
    if (!pending) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [pending, close]);

  useEffect(() => {
    if (!pending || !dialogRef.current) return;
    const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    first?.focus();

    const trap = (e: KeyboardEvent) => {
      if (e.key !== "Tab" || focusable.length === 0) return;
      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        }
      } else if (document.activeElement === last) {
        e.preventDefault();
        first?.focus();
      }
    };
    window.addEventListener("keydown", trap);
    return () => window.removeEventListener("keydown", trap);
  }, [pending]);

  const runConfirm = async () => {
    if (!pending) return;
    setLoading(true);
    try {
      await pending.onConfirm();
      pending.resolve(true);
      setPending(null);
    } catch {
      pending.resolve(false);
      setPending(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <ConfirmContext.Provider value={{ confirm }}>
      {children}
      {mounted &&
        pending &&
        createPortal(
          <div
            className="fixed inset-0 z-[110] flex items-center justify-center bg-black/40 p-4 motion-safe:animate-fadeIn"
            onClick={(e) => {
              if (e.target === e.currentTarget) close(false);
            }}
            role="presentation"
          >
            <ConfirmPanel
              ref={dialogRef}
              pending={pending}
              loading={loading}
              onCancel={() => close(false)}
              onConfirm={runConfirm}
            />
          </div>,
          document.body
        )}
    </ConfirmContext.Provider>
  );
}

const ConfirmPanel = forwardRef<
  HTMLDivElement,
  {
    pending: Pending;
    loading: boolean;
    onCancel: () => void;
    onConfirm: () => void;
  }
>(function ConfirmPanel({ pending, loading, onCancel, onConfirm }, ref) {
  const { t } = useI18n();
  return (
    <div
      ref={ref}
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-title"
      className="w-full max-w-md rounded-xl border border-gray-200 bg-white p-6 shadow-card motion-safe:animate-slideUp"
      onClick={(e) => e.stopPropagation()}
    >
      <h2 id="confirm-title" className="text-lg font-bold text-gray-900">
        {pending.title}
      </h2>
      {pending.body && <p className="mt-2 text-sm text-gray-600">{pending.body}</p>}
      <div className="mt-6 flex flex-wrap justify-end gap-2">
        <Button variant="secondary" size="md" onClick={onCancel} disabled={loading}>
          {pending.cancelLabel ?? t("common.cancel")}
        </Button>
        <Button
          variant={pending.danger ? "danger" : "primary"}
          size="md"
          loading={loading}
          onClick={onConfirm}
        >
          {pending.confirmLabel ?? t("common.confirm")}
        </Button>
      </div>
    </div>
  );
});

export function useConfirm() {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error("useConfirm must be used within ConfirmDialogProvider");
  return ctx;
}
