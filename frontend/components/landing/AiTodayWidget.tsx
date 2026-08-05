"use client";

import Link from "next/link";

import { useI18n } from "@/lib/i18n";

export type AiTodayMetrics = {
  needsAttention: number;
  awaitingSignature: number;
  needsLegal: number;
  deadlinesThisWeek: number;
};

export default function AiTodayWidget({ metrics }: { metrics: AiTodayMetrics }) {
  const { t } = useI18n();

  const lines = [
    {
      count: metrics.needsAttention,
      label: t("home.aiToday.needsAttention"),
      href: "/contracts?status=needs_review",
    },
    {
      count: metrics.awaitingSignature,
      label: t("home.aiToday.awaitingSignature"),
      href: "/contracts?stage=awaiting_signature",
    },
    {
      count: metrics.needsLegal,
      label: t("home.aiToday.needsLegal"),
      href: "/negotiations/monitor?filter=lawyer_review",
    },
    {
      count: metrics.deadlinesThisWeek,
      label: t("home.aiToday.deadlinesThisWeek"),
      href: "/dashboard",
    },
  ];

  return (
    <aside className="surface-glass p-5 md:p-6 motion-safe:animate-slideUp">
      <h2 className="text-sm font-bold uppercase tracking-wide text-brand-700 dark:text-brand-300">{t("home.aiToday.title")}</h2>
      <ul className="mt-4 space-y-3">
        {lines.map((line) => (
          <li key={line.href}>
            <Link href={line.href} className="group flex items-baseline gap-2 rounded-lg px-1 py-0.5 hover:bg-brand-50/50 dark:hover:bg-brand-950/30">
              <span className="text-2xl font-bold tabular-nums text-neutral-900 dark:text-neutral-100">{line.count}</span>
              <span className="text-sm text-neutral-600 group-hover:text-brand-800 dark:text-neutral-400 dark:group-hover:text-brand-200">
                {line.label}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </aside>
  );
}
