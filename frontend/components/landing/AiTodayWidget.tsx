"use client";

import Link from "next/link";

import { useI18n } from "@/lib/i18n";
import { formatCount, formatNum } from "@/lib/utils";

export type AiTodayMetrics = {
  needsAttention: number;
  awaitingSignature: number;
  needsLegal: number;
  deadlinesThisWeek: number;
};

export default function AiTodayWidget({ metrics }: { metrics: AiTodayMetrics }) {
  const { t, lang } = useI18n();

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
    <aside className="glass-card glass-card-hover p-6 md:p-7 motion-safe:animate-slideUp">
      <h2 className="text-sm font-bold tracking-tight text-emerald-700">{t("home.aiToday.title")}</h2>
      <ul className="mt-4 space-y-3">
        {lines.map((line) => (
          <li key={line.href}>
            <Link href={line.href} className="group flex items-baseline gap-2.5 rounded-xl px-2 py-1.5 transition-colors duration-200 hover:bg-emerald-50/60">
              <span className="tnum text-2xl font-extrabold tracking-tight text-slate-900">{formatCount(line.count, lang)}</span>
              <span className="text-sm font-medium text-slate-500 group-hover:text-emerald-700">
                {line.label}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </aside>
  );
}
