"use client";
// Do not `import * as Icons` from lucide-react — use inline SVG or explicit named imports only.
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { useShell } from "@/components/shell/ShellContext";
import { useI18n, type TKey } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const STORAGE_KEY = "sidebar.collapsed";

const PREFETCH_ROUTES = new Set(["/", "/dashboard", "/contracts", "/reviews", "/approvals", "/signatures", "/versions"]);

function navPrefetch(href: string): boolean | undefined {
  return PREFETCH_ROUTES.has(href) ? true : undefined;
}

type NavItem = { href: string; key: TKey; icon: NavIconName };

type NavIconName =
  | "dashboard"
  | "contracts"
  | "upload"
  | "reviews"
  | "negotiations"
  | "approvals"
  | "signatures"
  | "versions"
  | "templates"
  | "reports"
  | "flowdown"
  | "settings"
  | "help";

function NavIcon({ name }: { name: NavIconName }) {
  const cls = "h-5 w-5 shrink-0";
  switch (name) {
    case "dashboard":
      return (
        <svg className={cls} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="3" y="3" width="7" height="7" rx="1" />
          <rect x="14" y="3" width="7" height="7" rx="1" />
          <rect x="3" y="14" width="7" height="7" rx="1" />
          <rect x="14" y="14" width="7" height="7" rx="1" />
        </svg>
      );
    case "contracts":
      return (
        <svg className={cls} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M4 6h16M4 12h16M4 18h10" />
        </svg>
      );
    default:
      return (
        <svg className={cls} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="9" />
        </svg>
      );
  }
}

const SECTIONS: { titleKey?: TKey; items: NavItem[] }[] = [
  {
    titleKey: "shell.section.workspace",
    items: [
      { href: "/", key: "nav.home", icon: "dashboard" },
      { href: "/dashboard", key: "nav.dashboard", icon: "dashboard" },
      { href: "/contracts", key: "nav.contracts", icon: "contracts" },
      { href: "/upload", key: "nav.upload", icon: "upload" },
    ],
  },
  {
    titleKey: "shell.section.lifecycle",
    items: [
      { href: "/reviews", key: "nav.reviews", icon: "reviews" },
      { href: "/negotiations", key: "nav.negotiations", icon: "negotiations" },
      { href: "/negotiations/monitor", key: "nav.negotiationMonitor", icon: "negotiations" },
      { href: "/playbook", key: "nav.playbook", icon: "templates" },
      { href: "/approvals", key: "nav.approvals", icon: "approvals" },
      { href: "/signatures", key: "nav.signatures", icon: "signatures" },
      { href: "/versions", key: "nav.versions", icon: "versions" },
    ],
  },
  {
    titleKey: "shell.section.library",
    items: [
      { href: "/templates", key: "nav.templates", icon: "templates" },
      { href: "/reports", key: "nav.reports", icon: "reports" },
      { href: "/flowdown", key: "nav.flowdown", icon: "flowdown" },
    ],
  },
];

const BOTTOM: NavItem[] = [
  { href: "/settings", key: "nav.settings", icon: "settings" },
  { href: "/help", key: "nav.help", icon: "help" },
];

type SidebarProps = {
  mobileOpen: boolean;
  onMobileClose: () => void;
};

export default function Sidebar({ mobileOpen, onMobileClose }: SidebarProps) {
  const { t } = useI18n();
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    try {
      setCollapsed(localStorage.getItem(STORAGE_KEY) === "1");
    } catch {
      /* ignore */
    }
  }, []);

  const toggleCollapse = () => {
    setCollapsed((c) => {
      const next = !c;
      try {
        localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
      } catch {
        /* ignore */
      }
      return next;
    });
  };

  const nav = (
    <div
      className={cn(
        "flex h-full flex-col border-gray-200 bg-white",
        collapsed ? "w-[4.5rem]" : "w-60",
        "border-e"
      )}
    >
      <div className={cn("flex items-center gap-2 border-b border-gray-100 p-3", collapsed && "justify-center")}>
        <Link href="/contracts" className="flex min-w-0 items-center gap-2" onClick={onMobileClose}>
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white">
            C
          </span>
          {!collapsed && <span className="truncate font-bold text-brand-800">{t("appName")}</span>}
        </Link>
      </div>
      <div className="flex-1 overflow-y-auto py-3">
        {SECTIONS.map((sec) => (
          <div key={sec.titleKey ?? "misc"} className="mb-4">
            {sec.titleKey && !collapsed && (
              <p className="section-title mb-1 px-3">{t(sec.titleKey)}</p>
            )}
            <ul className="space-y-0.5 px-2">
              {sec.items.map((item) => {
                const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      prefetch={navPrefetch(item.href)}
                      title={collapsed ? t(item.key) : undefined}
                      onClick={onMobileClose}
                      className={cn(
                        "focus-ring relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium motion-safe:transition-colors",
                        active ? "bg-brand-50 text-brand-800" : "text-neutral-600 hover:bg-neutral-50",
                        collapsed && "justify-center px-2"
                      )}
                    >
                      {active && (
                        <span className="absolute inset-y-1 start-0 w-1 rounded-full bg-brand-600" aria-hidden />
                      )}
                      <NavIcon name={item.icon} />
                      {!collapsed && <span>{t(item.key)}</span>}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>
      <div className="border-t border-gray-100 p-2">
        {BOTTOM.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onMobileClose}
              className={cn(
                "focus-ring mb-0.5 flex items-center gap-3 rounded-lg px-3 py-2 text-sm",
                active ? "bg-brand-50 text-brand-800" : "text-gray-600 hover:bg-muted-50",
                collapsed && "justify-center"
              )}
            >
              <NavIcon name={item.icon} />
              {!collapsed && t(item.key)}
            </Link>
          );
        })}
        <button
          type="button"
          className="focus-ring mt-1 flex w-full items-center gap-3 rounded-lg px-3 py-2 text-xs text-gray-500 hover:bg-muted-50"
          onClick={toggleCollapse}
        >
          {!collapsed && (collapsed ? t("shell.expand") : t("shell.collapse"))}
        </button>
      </div>
    </div>
  );

  return (
    <>
      <aside className="sticky top-0 hidden h-screen shrink-0 md:block">{nav}</aside>
      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <button type="button" className="absolute inset-0 bg-black/40" aria-label="Close" onClick={onMobileClose} />
          <div className="relative h-full w-60 max-w-[85vw] shadow-xl">{nav}</div>
        </div>
      )}
    </>
  );
}

export function SidebarToggle({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" className="focus-ring rounded-lg p-2 text-gray-600 hover:bg-muted-50 md:hidden" onClick={onClick}>
      ☰
    </button>
  );
}

export function GlobalSearchButton() {
  const { setPaletteOpen } = useShell();
  const { t } = useI18n();
  return (
    <button
      type="button"
      className="focus-ring hidden items-center gap-2 rounded-lg border border-gray-200 px-3 py-1.5 text-sm text-gray-500 hover:bg-muted-50 sm:flex"
      onClick={() => setPaletteOpen(true)}
    >
      {t("shell.search")}
      <kbd className="kbd">⌘K</kbd>
    </button>
  );
}
