"use client";

import Link from "next/link";

import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

type Action = { href: string; labelKey: import("@/lib/i18n").TKey; icon: React.ReactNode };

function IconUpload() {
  return (
    <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 16V4m0 0l-4 4m4-4l4 4M4 20h16" />
    </svg>
  );
}

function IconDoc() {
  return (
    <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
      <path d="M14 2v6h6M8 13h8M8 17h5" />
    </svg>
  );
}

function IconChart() {
  return (
    <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M4 19V5M4 19h16M8 17V9m4 8V7m4 10v-4" />
    </svg>
  );
}

function IconGrid() {
  return (
    <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
      <rect x="14" y="14" width="7" height="7" rx="1" />
    </svg>
  );
}

function IconHandshake() {
  return (
    <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M7 11l2-2 3 3 5-5 2 2-7 7-5-5z" />
      <path d="M4 20h16" />
    </svg>
  );
}

export default function QuickActions() {
  const { t } = useI18n();

  const actions: Action[] = [
    { href: "/upload", labelKey: "home.quick.newContract", icon: <IconDoc /> },
    { href: "/upload", labelKey: "home.quick.upload", icon: <IconUpload /> },
    { href: "/negotiations/monitor", labelKey: "home.quick.negotiations", icon: <IconHandshake /> },
    { href: "/templates", labelKey: "home.quick.templates", icon: <IconDoc /> },
    { href: "/reports", labelKey: "home.quick.reports", icon: <IconChart /> },
    { href: "/dashboard", labelKey: "home.quick.dashboard", icon: <IconGrid /> },
  ];

  return (
    <section className="surface-panel p-5">
      <h2 className="text-sm font-bold text-neutral-900 dark:text-neutral-100">{t("home.quick.title")}</h2>
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
        {actions.map((a) => (
          <Link
            key={a.labelKey}
            href={a.href}
            className={cn(
              "surface-glass hover-lift flex flex-col items-center gap-2 rounded-xl p-4 text-center",
              "text-sm font-semibold text-neutral-800 dark:text-neutral-200"
            )}
          >
            <span className="text-brand-600 dark:text-brand-400">{a.icon}</span>
            {t(a.labelKey)}
          </Link>
        ))}
      </div>
    </section>
  );
}
