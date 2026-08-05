"use client";

import Link from "next/link";

import EmptyState from "@/components/ui/EmptyState";
import { useI18n } from "@/lib/i18n";
import type { ApprovalSummaryKpis, DeadlineRow, ReviewRequestRow, SignatureSummaryKpis } from "@/lib/types";
import { formatPortfolioSar } from "@/lib/pipeline";

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
      subtitle: String(data.sigKpis.awaiting_signature),
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
    <section className="surface-panel p-5">
      <h2 className="text-sm font-bold text-neutral-900 dark:text-neutral-100">{t("home.attention.title")}</h2>
      {items.length === 0 ? (
        <div className="mt-4">
          <EmptyState title={t("common.empty")} />
        </div>
      ) : (
        <ul className="mt-4 divide-y divide-neutral-100 dark:divide-neutral-800">
          {items.map((item) => (
            <li key={`${item.group}-${item.id}`}>
              <Link href={item.href} className="flex items-center justify-between gap-3 py-3 hover:bg-neutral-50/80 dark:hover:bg-neutral-800/40">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-neutral-900 dark:text-neutral-100">{item.title}</p>
                  <p className="text-xs text-neutral-500">{item.subtitle}</p>
                </div>
                <span className="text-brand-600">→</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
