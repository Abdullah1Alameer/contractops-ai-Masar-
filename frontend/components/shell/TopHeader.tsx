"use client";
import { Bell, ShieldCheck } from "lucide-react";

import Breadcrumbs from "@/components/shell/Breadcrumbs";
import NotificationsDrawer from "@/components/shell/NotificationsDrawer";
import { GlobalSearchButton, SidebarToggle } from "@/components/shell/Sidebar";
import { useShell } from "@/components/shell/ShellContext";
import UserMenu from "@/components/shell/UserMenu";
import { useI18n } from "@/lib/i18n";

type TopHeaderProps = {
  onMenuClick: () => void;
};

/** Live regulatory-alignment indicator. The halo is a sibling span rather than
 *  a ring on the dot itself, so the pulse can scale past its own bounds. */
function ComplianceBadge() {
  return (
    <span className="hidden items-center gap-2 rounded-full border border-brand-500/20 bg-brand-50/70 px-3 py-1.5 text-[11px] font-bold text-brand-700 backdrop-blur-md lg:inline-flex">
      <span className="relative flex h-1.5 w-1.5">
        <span className="absolute inline-flex h-full w-full rounded-full bg-jade-400 motion-safe:animate-livePulse" aria-hidden />
        <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-brand-600" aria-hidden />
      </span>
      <ShieldCheck className="h-3.5 w-3.5" aria-hidden />
      نظام متوافق مع البيئة التشريعية
    </span>
  );
}

export default function TopHeader({ onMenuClick }: TopHeaderProps) {
  const { t } = useI18n();
  const { primaryAction, setNotificationsOpen } = useShell();

  return (
    <>
      <header className="sticky top-0 z-40 border-b border-brand-500/10 bg-porcelain/70 backdrop-blur-xl backdrop-saturate-150">
        <div className="flex flex-wrap items-center gap-3 px-4 py-3">
          <SidebarToggle onClick={onMenuClick} />
          <Breadcrumbs />
          <ComplianceBadge />
          <div className="ms-auto flex flex-wrap items-center gap-2 sm:gap-3">
            <GlobalSearchButton />
            <button
              type="button"
              className="focus-ring relative rounded-xl p-2 text-neutral-500 motion-safe:transition-colors hover:bg-white hover:text-brand-700"
              title={t("shell.notifications")}
              aria-label={t("shell.notifications")}
              onClick={() => setNotificationsOpen(true)}
            >
              <Bell className="h-5 w-5" strokeWidth={1.9} aria-hidden />
              <span className="absolute end-1.5 top-1.5 h-2 w-2 rounded-full bg-jade-500 shadow-[0_0_8px_rgb(0_212_138/0.9)]" aria-hidden />
            </button>
            <div className="hidden md:block">{primaryAction}</div>
            <UserMenu />
          </div>
        </div>
        {primaryAction && <div className="border-t border-neutral-200/60 px-4 py-2 md:hidden">{primaryAction}</div>}
      </header>
      <NotificationsDrawer />
    </>
  );
}
