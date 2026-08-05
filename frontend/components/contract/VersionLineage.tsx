"use client";

import { useMemo, useState } from "react";

import EventDetailDrawer from "@/components/contract/EventDetailDrawer";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import RiskScoreRing from "@/components/ui/RiskScoreRing";
import { transitionReasonKey } from "@/lib/lineageLinks";
import { useI18n, type TKey } from "@/lib/i18n";
import type { VersionLineageEvent, VersionLineageResponse, VersionLineageVersion } from "@/lib/types";
import { cn, formatDate } from "@/lib/utils";

const CATEGORY_DOT: Record<string, string> = {
  version: "bg-neutral-400",
  ai: "bg-blue-500",
  review: "bg-violet-500",
  negotiation: "bg-amber-500",
  approval: "bg-brand-600",
  signature: "bg-indigo-600",
  lifecycle: "bg-neutral-500",
  comparison: "bg-teal-600",
};

function eventTitle(event: VersionLineageEvent, t: (k: TKey) => string) {
  const key = `activity.${event.event_type}` as TKey;
  const label = t(key);
  return label === key ? event.event_type.replace(/_/g, " ") : label;
}

function VersionNode({
  v,
  expanded,
  onToggle,
  onEventClick,
  highlightEventId,
}: {
  v: VersionLineageVersion;
  expanded: boolean;
  onToggle: () => void;
  onEventClick: (e: VersionLineageEvent) => void;
  highlightEventId?: string | null;
}) {
  const { t, lang } = useI18n();
  return (
    <div className={cn("relative ps-6", v.is_current && "rounded-card ring-2 ring-brand-600/20")}>
      <span className="absolute start-0 top-3 h-3 w-3 rounded-full bg-brand-600 ring-4 ring-brand-100" aria-hidden />
      <div className="surface-card p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-lg font-bold text-neutral-900">{v.version_label}</h3>
              {v.is_current && <Badge tone="success">{t("versions.current")}</Badge>}
              {v.is_signed && <Badge tone="info">{t("versions.signedBadge")}</Badge>}
              {v.is_approved && !v.is_signed && <Badge tone="success">{t("versions.approvedBadge")}</Badge>}
              {v.is_superseded && !v.is_current && <Badge tone="neutral">{t("versions.superseded")}</Badge>}
            </div>
            <p className="mt-1 text-sm text-neutral-600">
              {t("versions.audit.uploadedBy")}: {v.created_by_display ?? v.created_by ?? "—"} ·{" "}
              {formatDate(v.created_at, lang)}
            </p>
            {v.change_summary && (
              <p className="mt-1 text-sm text-neutral-700">
                {t("versions.changeReason")}: {v.change_summary}
              </p>
            )}
            {v.workflow_stale_count > 0 && (
              <p className="mt-2 text-sm text-warning-800">{t("versions.staleWarning")}</p>
            )}
          </div>
          <div className="flex flex-col items-center gap-1">
            {v.risk_score != null ? (
              <RiskScoreRing score={v.risk_score} size={48} label={t("versions.riskScore")} />
            ) : (
              <span className="text-xs text-neutral-500">{t("versions.riskNotCalculated")}</span>
            )}
          </div>
        </div>
        <Button variant="secondary" size="sm" className="mt-3" onClick={onToggle}>
          {expanded ? t("versions.hideEvents") : t("versions.showEvents")} ({v.event_count})
        </Button>
        {expanded && (
          <ul className="mt-3 space-y-2 border-s-2 border-neutral-100 ps-4">
            {v.events.map((e) => (
              <li key={e.event_id}>
                <button
                  type="button"
                  className={cn(
                    "flex w-full items-start gap-2 rounded-lg px-2 py-1.5 text-start text-sm hover:bg-neutral-50",
                    highlightEventId === e.event_id && "ring-2 ring-brand-500/40"
                  )}
                  onClick={() => onEventClick(e)}
                >
                  <span
                    className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-full", CATEGORY_DOT[e.event_category] ?? "bg-neutral-400")}
                    aria-hidden
                  />
                  <span className="flex-1">
                    <span className="font-medium text-neutral-900">{eventTitle(e, t)}</span>
                    <span className="block text-xs text-neutral-500">
                      {e.actor ?? "—"} · {e.timestamp?.slice(0, 16) ?? "—"}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default function VersionLineage({
  contractId,
  lineage,
  highlightEventId,
}: {
  contractId: string;
  lineage: VersionLineageResponse;
  highlightEventId?: string | null;
}) {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState<Record<string, boolean>>(() => {
    const init: Record<string, boolean> = {};
    const sorted = [...lineage.versions].sort((a, b) => b.version_number - a.version_number);
    sorted.slice(0, 3).forEach((v) => {
      init[v.id] = true;
    });
    if (lineage.current_version_id) init[lineage.current_version_id] = true;
    return init;
  });
  const [drawerEvent, setDrawerEvent] = useState<VersionLineageEvent | null>(null);

  const transitionByTo = useMemo(() => {
    const m = new Map<string, (typeof lineage.transitions)[0]>();
    lineage.transitions.forEach((tr) => m.set(tr.to_version_id, tr));
    return m;
  }, [lineage.transitions]);

  const versionLabel = (id: string) => lineage.versions.find((v) => v.id === id)?.version_label ?? id;

  return (
    <div className="space-y-0">
      {lineage.versions.map((v, idx) => {
        const tr = transitionByTo.get(v.id);
        return (
          <div key={v.id}>
            {tr && (
              <div className="my-4 flex items-center gap-2 ps-6 text-sm text-neutral-600">
                <span className="text-lg leading-none" aria-hidden>
                  ↓
                </span>
                <span>
                  {t(transitionReasonKey(tr.reason) as TKey) !== transitionReasonKey(tr.reason)
                    ? t(transitionReasonKey(tr.reason) as TKey)
                    : tr.reason.replace(/_/g, " ")}
                </span>
              </div>
            )}
            <VersionNode
              v={v}
              expanded={!!expanded[v.id]}
              onToggle={() => setExpanded((s) => ({ ...s, [v.id]: !s[v.id] }))}
              onEventClick={setDrawerEvent}
              highlightEventId={highlightEventId}
            />
            {idx < lineage.versions.length - 1 && <div className="ms-3 h-6 w-px bg-neutral-200" aria-hidden />}
          </div>
        );
      })}
      <EventDetailDrawer
        contractId={contractId}
        event={drawerEvent}
        versionLabel={drawerEvent ? versionLabel(drawerEvent.version_id) : undefined}
        open={!!drawerEvent}
        onClose={() => setDrawerEvent(null)}
      />
    </div>
  );
}
