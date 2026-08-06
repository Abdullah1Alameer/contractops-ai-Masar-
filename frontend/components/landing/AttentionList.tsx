"use client";

import { ChevronLeft } from "lucide-react";
import Link from "next/link";

import EmptyState from "@/components/ui/EmptyState";
import { useI18n } from "@/lib/i18n";
import type { ApprovalSummaryKpis, DeadlineRow, ReviewRequestRow, SignatureSummaryKpis } from "@/lib/types";
import { formatPortfolioSar } from "@/lib/pipeline";
import { formatNum } from "@/lib/utils";

export type AttentionInput = {
  reviewItems: ReviewRequestRow[];
  approvalKpis: ApprovalSummaryKpis | null;
  sigKpis: SignatureSummaryKpis | null;
  upcomingList: { contract_id: string; contract_title: string; row: DeadlineRow }[];
  claimableSar: number;
  locale: string;
};

type AttentionItem = { id: string; title: string; subtitle: string; href: string; group: string };

export default function AttentionList({ data }: { data: AttentionInput }) {
  const { t } = useI18n();

  const items: AttentionItem[] = [];

  for (const r of data.reviewItems.filter((x) => x.status === "sent" || x.status === "opened").slice(0, 6)) {
    items.push({
      id: r.id,
      title: r.contract_title ?? r.contract_id,
      subtitle: t("home.attention.waitingClient"),
      href: `/contracts/${r.contract_id}`,
      group: "client",
    });
  }

  if (data.approvalKpis) {
    if (data.approvalKpis.pending_finance > 0) {
      items.push({
        id: "finance",
        title: t("home.attention.pendingFinance"),
        subtitle: String(data.approvalKpis.pending_finance),
        href: "/contracts?stage=internal_review&role=finance",
        group: "finance",
      });
    }
    if (data.approvalKpis.pending_legal > 0) {
      items.push({
        id: "legal",
        title: t("home.attention.pendingLegal"),
        subtitle: String(data.approvalKpis.pending_legal),
        href: "/contracts?stage=internal_review&role=legal",
        group: "legal",
      });
    }
  }

  if (data.sigKpis && data.sigKpis.awaiting_signature > 0) {
    items.push({
      id: "sig",
      title: t("home.attention.awaitingSignature"),
      subtitle: formatNum(data.sigKpis.awaiting_signature, data.locale as "ar" | "en"),
      href: "/contracts?stage=awaiting_signature",
      group: "sig",
    });
  }

  for (const u of data.upcomingList.slice(0, 5)) {
    items.push({
      id: u.row.id ?? u.contract_id,
      title: u.row.title ?? u.contract_title,
      subtitle: t("home.attention.deadlineThisWeek"),
      href: `/contracts/${u.contract_id}`,
      group: "deadline",
    });
  }

  if (data.claimableSar > 0) {
    items.push({
      id: "claim",
      title: t("home.attention.claimablePayment"),
      subtitle: formatPortfolioSar(data.claimableSar, data.locale),
      href: "/dashboard",
      group: "claim",
    });
  }

  return (
    <section className="glass-card p-6 md:p-7">
      <h2 className="text-lg font-extrabold tracking-tight text-slate-900">{t("home.attention.title")}</h2>
      {items.length === 0 ? (
        <div className="mt-4">
          <EmptyState title={t("common.empty")} />
        </div>
      ) : (
        <ul className="mt-4 divide-y divide-slate-100">
          {items.map((item) => (
            <li key={`${item.group}-${item.id}`}>
              <Link href={item.href} className="group flex items-center justify-between gap-3 rounded-2xl px-2 py-3.5 transition-colors duration-200 hover:bg-emerald-50/50">
                <div className="min-w-0">
                  <p className="truncate text-sm font-bold text-slate-900 group-hover:text-emerald-800">{item.title}</p>
                  <p className="tnum mt-0.5 text-xs font-medium text-slate-500">{item.subtitle}</p>
                </div>
                <ChevronLeft
                  className="h-4 w-4 shrink-0 text-slate-300 transition-all duration-200 group-hover:text-emerald-600 rtl:rotate-0 ltr:rotate-180"
                  aria-hidden
                />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
