"use client";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";

import CommandPalette from "@/components/shell/CommandPalette";
import { ShellProvider } from "@/components/shell/ShellContext";
import Sidebar from "@/components/shell/Sidebar";
import TopHeader from "@/components/shell/TopHeader";

export function PageContainer({ children }: { children: ReactNode }) {
  return <div className="mx-auto w-full max-w-7xl px-4 py-6">{children}</div>;
}

function AppShellInner({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const isPublic = pathname.startsWith("/review/") || pathname.startsWith("/sign/");

  if (isPublic) {
    return <>{children}</>;
  }

  return (
    <div className="flex min-h-screen bg-muted-50/40">
      <Sidebar mobileOpen={mobileOpen} onMobileClose={() => setMobileOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader onMenuClick={() => setMobileOpen(true)} />
        <PageContainer>{children}</PageContainer>
      </div>
      <CommandPalette />
    </div>
  );
}

export default function AppShell({ children }: { children: ReactNode }) {
  return (
    <ShellProvider>
      <AppShellInner>{children}</AppShellInner>
    </ShellProvider>
  );
}
