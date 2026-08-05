"use client";
import { createContext, useContext, useId, type ReactNode } from "react";

import { cn } from "@/lib/utils";

type TabsContextValue = {
  value: string;
  setValue: (v: string) => void;
  baseId: string;
};

const TabsContext = createContext<TabsContextValue | null>(null);

export function Tabs({
  value,
  onValueChange,
  children,
  className,
}: {
  value: string;
  onValueChange: (v: string) => void;
  children: ReactNode;
  className?: string;
}) {
  const baseId = useId();
  return (
    <TabsContext.Provider value={{ value, setValue: onValueChange, baseId }}>
      <div className={className}>{children}</div>
    </TabsContext.Provider>
  );
}

export function TabList({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div role="tablist" className={cn("flex flex-wrap gap-1 border-b border-gray-200 pb-px", className)}>
      {children}
    </div>
  );
}

export function TabTrigger({
  value,
  children,
  className,
}: {
  value: string;
  children: ReactNode;
  className?: string;
}) {
  const ctx = useContext(TabsContext);
  if (!ctx) throw new Error("TabTrigger must be inside Tabs");
  const selected = ctx.value === value;
  const id = `${ctx.baseId}-tab-${value}`;
  const panelId = `${ctx.baseId}-panel-${value}`;
  return (
    <button
      type="button"
      role="tab"
      id={id}
      aria-selected={selected}
      aria-controls={panelId}
      tabIndex={selected ? 0 : -1}
      className={cn(
        "focus-ring -mb-px rounded-t-lg px-3 py-2 text-sm font-semibold motion-safe:transition-colors",
        selected ? "border-b-2 border-brand-600 text-brand-800 bg-white" : "text-gray-600 hover:text-gray-900",
        className
      )}
      onClick={() => ctx.setValue(value)}
    >
      {children}
    </button>
  );
}

export function TabPanel({
  value,
  children,
  className,
}: {
  value: string;
  children: ReactNode;
  className?: string;
}) {
  const ctx = useContext(TabsContext);
  if (!ctx) throw new Error("TabPanel must be inside Tabs");
  if (ctx.value !== value) return null;
  const id = `${ctx.baseId}-panel-${value}`;
  const tabId = `${ctx.baseId}-tab-${value}`;
  return (
    <div role="tabpanel" id={id} aria-labelledby={tabId} className={cn("pt-4", className)}>
      {children}
    </div>
  );
}
