"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import ImportEmailDialog from "@/components/negotiation-monitor/ImportEmailDialog";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import DataTable from "@/components/ui/DataTable";
import SectionHeader from "@/components/ui/SectionHeader";
import { useCachedFetch } from "@/lib/cache";
import { listNegotiationMonitorThreads } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { NegotiationMonitorThread } from "@/lib/types";

export default function NegotiationMonitorPage() {
  const { t } = useI18n();
  const [filter, setFilter] = useState<string | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [importThreadId, setImportThreadId] = useState<string | null>(null);

  const cacheKey = filter ? `negotiation:threads:${filter}` : "negotiation:threads";
  const { data, isLoading, refresh } = useCachedFetch(cacheKey, () =>
    listNegotiationMonitorThreads(filter ?? undefined).then((r) => r.threads)
  );

  const rows = useMemo(() => data ?? [], [data]);

  const columns = [
    { id: "counterparty", header: t("nav.contracts"), cell: (r: NegotiationMonitorThread) => r.counterparty_name ?? r.counterparty_email ?? "—" },
    { id: "contract", header: t("nav.contracts"), cell: (r: NegotiationMonitorThread) => r.contract_title ?? "—" },
    { id: "subject", header: t("monitor.emailThread"), cell: (r: NegotiationMonitorThread) => r.subject ?? "—" },
    { id: "risk", header: t("monitor.filters.highRisk"), cell: (r: NegotiationMonitorThread) => r.overall_risk_score ?? "—" },
    { id: "status", header: t("nav.approvals"), cell: (r: NegotiationMonitorThread) => <Badge tone="subtle">{r.status}</Badge> },
    {
      id: "actions",
      header: "",
      cell: (r: NegotiationMonitorThread) => (
        <div className="flex gap-2">
          <Link href={`/negotiations/monitor/${r.id}`} className="text-sm font-semibold text-brand-600">
            {t("common.viewAll")}
          </Link>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => {
              setImportThreadId(r.id);
              setImportOpen(true);
            }}
          >
            {t("monitor.importEmail")}
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <SectionHeader title={t("monitor.title")} eyebrow={t("nav.negotiationMonitor")} />
      {rows.some((row) => row.simulated) && (
        <Badge tone="warning">{t("monitor.simulatedLabel")}</Badge>
      )}
      <div className="flex flex-wrap gap-2">
        <Button variant={filter === null ? "primary" : "secondary"} size="sm" onClick={() => setFilter(null)}>
          {t("common.clear")}
        </Button>
        <Button variant={filter === "lawyer_review" ? "primary" : "secondary"} size="sm" onClick={() => setFilter("lawyer_review")}>
          {t("monitor.awaitingLawyer")}
        </Button>
        <Button variant={filter === "monitoring" ? "primary" : "secondary"} size="sm" onClick={() => setFilter("monitoring")}>
          {t("monitor.filters.needsReview")}
        </Button>
      </div>
      {isLoading && rows.length === 0 ? (
        <p className="text-hint">{t("common.loading")}</p>
      ) : (
        <DataTable columns={columns} rows={rows} getRowKey={(r) => r.id} />
      )}
      <ImportEmailDialog
        open={importOpen}
        threadId={importThreadId}
        onClose={() => setImportOpen(false)}
        onDone={() => refresh()}
      />
    </div>
  );
}
