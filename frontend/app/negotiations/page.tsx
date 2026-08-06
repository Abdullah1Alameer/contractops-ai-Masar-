"use client";
import Link from "next/link";
import { useMemo, useState } from "react";

import Badge from "@/components/ui/Badge";
import { Card, CardBody } from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import { SkeletonTable } from "@/components/ui/Skeleton";
import Stat from "@/components/ui/Stat";
import { fetchNegotiationBoard } from "@/lib/api";
import { useCachedFetch } from "@/lib/cache";
import { useI18n, type TKey } from "@/lib/i18n";
import type { NegotiationBoardItem } from "@/lib/types";
import { cn, formatDate } from "@/lib/utils";

type FilterKey = "all" | "pending" | "waiting_client" | "waiting_lawyer" | "high_risk" | "overdue";

const FILTERS: { key: FilterKey; labelKey: TKey }[] = [
  { key: "all", labelKey: "negotiationsBoard.filter.all" },
  { key: "pending", labelKey: "negotiationsBoard.filter.pending" },
  { key: "waiting_client", labelKey: "negotiationsBoard.filter.waitingClient" },
  { key: "waiting_lawyer", labelKey: "negotiationsBoard.filter.waitingLawyer" },
  { key: "high_risk", labelKey: "negotiationsBoard.filter.highRisk" },
  { key: "overdue", labelKey: "negotiationsBoard.filter.overdue" },
];

function riskTone(r: string | null): "success" | "warning" | "orange" | "danger" | "neutral" {
  if (r === "critical") return "danger";
  if (r === "high") return "orange";
  if (r === "medium") return "warning";
  if (r === "low") return "success";
  return "neutral";
}

function matchesFilter(item: NegotiationBoardItem, filter: FilterKey): boolean {
  switch (filter) {
    case "waiting_client":
      return item.waiting_party === "client";
    case "waiting_lawyer":
      return item.waiting_party === "lawyer";
    case "high_risk":
      return item.risk_level === "high" || item.risk_level === "critical";
    case "overdue":
      return item.sla_status === "overdue" || item.missed_deadlines > 0;
    case "pending":
      return item.waiting_party === null;
    default:
      return true;
  }
}

export default function NegotiationsPage() {
  const { t, lang } = useI18n();
  const [filter, setFilter] = useState<FilterKey>("all");
  const [search, setSearch] = useState("");

  const { data, isLoading } = useCachedFetch("negotiations:board", fetchNegotiationBoard);
  const items = data?.items ?? [];
  const summary = data?.summary;

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return items
      .filter((i) => matchesFilter(i, filter))
      .filter(
        (i) =>
          !q ||
          (i.contract_title ?? "").toLowerCase().includes(q) ||
          (i.counterparty ?? "").toLowerCase().includes(q)
      );
  }, [items, filter, search]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{t("nav.negotiations")}</h1>
        <p className="mt-1 text-sm text-gray-500">{t("negotiationsBoard.subtitle")}</p>
      </div>

      {summary && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Stat label={t("negotiationsBoard.metric.total")} value={summary.total_active} tone="brand" />
          <Stat label={t("negotiationsBoard.metric.pending")} value={summary.pending} tone="default" />
          <Stat label={t("negotiationsBoard.metric.waitingClient")} value={summary.waiting_client} tone="warning" />
          <Stat label={t("negotiationsBoard.metric.waitingLawyer")} value={summary.waiting_lawyer} tone="warning" />
          <Stat label={t("negotiationsBoard.metric.highRisk")} value={summary.high_risk} tone="danger" />
          <Stat label={t("negotiationsBoard.metric.overdue")} value={summary.overdue} tone="danger" />
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            type="button"
            onClick={() => setFilter(f.key)}
            className={cn("chip", filter === f.key && "bg-brand-600 text-white hover:bg-brand-600")}
          >
            {t(f.labelKey)}
          </button>
        ))}
        <input
          className="ms-auto min-w-[220px] flex-1 rounded-lg border border-gray-200 px-3 py-2 text-sm sm:flex-none"
          placeholder={t("negotiationsBoard.searchPlaceholder")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {/* "Unread messages" was part of the original brief but has no backing
          data — no read/unread column exists anywhere in the schema. Message
          count (real, from negotiation_messages) is shown per row instead;
          see docs/negotiation-flow-bugfix-report.md. */}

      {isLoading ? (
        <SkeletonTable rows={5} />
      ) : filtered.length === 0 ? (
        <EmptyState title={t(items.length === 0 ? "negotiationsBoard.emptyAll" : "negotiationsBoard.emptyFiltered")} />
      ) : (
        <div className="space-y-3">
          {filtered.map((item) => (
            <Card key={item.negotiation_id}>
              <CardBody className="space-y-2">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-semibold text-gray-900">{item.contract_title ?? "—"}</p>
                    <p className="text-sm text-gray-600">{item.counterparty ?? "—"}</p>
                    {item.issue && <p className="mt-1 text-sm text-gray-700">{item.issue}</p>}
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="info">{t(`negotiation.workflow.${item.workflow_status}` as TKey)}</Badge>
                    {item.contract_stage && <Badge tone="subtle">{t(`stage.${item.contract_stage}` as TKey)}</Badge>}
                    {item.risk_level && <Badge tone={riskTone(item.risk_level)}>{t(`negotiation.risk.${item.risk_level}` as TKey)}</Badge>}
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-500">
                  <span>
                    {t("negotiation.card.lawyer")}: {item.assigned_lawyer ?? "—"}
                  </span>
                  <span>
                    {t("negotiation.card.lastActivity")}: {item.updated_at ? formatDate(item.updated_at, lang) : "—"}
                  </span>
                  <span>
                    {t("negotiationsBoard.messages")}: {item.message_count}
                  </span>
                  {item.waiting_party && (
                    <span className="font-medium text-amber-700">
                      {t(item.waiting_party === "client" ? "negotiation.waitingOn.client" : "negotiation.waitingOn.lawyer")}
                    </span>
                  )}
                  {item.days_waiting != null && item.waiting_party === "client" && (
                    <span
                      className={cn(
                        "font-medium",
                        item.sla_status === "overdue" && "text-danger-700",
                        item.sla_status === "approaching" && "text-orange-700"
                      )}
                    >
                      {t("negotiationsBoard.waitingDays").replace("{n}", String(item.days_waiting))}
                    </span>
                  )}
                  {(item.critical_deadlines > 0 || item.missed_deadlines > 0) && (
                    <span className="font-medium text-danger-700">
                      {t("negotiationsBoard.deadlineFlag")
                        .replace("{critical}", String(item.critical_deadlines))
                        .replace("{missed}", String(item.missed_deadlines))}
                    </span>
                  )}
                  {item.is_stale && <span className="font-medium text-sky-700">{t("versions.staleWarning")}</span>}
                </div>

                <Link
                  href={`/contracts/${item.contract_id}?tab=negotiation&item=${item.negotiation_id}`}
                  className="inline-block text-sm font-semibold text-brand-700 hover:underline"
                >
                  {t("negotiationsBoard.open")}
                </Link>
              </CardBody>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
