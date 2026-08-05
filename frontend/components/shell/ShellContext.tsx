"use client";
import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

type ShellContextValue = {
  pageTitle: string | null;
  setPageTitle: (t: string | null) => void;
  primaryAction: ReactNode;
  setPrimaryAction: (n: ReactNode) => void;
  paletteOpen: boolean;
  setPaletteOpen: (v: boolean) => void;
  notificationsOpen: boolean;
  setNotificationsOpen: (v: boolean) => void;
};

const ShellContext = createContext<ShellContextValue | null>(null);

export function ShellProvider({ children }: { children: ReactNode }) {
  const [pageTitle, setPageTitle] = useState<string | null>(null);
  const [primaryAction, setPrimaryAction] = useState<ReactNode>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const value = useMemo(
    () => ({
      pageTitle,
      setPageTitle,
      primaryAction,
      setPrimaryAction,
      paletteOpen,
      setPaletteOpen,
      notificationsOpen,
      setNotificationsOpen,
    }),
    [pageTitle, primaryAction, paletteOpen, notificationsOpen]
  );
  return <ShellContext.Provider value={value}>{children}</ShellContext.Provider>;
}

export function useShell() {
  const ctx = useContext(ShellContext);
  if (!ctx) throw new Error("useShell must be used within ShellProvider");
  return ctx;
}
