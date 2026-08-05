"use client";
// Do not `import * as Icons` from lucide-react — use inline SVG or explicit named imports only.
import {
  BarChart3,
  BookOpen,
  CheckCircle2,
  ChevronsLeft,
  FileSignature,
  FileText,
  GitCompareArrows,
  HelpCircle,
  LayoutDashboard,
  LayoutTemplate,
  MessagesSquare,
  PanelsTopLeft,
  Radar,
  Scale,
  Settings,
  UploadCloud,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import Logo from "@/components/Logo";
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
  | "home"
  | "dashboard"
  | "contracts"
  | "upload"
  | "reviews"
  | "negotiations"
  | "negotiationMonitor"
  | "playbook"
  | "approvals"
  | "signatures"
  | "versions"
  | "templates"
  | "reports"
  | "flowdown"
  | "settings"
  | "help";

/**
 * Every nav destination gets its own glyph. The previous implementation
 * defined two and fell through to a generic circle for everything else, which
 * made eleven of thirteen destinations visually identical.
 */
const ICONS: Record<NavIconName, typeof FileText> = {
  home: PanelsTopLeft,
  dashboard: LayoutDashboard,
  contracts: FileText,
  upload: UploadCloud,
  reviews: MessagesSquare,
  negotiations: Scale,
  negotiationMonitor: Radar,
  playbook: BookOpen,
  approvals: CheckCircle2,
  signatures: FileSignature,
  versions: GitCompareArrows,
  templates: LayoutTemplate,
  reports: BarChart3,
  flowdown: GitCompareArrows,
  settings: Settings,
  help: HelpCircle,
};

function NavIcon({ name }: { name: NavIconName }) {
  const Glyph = ICONS[name];
  return <Glyph className="h-[18px] w-[18px] shrink-0" strokeWidth={1.9} aria-hidden />;
}

const SECTIONS: { titleKey?: TKey; items: NavItem[] }[] = [
  {
    titleKey: "shell.section.workspace",
    items: [
      { href: "/", key: "nav.home", icon: "home" },
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
      { href: "/negotiations/monitor", key: "nav.negotiationMonitor", icon: "negotiationMonitor" },
      { href: "/playbook", key: "nav.playbook", icon: "playbook" },
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

  // Flat index across all sections so the entrance stagger runs continuously
  // down the rail rather than restarting at each group.
  let staggerIndex = 0;

  const nav = (
    <div
      className={cn(
        "relative flex h-full flex-col overflow-hidden border-e border-neutral-200/80 bg-white text-neutral-600",
        "motion-safe:transition-[width] motion-safe:duration-300 motion-safe:ease-settle",
        collapsed ? "w-[4.75rem]" : "w-64",
      )}
    >
      {/* Faint emerald wash at the top of the rail — depth without tinting the
          working area. */}
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-56 bg-[radial-gradient(120%_70%_at_50%_0%,rgb(4_120_87/0.07)_0%,transparent_70%)]"
        aria-hidden
      />

      <div className={cn("relative flex items-center gap-2.5 px-4 py-5", collapsed && "justify-center px-0")}>
        <Link
          href="/"
          aria-label="ميثاق — MITHAQ"
          className="focus-ring flex min-w-0 items-center justify-center rounded-lg"
          onClick={onMobileClose}
        >
          {collapsed ? (
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-sheen font-display text-lg font-bold text-white shadow-glow">
              م
            </span>
          ) : (
            <Logo size="md" tone="brand" />
          )}
        </Link>
      </div>

      <nav className="relative flex-1 overflow-y-auto overflow-x-hidden pb-3">
        {SECTIONS.map((sec) => (
          <div key={sec.titleKey ?? "misc"} className="mb-5">
            {sec.titleKey && !collapsed && (
              <p className="mb-1.5 px-4 text-[10px] font-bold uppercase tracking-[0.14em] text-neutral-400">
                {t(sec.titleKey)}
              </p>
            )}
            <ul className="stagger space-y-0.5 px-2.5">
              {sec.items.map((item) => {
                const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
                const i = staggerIndex++;
                return (
                  <li
                    key={item.href}
                    className="motion-safe:animate-slideUp"
                    style={{ "--i": i } as React.CSSProperties}
                  >
                    <Link
                      href={item.href}
                      prefetch={navPrefetch(item.href)}
                      title={collapsed ? t(item.key) : undefined}
                      onClick={onMobileClose}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "focus-ring group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13.5px] font-medium",
                        "motion-safe:transition-all motion-safe:duration-200 motion-safe:ease-settle",
                        active
                          ? "bg-brand-50 text-brand-800"
                          : "text-neutral-600 hover:bg-neutral-50 hover:text-ink-900",
                        collapsed && "justify-center px-2",
                      )}
                    >
                      {/* Logical inset-inline-start, so the marker sits on the
                          correct edge under both RTL and LTR. */}
                      {active && (
                        <span
                          className="absolute inset-y-2 start-0 w-[3px] rounded-full bg-brand-600"
                          aria-hidden
                        />
                      )}
                      <span className={cn(active ? "text-brand-600" : "text-neutral-400 group-hover:text-brand-600")}>
                        <NavIcon name={item.icon} />
                      </span>
                      {!collapsed && <span className="truncate">{t(item.key)}</span>}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="relative border-t border-neutral-200/80 p-2.5">
        {BOTTOM.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onMobileClose}
              aria-current={active ? "page" : undefined}
              className={cn(
                "focus-ring mb-0.5 flex items-center gap-3 rounded-xl px-3 py-2 text-[13.5px] motion-safe:transition-colors",
                active ? "bg-brand-50 text-brand-800" : "text-neutral-600 hover:bg-neutral-50 hover:text-ink-900",
                collapsed && "justify-center px-2",
              )}
            >
              <NavIcon name={item.icon} />
              {!collapsed && <span className="truncate">{t(item.key)}</span>}
            </Link>
          );
        })}

        {/* Always renders a label or an icon — the previous version emitted an
            empty button once collapsed, stranding the user with no way back. */}
        <button
          type="button"
          onClick={toggleCollapse}
          aria-expanded={!collapsed}
          title={collapsed ? t("shell.expand") : t("shell.collapse")}
          className={cn(
            "focus-ring mt-1 flex w-full items-center gap-3 rounded-xl px-3 py-2 text-xs text-neutral-500 hover:bg-neutral-50 hover:text-neutral-700 motion-safe:transition-colors",
            collapsed && "justify-center px-2",
          )}
        >
          <ChevronsLeft
            className={cn(
              "h-4 w-4 shrink-0 motion-safe:transition-transform motion-safe:duration-300 rtl:rotate-180",
              collapsed && "rotate-180 rtl:rotate-0",
            )}
            aria-hidden
          />
          {!collapsed && <span>{t("shell.collapse")}</span>}
        </button>
      </div>
    </div>
  );

  return (
    <>
      <aside className="sticky top-0 hidden h-screen shrink-0 md:block">{nav}</aside>
      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-ink-900/40 backdrop-blur-sm motion-safe:animate-fadeIn"
            aria-label="Close"
            onClick={onMobileClose}
          />
          <div className="relative h-full w-64 max-w-[85vw] shadow-elevation-4 motion-safe:animate-fadeIn">{nav}</div>
        </div>
      )}
    </>
  );
}

export function SidebarToggle({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      className="focus-ring rounded-lg p-2 text-neutral-600 hover:bg-neutral-100 md:hidden"
      onClick={onClick}
      aria-label="Menu"
    >
      <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M4 6h16M4 12h16M4 18h16" strokeLinecap="round" />
      </svg>
    </button>
  );
}

export function GlobalSearchButton() {
  const { setPaletteOpen } = useShell();
  const { t } = useI18n();
  return (
    <button
      type="button"
      className="focus-ring hidden items-center gap-2 rounded-xl border border-neutral-200 bg-white px-3 py-1.5 text-sm text-neutral-500 shadow-elevation-1 hover:border-neutral-300 hover:text-neutral-700 motion-safe:transition-all motion-safe:duration-200 sm:flex"
      onClick={() => setPaletteOpen(true)}
    >
      <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-3.5-3.5" strokeLinecap="round" />
      </svg>
      {t("shell.search")}
      <kbd className="kbd">⌘K</kbd>
    </button>
  );
}
