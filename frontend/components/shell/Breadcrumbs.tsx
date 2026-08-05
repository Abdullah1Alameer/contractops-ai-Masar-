"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useShell } from "@/components/shell/ShellContext";
import { useI18n, type TKey } from "@/lib/i18n";

const SEGMENTS: Record<string, TKey> = {
  dashboard: "nav.dashboard",
  contracts: "nav.contracts",
  upload: "nav.upload",
  flowdown: "nav.flowdown",
  reviews: "nav.reviews",
  negotiations: "nav.negotiations",
  approvals: "nav.approvals",
  signatures: "nav.signatures",
  versions: "nav.versions",
  templates: "nav.templates",
  reports: "nav.reports",
  settings: "nav.settings",
  help: "nav.help",
};

export default function Breadcrumbs() {
  const pathname = usePathname();
  const { t } = useI18n();
  const { pageTitle } = useShell();
  const parts = pathname.split("/").filter(Boolean);

  if (parts.length === 0) return null;

  const crumbs: { href: string; label: string }[] = [];
  let acc = "";
  for (let i = 0; i < parts.length; i++) {
    acc += `/${parts[i]}`;
    const key = SEGMENTS[parts[i]];
    const isUuid = parts[i].length > 20;
    crumbs.push({
      href: acc,
      label: isUuid && pageTitle ? pageTitle : key ? t(key) : parts[i],
    });
  }

  return (
    <nav aria-label="Breadcrumb" className="hidden min-w-0 truncate text-sm text-gray-500 sm:block">
      <ol className="flex flex-wrap items-center gap-1">
        {crumbs.map((c, i) => (
          <li key={c.href} className="flex items-center gap-1">
            {i > 0 && <span className="text-gray-300">/</span>}
            {i === crumbs.length - 1 ? (
              <span className="font-medium text-gray-900">{c.label}</span>
            ) : (
              <Link href={c.href} className="hover:text-brand-700">
                {c.label}
              </Link>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
