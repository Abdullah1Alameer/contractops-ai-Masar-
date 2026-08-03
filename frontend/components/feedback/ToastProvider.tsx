"use client";
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

type ToastTone = "success" | "error" | "warning" | "info";

type ToastItem = {
  id: string;
  tone: ToastTone;
  message: string;
  duration: number;
};

type ToastContextValue = {
  toast: (message: string, tone?: ToastTone, duration?: number) => void;
  success: (message: string) => void;
  error: (message: string) => void;
  warning: (message: string) => void;
  info: (message: string) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

const toneStyles: Record<ToastTone, string> = {
  success: "border-success-500 bg-success-50 text-success-800",
  error: "border-danger-500 bg-danger-50 text-danger-800",
  warning: "border-warning-500 bg-warning-50 text-warning-800",
  info: "border-info-500 bg-info-50 text-info-800",
};

function ToastStack({ items, onDismiss }: { items: ToastItem[]; onDismiss: (id: string) => void }) {
  return (
    <div
      className="pointer-events-none fixed inset-x-0 top-20 z-[100] flex flex-col items-center gap-2 px-4 sm:items-end sm:px-6"
      aria-live="polite"
    >
      {items.map((item) => (
        <Toast key={item.id} item={item} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

function Toast({ item, onDismiss }: { item: ToastItem; onDismiss: (id: string) => void }) {
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const paused = useRef(false);

  const schedule = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => onDismiss(item.id), item.duration);
  }, [item.duration, item.id, onDismiss]);

  useEffect(() => {
    schedule();
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [schedule]);

  return (
    <div
      role="status"
      className={`pointer-events-auto w-full max-w-sm rounded-lg border px-4 py-3 text-sm font-medium shadow-card motion-safe:animate-slideUp ${toneStyles[item.tone]}`}
      onMouseEnter={() => {
        paused.current = true;
        if (timer.current) clearTimeout(timer.current);
      }}
      onMouseLeave={() => {
        paused.current = false;
        schedule();
      }}
    >
      <div className="flex items-start justify-between gap-2">
        <span>{item.message}</span>
        <button
          type="button"
          className="shrink-0 rounded p-0.5 opacity-70 hover:opacity-100 focus-visible:focus-ring"
          onClick={() => onDismiss(item.id)}
          aria-label="Dismiss"
        >
          ×
        </button>
      </div>
    </div>
  );
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  const dismiss = useCallback((id: string) => {
    setItems((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const add = useCallback((message: string, tone: ToastTone = "info", duration = 4500) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    setItems((prev) => [...prev.slice(-4), { id, tone, message, duration }]);
  }, []);

  const value: ToastContextValue = {
    toast: add,
    success: (m) => add(m, "success"),
    error: (m) => add(m, "error"),
    warning: (m) => add(m, "warning"),
    info: (m) => add(m, "info"),
  };

  return (
    <ToastContext.Provider value={value}>
      {children}
      {mounted && createPortal(<ToastStack items={items} onDismiss={dismiss} />, document.body)}
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
