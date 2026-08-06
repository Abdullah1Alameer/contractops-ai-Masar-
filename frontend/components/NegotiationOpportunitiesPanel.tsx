"use client";

import { useCallback, useEffect, useState } from "react";

import Badge from "@/components/ui/Badge";
import { fetchNegotiationOpportunities } from "@/lib/api";
import { useI18n, type TKey } from "@/lib/i18n";
import type { NegotiationOpportunityRow } from "@/lib/types";

// This is a *proactive*, AI-suggested "other clauses worth negotiating"
// widget — a different, optional data source from the real, actionable
// negotiation item(s) NegotiationPanel renders below it on the same tab.
// It used to render a full-page EmptyState ("No structured negotiation
// issue detected") whenever there were no suggestions, which read as if
// the whole Negotiation tab were empty even when a real, active
// negotiation was sitting right underneath (see docs/
// negotiation-flow-bugfix-report.md, Bug 1). Having nothing to
// proactively suggest is not itself noteworthy, so it now renders
// nothing rather than a prominent empty state.
export default function NegotiationOpportunitiesPanel({ contractId }: { contractId: string }) {
  const { t } = useI18n();
  const [rows, setRows] = useState<NegotiationOpportunityRow[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    fetchNegotiationOpportunities(contractId)
      .then((r) => setRows(r.opportunities ?? []))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [contractId]);

  useEffect(load, [load]);

  if (loading || !rows.length) return null;

  return (
    <div className="mb-6 space-y-3">
      <h3 className="text-sm font-semibold">{t("negotiation.opportunitiesTitle")}</h3>
      <ul className="space-y-2">
        {rows.map((o) => (
          <li key={o.id} className="rounded-lg border border-gray-200 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="warning">{o.category}</Badge>
              {o.clause_ref && <span className="text-xs text-gray-500">{o.clause_ref}</span>}
              {o.negotiability === "non_negotiable" && (
                <Badge tone="neutral">{t("negotiation.nonNegotiable" as TKey)}</Badge>
              )}
            </div>
            <p className="mt-2 text-sm font-medium text-gray-900">{o.issue}</p>
            {o.recommendation && (
              <p className="mt-1 text-xs text-gray-600">
                {t("negotiation.recommendation" as TKey)}: {o.recommendation}
              </p>
            )}
            {o.suggested_counterproposal && (
              <p className="mt-1 text-xs text-gray-600">{o.suggested_counterproposal}</p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
