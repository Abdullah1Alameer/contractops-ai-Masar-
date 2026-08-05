"use client";
import { useCallback, useEffect, useMemo, useState } from "react";

import DemoStoryPlayer from "@/components/contract/DemoStoryPlayer";
import VersionLineage from "@/components/contract/VersionLineage";
import VersionLifecycleTimeline from "@/components/contract/VersionLifecycleTimeline";
import CreateVersionDialog from "@/components/CreateVersionDialog";
import { useConfirm } from "@/components/feedback/ConfirmDialog";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Drawer from "@/components/ui/Drawer";
import EmptyState from "@/components/ui/EmptyState";
import RiskScoreRing from "@/components/ui/RiskScoreRing";
import SectionHeader from "@/components/ui/SectionHeader";
import { SkeletonCard } from "@/components/ui/Skeleton";
import StageBadge from "@/components/ui/StageBadge";
import { TabList, TabPanel, TabTrigger, Tabs } from "@/components/ui/Tabs";
import {
  compareVersions,
  downloadVersionBlob,
  fetchActivity,
  fetchVersionLineage,
  fetchVersions,
  setCurrentVersion,
  uploadNewVersion,
} from "@/lib/api";
import { useI18n, type TKey } from "@/lib/i18n";
import type {
  ActivityEventRow,
  ContractVersionRow,
  VersionCompareChangeSection,
  VersionCompareResult,
  VersionCompareRich,
  VersionLineageResponse,
} from "@/lib/types";
import { cn } from "@/lib/utils";

function WfPill({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <span className="pill text-[11px]">
      <span className="text-neutral-500">{label}</span>
      <span className="font-semibold text-neutral-800">{value ?? "—"}</span>
    </span>
  );
}

function ChangeSection({ title, section }: { title: string; section: VersionCompareChangeSection | undefined }) {
  if (!section?.summary && !(section?.items?.length ?? 0)) return null;
  return (
    <div className="surface-card p-3">
      <h4 className="text-sm font-semibold text-neutral-900">{title}</h4>
      <p className="mt-1 text-sm text-neutral-700">{section?.summary}</p>
      {section?.items?.length ? (
        <ul className="mt-2 list-disc space-y-1 ps-4 text-sm text-neutral-600">
          {section.items.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function CompareAiView({ rich }: { rich: VersionCompareRich }) {
  const { t } = useI18n();
  const sections: { key: TKey; data: VersionCompareChangeSection | undefined }[] = [
    { key: "versions.compare.risk", data: rich.risk_changes },
    { key: "versions.compare.financial", data: rich.financial_changes },
    { key: "versions.compare.legal", data: rich.legal_changes },
    { key: "versions.compare.liability", data: rich.liability_changes },
    { key: "versions.compare.termination", data: rich.termination_changes },
    { key: "versions.compare.confidentiality", data: rich.confidentiality_changes },
    { key: "versions.compare.timeline", data: rich.timeline_changes },
    { key: "versions.compare.payment", data: rich.payment_changes },
  ];

  return (
    <div className="space-y-4">
      <p className="text-sm text-neutral-800">{rich.executive_summary}</p>
      <div className="flex flex-wrap items-center gap-6">
        <RiskScoreRing score={rich.overall_risk_score} label={t("versions.compare.riskScore")} size={88} />
        <div className="flex-1">
          <p className="text-eyebrow">{t("versions.compare.recommendation")}</p>
          <p className="mt-1 text-sm text-neutral-800">{rich.recommendation}</p>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {sections.map(({ key, data }) => (
          <ChangeSection key={key} title={t(key)} section={data} />
        ))}
      </div>
      <div className="grid gap-3 lg:grid-cols-3">
        <ClauseList title={t("versions.compare.added")} items={rich.added_clauses} tone="success" />
        <ClauseList title={t("versions.compare.removed")} items={rich.removed_clauses} tone="danger" />
        <ClauseList title={t("versions.compare.modified")} items={rich.modified_clauses} tone="warning" />
      </div>
    </div>
  );
}

function ClauseList({
  title,
  items,
  tone,
}: {
  title: string;
  items: { clause_ref: string; note: string }[];
  tone: "success" | "danger" | "warning";
}) {
  const border =
    tone === "success" ? "border-success-200/80" : tone === "danger" ? "border-danger-200/80" : "border-warning-200/80";
  if (!items?.length) {
    return (
      <div className={cn("rounded-card border p-3", border)}>
        <h4 className="text-sm font-semibold">{title}</h4>
        <p className="mt-2 text-xs text-neutral-500">—</p>
      </div>
    );
  }
  return (
    <div className={cn("rounded-card border p-3", border)}>
      <h4 className="text-sm font-semibold">{title}</h4>
      <ul className="mt-2 space-y-2">
        {items.map((c, i) => (
          <li key={i} className="text-xs">
            <span className="font-semibold text-neutral-900">{c.clause_ref}</span>
            <p className="text-neutral-600">{c.note}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

function CompareSplitView({ result }: { result: VersionCompareResult }) {
  const { t } = useI18n();
  const left = result.from_extracted_json ?? {};
  const right = result.to_extracted_json ?? {};
  const added = new Set(result.diff.added_fields ?? []);
  const removed = new Set(result.diff.removed_fields ?? []);
  const modified = new Set(result.diff.modified_fields ?? []);
  const rich = result.diff.rich;
  const noteByField = useMemo(() => {
    const m = new Map<string, string>();
    for (const c of rich?.modified_clauses ?? []) {
      m.set(c.clause_ref, c.note);
    }
    return m;
  }, [rich]);

  const keys = useMemo(() => {
    return Array.from(new Set([...Object.keys(left), ...Object.keys(right)])).sort();
  }, [left, right]);

  const fromLabel = result.from_version_number != null ? `v${result.from_version_number}` : t("versions.compare.from");
  const toLabel = result.to_version_number != null ? `v${result.to_version_number}` : t("versions.compare.to");

  return (
    <div className="space-y-3">
      <div className="grid gap-3 lg:grid-cols-2">
        <div>
          <p className="mb-2 text-sm font-bold text-neutral-800">{fromLabel}</p>
          <div className="max-h-96 space-y-2 overflow-auto rounded-lg border bg-neutral-50/80 p-3">
            {keys.map((k) => {
              const inLeft = k in left;
              const tone = removed.has(k) ? "bg-danger-50 border-danger-200" : modified.has(k) ? "bg-warning-50 border-warning-200" : "border-neutral-200 bg-white";
              if (!inLeft && added.has(k)) return null;
              return (
                <FieldRow key={k} name={k} value={left[k]} className={tone} note={modified.has(k) ? noteByField.get(k) : undefined} />
              );
            })}
          </div>
        </div>
        <div>
          <p className="mb-2 text-sm font-bold text-neutral-800">{toLabel}</p>
          <div className="max-h-96 space-y-2 overflow-auto rounded-lg border bg-neutral-50/80 p-3">
            {keys.map((k) => {
              const inRight = k in right;
              const tone = added.has(k) ? "bg-success-50 border-success-200" : modified.has(k) ? "bg-warning-50 border-warning-200" : "border-neutral-200 bg-white";
              if (!inRight && removed.has(k)) return null;
              return (
                <FieldRow key={k} name={k} value={right[k]} className={tone} note={modified.has(k) ? noteByField.get(k) : undefined} />
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

function FieldRow({ name, value, className, note }: { name: string; value: unknown; className: string; note?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={cn("rounded border p-2 text-xs", className)}>
      <p className="font-semibold text-neutral-800">{name}</p>
      <pre className="mt-1 whitespace-pre-wrap text-neutral-600">{JSON.stringify(value, null, 2)}</pre>
      {note && (
        <>
          <button type="button" className="link-strong mt-1 text-xs" onClick={() => setOpen((o) => !o)}>
            AI
          </button>
          {open && <p className="mt-1 text-neutral-700">{note}</p>}
        </>
      )}
    </div>
  );
}

export default function VersionsPanel({ contractId }: { contractId: string }) {
  const { t } = useI18n();
  const { confirm } = useConfirm();
  const [loading, setLoading] = useState(true);
  const [rows, setRows] = useState<ContractVersionRow[]>([]);
  const [activity, setActivity] = useState<ActivityEventRow[]>([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [compareOpen, setCompareOpen] = useState(false);
  const [compareFrom, setCompareFrom] = useState<string | null>(null);
  const [compareTo, setCompareTo] = useState<string | null>(null);
  const [compareResult, setCompareResult] = useState<VersionCompareResult | null>(null);
  const [compareTab, setCompareTab] = useState<"ai" | "split">("ai");
  const [busy, setBusy] = useState(false);
  const [viewMode, setViewMode] = useState<"lineage" | "cards">("lineage");
  const [lineage, setLineage] = useState<VersionLineageResponse | null>(null);
  const [storyHighlight, setStoryHighlight] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([fetchVersions(contractId), fetchActivity(contractId), fetchVersionLineage(contractId)])
      .then(([v, act, lin]) => {
        setRows(v.versions);
        setActivity(act.events ?? []);
        setLineage(lin);
      })
      .catch(() => {
        setRows([]);
        setActivity([]);
      })
      .finally(() => setLoading(false));
  }, [contractId]);

  useEffect(load, [load]);

  const runCompare = async () => {
    if (!compareFrom || !compareTo) return;
    setBusy(true);
    try {
      setCompareResult(await compareVersions(contractId, compareFrom, compareTo));
      setCompareTab("ai");
    } finally {
      setBusy(false);
    }
  };

  const restore = (v: ContractVersionRow) => {
    const signedWarn = v.is_signed ? `\n\n${t("versions.restoreSignedWarn")}` : "";
    confirm({
      title: t("versions.restore"),
      body: `${v.version_label}${signedWarn}`,
      confirmLabel: t("versions.setCurrent"),
      onConfirm: async () => {
        await setCurrentVersion(v.id, contractId);
        load();
      },
    });
  };

  if (loading) return <SkeletonCard rows={4} />;
  if (rows.length === 0)
    return <EmptyState title={t("versions.empty")} actionLabel={t("versions.createNew")} onAction={() => setCreateOpen(true)} />;

  const rich = compareResult?.diff?.rich;

  return (
    <div className="space-y-6">
      <SectionHeader
        title={t("versions.lineageTitle")}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {lineage && <DemoStoryPlayer contractId={contractId} lineage={lineage} onHighlight={setStoryHighlight} />}
            <Button variant="primary" size="sm" onClick={() => setCreateOpen(true)}>
              {t("versions.createNew")}
            </Button>
          </div>
        }
      />

      <Tabs value={viewMode} onValueChange={(v) => setViewMode(v as "lineage" | "cards")}>
        <TabList>
          <TabTrigger value="lineage">{t("versions.view.lineage")}</TabTrigger>
          <TabTrigger value="cards">{t("versions.view.cards")}</TabTrigger>
        </TabList>
        <TabPanel value="lineage">
          {lineage ? (
            <VersionLineage contractId={contractId} lineage={lineage} highlightEventId={storyHighlight} />
          ) : (
            <SkeletonCard rows={3} />
          )}
        </TabPanel>
        <TabPanel value="cards">
          <VersionLifecycleTimeline versions={rows} activity={activity} />
          <ul className="mt-6 space-y-3">
        {rows.map((v) => (
          <li key={v.id} className={cn("surface-card p-4", v.is_current && "ring-2 ring-brand-600/20")}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-lg font-bold text-neutral-900">{v.version_label}</span>
                  {v.is_current && <Badge tone="success">{t("versions.current")}</Badge>}
                  <StageBadge stage={v.status} />
                </div>
                <p className="mt-1 text-sm text-neutral-600">
                  {t("versions.audit.uploadedBy")}: {v.created_by ?? "—"} · {v.created_at?.slice(0, 10) ?? "—"}
                </p>
                {v.restored_by && (
                  <p className="text-sm text-neutral-600">
                    {t("versions.audit.restoredBy")}: {v.restored_by} · {v.restored_at?.slice(0, 10) ?? "—"}
                  </p>
                )}
                <div className="mt-2 flex flex-wrap gap-2">
                  <WfPill label={t("review.tab")} value={v.review_status} />
                  <WfPill label={t("negotiation.tab")} value={v.negotiation_status} />
                  <WfPill label={t("approval.tab")} value={v.approval_status} />
                  <WfPill label={t("signature.tab")} value={v.signature_status} />
                </div>
                {(v.workflow_stale_count ?? 0) > 0 && (
                  <p className="mt-2 text-sm text-warning-800">{t("versions.staleWarning")}</p>
                )}
                <p className="mt-2 text-xs text-neutral-500">
                  {t("versions.lastActivity")}: {v.last_activity_at?.slice(0, 16) ?? "—"} · {v.event_count ?? 0} events
                </p>
                {v.risk_score != null ? (
                  <div className="mt-2">
                    <RiskScoreRing score={v.risk_score} size={56} label={t("versions.riskScore")} />
                  </div>
                ) : (
                  <p className="mt-2 text-xs text-neutral-500">{t("versions.riskNotCalculated")}</p>
                )}
                {v.change_summary && (
                  <p className="mt-2 text-sm text-neutral-700">
                    {t("versions.reason")}: {v.change_summary}
                  </p>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={async () => {
                    const blob = await downloadVersionBlob(v.id);
                    window.open(URL.createObjectURL(blob), "_blank");
                  }}
                >
                  {t("versions.open")}
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    setViewMode("lineage");
                    setStoryHighlight(null);
                  }}
                >
                  {t("versions.viewAudit")}
                </Button>
                {!v.is_current && (
                  <Button variant="secondary" size="sm" onClick={() => restore(v)}>
                    {t("versions.restore")}
                  </Button>
                )}
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    setCompareFrom(v.id);
                    setCompareTo(null);
                    setCompareResult(null);
                    setCompareOpen(true);
                  }}
                >
                  {t("versions.comparePick")}
                </Button>
              </div>
            </div>
          </li>
        ))}
          </ul>
        </TabPanel>
      </Tabs>

      <Drawer open={compareOpen} onClose={() => setCompareOpen(false)} title={t("versions.compareTitle")} size="lg">
        <p className="mb-3 text-hint">{t("versions.compareHint")}</p>
        <select className="mb-2 w-full rounded-lg border px-3 py-2 text-sm" value={compareTo ?? ""} onChange={(e) => setCompareTo(e.target.value)}>
          <option value="">{t("versions.compareTo")}</option>
          {rows
            .filter((v) => v.id !== compareFrom)
            .map((v) => (
              <option key={v.id} value={v.id}>
                {v.version_label}
              </option>
            ))}
        </select>
        <Button variant="primary" size="sm" loading={busy} onClick={runCompare}>
          {t("versions.runCompare")}
        </Button>
        {compareResult && (
          <div className="mt-6">
            <Tabs value={compareTab} onValueChange={(v) => setCompareTab(v as "ai" | "split")}>
              <TabList>
                <TabTrigger value="ai">{t("versions.compare.aiView")}</TabTrigger>
                <TabTrigger value="split">{t("versions.compare.splitView")}</TabTrigger>
              </TabList>
              <TabPanel value="ai">
              {rich ? (
                <CompareAiView rich={rich} />
              ) : (
                <p className="mt-4 text-sm text-neutral-700">{compareResult.ai_explanation}</p>
              )}
            </TabPanel>
            <TabPanel value="split">
              <CompareSplitView result={compareResult} />
            </TabPanel>
            </Tabs>
          </div>
        )}
      </Drawer>

      <CreateVersionDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onSubmit={async (file, source, summary) => {
          await uploadNewVersion(contractId, file, source, summary);
          setCreateOpen(false);
          load();
        }}
      />
    </div>
  );
}
