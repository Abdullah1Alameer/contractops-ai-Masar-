"use client";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";

import CommandPalette from "@/components/shell/CommandPalette";
import { ShellProvider } from "@/components/shell/ShellContext";
import Sidebar from "@/components/shell/Sidebar";
import { PageTransition, ScrollProgress } from "@/components/shell/PageTransition";
import TopHeader from "@/components/shell/TopHeader";

export function PageContainer({ children }: { children: ReactNode }) {
  return (
    <div className="relative mx-auto w-full max-w-7xl px-4 py-6">
      <PageTransition>{children}</PageTransition>
    </div>
  );
}

/**
 * Ambient light field.
 *
 * Large, heavily-blurred colour volumes sit behind the whole app so the
 * porcelain canvas is never a flat expanse of white — the glass surfaces above
 * have something to refract. Fixed rather than absolute so the light stays put
 * while content scrolls past it, and pointer-events-none so it never
 * intercepts interaction.
 */
function AmbientCanvas() {
  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden" aria-hidden>
      <div className="absolute -top-40 end-[-6rem] h-96 w-96 rounded-full bg-emerald-100/50 blur-[100px]" />
      <div className="absolute top-1/3 start-[-8rem] h-96 w-96 rounded-full bg-blue-50/60 blur-[120px]" />
      <div className="absolute bottom-[-10rem] end-1/4 h-[28rem] w-[28rem] rounded-full bg-teal-50/60 blur-[120px]" />
      <div className="absolute top-2/3 start-1/3 h-72 w-72 rounded-full bg-amber-50/40 blur-[100px]" />
    </div>
  );
}

function AppShellInner({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const isPublic = pathname.startsWith("/review/") || pathname.startsWith("/sign/");

  if (isPublic) {
    return <>{children}</>;
  }

  return (
    <div className="relative flex min-h-screen bg-[#F8FAFC]">
      <ScrollProgress />
      <AmbientCanvas />
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
