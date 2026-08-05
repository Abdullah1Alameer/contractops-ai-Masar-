"use client";
import NotificationsDrawer from "@/components/shell/NotificationsDrawer";
import UserMenu from "@/components/shell/UserMenu";
import Breadcrumbs from "@/components/shell/Breadcrumbs";
import { GlobalSearchButton, SidebarToggle } from "@/components/shell/Sidebar";
import { useShell } from "@/components/shell/ShellContext";
import { useI18n } from "@/lib/i18n";

type TopHeaderProps = {
  onMenuClick: () => void;
};

export default function TopHeader({ onMenuClick }: TopHeaderProps) {
  const { t } = useI18n();
  const { primaryAction, setNotificationsOpen } = useShell();

  return (
    <>
      <header className="sticky top-0 z-40 border-b border-neutral-200/80 bg-white/90 backdrop-blur-md">
        <div className="flex flex-wrap items-center gap-3 px-4 py-3">
          <SidebarToggle onClick={onMenuClick} />
          <Breadcrumbs />
          <div className="ms-auto flex flex-wrap items-center gap-2 sm:gap-3">
            <GlobalSearchButton />
            <button
              type="button"
              className="focus-ring relative rounded-lg p-2 text-neutral-500 hover:bg-neutral-50"
              title={t("shell.notifications")}
              aria-label={t("shell.notifications")}
              onClick={() => setNotificationsOpen(true)}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
                <path d="M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
                <path d="M13.73 21a2 2 0 01-3.46 0" />
              </svg>
              <span className="absolute top-1.5 end-1.5 h-2 w-2 rounded-full bg-brand-600" aria-hidden />
            </button>
            <div className="hidden md:block">{primaryAction}</div>
            <UserMenu />
          </div>
        </div>
        {primaryAction && <div className="border-t border-neutral-100 px-4 py-2 md:hidden">{primaryAction}</div>}
      </header>
      <NotificationsDrawer />
    </>
  );
}
