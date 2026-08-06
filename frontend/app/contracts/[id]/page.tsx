"use client";
// F1 money screen. Two panes:
//  - data pane (first in DOM = RIGHT in RTL): header cards + obligations +
//    extracted notice periods + F2 timeline tab + F3 payment tracker
//  - source viewer (LEFT): raw page text with the exact quote highlighted.
// Every extracted value either opens its highlighted source (verified quote)
// or shows a "source unverified" badge — never a wrong highlight.
import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";

import ConfidenceChip from "@/components/ConfidenceChip";
import DeadlineTimeline from "@/components/DeadlineTimeline";
import DemoClockControl from "@/components/DemoClockControl";
import DualDate from "@/components/DualDate";
import LogEventDialog from "@/components/LogEventDialog";
import PaymentTracker from "@/components/PaymentTracker";
import StatusChip from "@/components/StatusChip";
import TypeBadge from "@/components/TypeBadge";
import ContractHeader from "@/components/contract/ContractHeader";
import AiSummaryPanel from "@/components/contract/AiSummaryPanel";
import WorkflowStepper from "@/components/contract/WorkflowStepper";
import ReviewHistoryPanel from "@/components/ReviewHistoryPanel";
import SendForReviewDialog from "@/components/SendForReviewDialog";
import { useShell } from "@/components/shell/ShellContext";
import UnsupportedContractWarning from "@/components/UnsupportedContractWarning";
import RefreshingDot from "@/components/ui/RefreshingDot";
import { SkeletonCard } from "@/components/ui/Skeleton";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import { TabList, TabPanel, Tabs, TabTrigger } from "@/components/ui/Tabs";
import Timeline from "@/components/ui/Timeline";
import RiskScoreRing from "@/components/ui/RiskScoreRing";
import StageBadge from "@/components/ui/StageBadge";
import { api, apiJson, fetchActivity, fetchDeadlines, fetchVersions, getDemoToday, rebuildContractIntelligence } from "@/lib/api";
import { mapActivityEvents } from "@/lib/activity";
import { invalidateContract, useCachedFetch } from "@/lib/cache";
import { useI18n, type TKey } from "@/lib/i18n";
import type {
  ClauseSource,
  ContractDetail,
  NoticePeriodItem,
  ObligationRow,
  SourceTarget,
  DeadlineRow,
} from "@/lib/types";
import { cn, formatDate, formatNum, formatSAR } from "@/lib/utils";

type Tab =
  | "overview"
  | "aiSummary"
  | "clauses"
  | "risk"
  | "documents"
  | "obligations"
  | "notice"
  | "deadlines"
  | "milestones"
  | "review"
  | "negotiation"
  | "approvals"
  | "signature"
  | "versions"
  | "activity";

const VALID_DETAIL_TABS = new Set<Tab>([
  "overview",
  "aiSummary",
  "clauses",
  "risk",
  "documents",
  "obligations",
  "notice",
  "deadlines",
  "milestones",
  "review",
  "negotiation",
  "approvals",
  "signature",
  "versions",
  "activity",
]);

const panelLoading = () => <SkeletonCard rows={3} />;

const SourceViewer = dynamic(() => import("@/components/SourceViewer"), { ssr: false, loading: panelLoading });
const NegotiationPanel = dynamic(() => import("@/components/NegotiationPanel"), { ssr: false, loading: panelLoading });
const NegotiationOpportunitiesPanel = dynamic(() => import("@/components/NegotiationOpportunitiesPanel"), {
  ssr: false,
  loading: panelLoading,
});
const ApprovalsPanel = dynamic(() => import("@/components/ApprovalsPanel"), { ssr: false, loading: panelLoading });
const SignaturePanel = dynamic(() => import("@/components/SignaturePanel"), { ssr: false, loading: panelLoading });
const VersionsPanel = dynamic(() => import("@/components/VersionsPanel"), { ssr: false, loading: panelLoading });

export default function ContractDetailPage() {
  const { t, lang } = useI18n();
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const id = params.id;
  const highlightReview = searchParams.get("review");
  const highlightNegotiation = searchParams.get("item");
  const highlightWorkflow = searchParams.get("workflow");
  const highlightSignature = searchParams.get("request");

  const [detail, setDetail] = useState<ContractDetail | null>(null);
  const [obligations, setObligations] = useState<ObligationRow[]>([]);
  const {
    data: cachedDetail,
    isLoading: detailLoading,
    isValidating: detailValidating,
    error: detailError,
    refresh: refreshDetail,
  } = useCachedFetch(`contract:${id}`, () => api<ContractDetail>(`/api/contracts/${id}`));
  const { data: cachedObligations, refresh: refreshObligations } = useCachedFetch(
    `obligations:${id}`,
    () => api<ObligationRow[]>(`/api/contracts/${id}/obligations`)
  );
  const { data: noticeDeadlines } = useCachedFetch(`notice-deadlines:${id}`, () =>
    fetchDeadlines(id).then((r) => r.deadlines)
  );

  useEffect(() => {
    if (cachedDetail) setDetail(cachedDetail);
  }, [cachedDetail]);
  useEffect(() => {
    if (cachedObligations) setObligations(cachedObligations);
  }, [cachedObligations]);

  const [target, setTarget] = useState<SourceTarget | null>(null);
  const { setPageTitle } = useShell();
  const [tab, setTab] = useState<Tab>("overview");
  const [error, setError] = useState(false);
  const load = useCallback(() => {
    setError(false);
    refreshDetail();
    refreshObligations();
  }, [refreshDetail, refreshObligations]);

  useEffect(() => {
    if (detailError) setError(true);
  }, [detailError]);

  useEffect(() => {
    const tabParam = searchParams.get("tab");
    if (tabParam && VALID_DETAIL_TABS.has(tabParam as Tab)) {
      setTab(tabParam as Tab);
    }
  }, [searchParams]);

  const [demoToday, setDemoToday] = useState("");
  const [timelineRefresh, setTimelineRefresh] = useState(0);

  useEffect(() => {
    if (detail?.title) setPageTitle(detail.title);
    return () => setPageTitle(null);
  }, [detail?.title, setPageTitle]);

  useEffect(() => {
    getDemoToday()
      .then((r) => setDemoToday(r.today))
      .catch(() => {});
  }, []);

  const extraction = (field: string) => detail?.extractions.find((e) => e.field_name === field);
  const notices: NoticePeriodItem[] = (extraction("notice_periods")?.value_json as NoticePeriodItem[]) ?? [];

  const jump = (
    src: ClauseSource | { page: number; char_start: number | null; char_end: number | null; quote?: string } | null
  ) => {
    if (!src?.page) return;
    setTab("clauses");
    if (src.char_start != null && src.char_end != null)
      setTarget({
        page: src.page,
        char_start: src.char_start,
        char_end: src.char_end,
        quote: "quote" in src ? src.quote : undefined,
      });
    else if ("quote" in src && src.quote)
      setTarget({ page: src.page, char_start: 0, char_end: 0, quote: src.quote });
  };

  const toggleObligation = async (o: ObligationRow) => {
    const next = o.status === "done" ? "pending" : "done";
    setObligations((rows) => rows.map((r) => (r.id === o.id ? { ...r, status: next } : r)));
    try {
      await apiJson(`/api/obligations/${o.id}`, "PATCH", { status: next });
      invalidateContract(id);
    } catch {
      load();
    }
  };

  if (error)
    return (
      <Card>
        <CardBody className="text-center">
          <p className="mb-3 text-danger-600">{t("common.error")}</p>
          <Button variant="secondary" onClick={load}>
            {t("common.retry")}
          </Button>
        </CardBody>
      </Card>
    );
  if (!detail && detailLoading) return <p className="p-8 text-center text-gray-400">{t("common.loading")}</p>;
  if (!detail) return <p className="p-8 text-center text-gray-400">{t("common.loading")}</p>;

  if (detail.supported === false) {
    return (
      <UnsupportedContractWarning
        category={detail.contract_category ?? "Unknown"}
        message={detail.classification_message ?? undefined}
        confidence={detail.classification_confidence ?? undefined}
      />
    );
  }

  const SourceButton = ({ src }: { src: ClauseSource | null }) =>
    src ? (
      <button
        onClick={() => jump(src)}
        className="inline-flex items-center rounded-md bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700 hover:bg-brand-100"
        title={src.quote}
      >
        {t("detail.clause")} {src.clause_ref ?? "؟"}
      </button>
    ) : (
      <span className="inline-flex items-center rounded-md bg-gray-100 px-2 py-0.5 text-xs text-gray-500">
        {t("detail.sourceUnverified")}
      </span>
    );

  const card = (title: string, body: React.ReactNode, field?: string) => {
    const e = field ? extraction(field) : undefined;
    return (
      <Card className="p-5">
        <div className="mb-1 flex items-center justify-between gap-2">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500">{title}</h3>
          <div className="flex items-center gap-1.5">
            {e && <ConfidenceChip confidence={e.confidence} />}
            {e?.clause && <SourceButton src={e.clause} />}
          </div>
        </div>
        <div className="text-sm font-semibold text-gray-800">{body}</div>
      </Card>
    );
  };

  const riskScore = detail?.risk?.score ?? 0;
  const riskBreakdown = detail?.risk?.breakdown ?? [];

  const noticeDeadlineByPurpose = (() => {
    const map = new Map<string, DeadlineRow>();
    for (const d of noticeDeadlines ?? []) {
      if (d.title) map.set(d.title.toLowerCase(), d);
    }
    return map;
  })();

  const tabs: { key: Tab; label: TKey }[] = [
    { key: "overview", label: "detail.tab.overview" },
    { key: "clauses", label: "detail.tab.document" },
    { key: "aiSummary", label: "detail.tab.aiSummary" },
    { key: "risk", label: "detail.tab.risk" },
    { key: "obligations", label: "detail.tab.obligations" },
    { key: "notice", label: "detail.tab.notice" },
    { key: "deadlines", label: "detail.tab.deadlines" },
    { key: "milestones", label: "detail.tab.milestones" },
    { key: "review", label: "review.tab" },
    { key: "negotiation", label: "negotiation.tab" },
    { key: "approvals", label: "approval.tab" },
    { key: "signature", label: "signature.tab" },
    { key: "versions", label: "versions.tab" },
    { key: "documents", label: "detail.tab.documents" },
    { key: "activity", label: "detail.tab.activity" },
  ];

  return (
    <div className="space-y-6 motion-safe:animate-fadeIn">
      {detailValidating && (
        <div className="flex justify-end">
          <RefreshingDot />
        </div>
      )}
      <ContractHeader
        detail={detail}
        contractId={id}
        onStartApproval={() => setTab("approvals")}
        onCreateSignature={() => setTab("signature")}
      />
      <div className="surface-panel grid gap-4 p-4 md:grid-cols-4">
        <div>
          <p className="text-eyebrow">{t("versions.col.version")}</p>
          <p className="text-lg font-bold">
            {formatNum(detail.current_version_number ?? 1, lang)}/{formatNum(detail.total_versions ?? 1, lang)}
          </p>
        </div>
        <div>
          <p className="text-eyebrow">{t("list.col.stage")}</p>
          <StageBadge stage={detail.stage} />
        </div>
        <div>
          <p className="text-eyebrow">{t("detail.value")}</p>
          <p className="text-lg font-bold">{formatSAR(detail.value_sar, lang)}</p>
        </div>
        <div className="flex justify-center md:justify-end">
          <RiskScoreRing score={riskScore} label={t("detail.tab.risk")} />
        </div>
      </div>
      <Card className="surface-card border-0 p-4">
        <WorkflowStepper stage={detail.stage} />
      </Card>
      <Card className="overflow-hidden p-4 md:p-6">
        <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
          <TabList className="overflow-x-auto">
            {tabs.map(({ key, label }) => (
              <TabTrigger key={key} value={key}>
                {t(label)}
              </TabTrigger>
            ))}
          </TabList>

          <TabPanel value="overview">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {card(
                t("detail.parties"),
                <div className="space-y-1">
                  <p>
                    <span className="text-gray-500">{t("detail.partyA")}: </span>
                    {detail.party_a ?? "—"}
                  </p>
                  <p>
                    <span className="text-gray-500">{t("detail.partyB")}: </span>
                    {detail.party_b ?? "—"}
                  </p>
                </div>,
                "party_a"
              )}
              {card(t("detail.value"), formatSAR(detail.value_sar, lang), "value_sar")}
              {card(
                t("detail.duration"),
                <div className="space-y-1">
                  <p>
                    <span className="text-gray-500">{t("detail.from")}: </span>
                    <DualDate date={detail.start_date} />
                  </p>
                  <p>
                    <span className="text-gray-500">{t("detail.to")}: </span>
                    <DualDate date={detail.end_date} />
                  </p>
                </div>,
                "start_date"
              )}
              {card(t("detail.law"), detail.governing_law ?? "—", "governing_law")}
              <Card className="p-5 sm:col-span-2">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500">{t("detail.tab.obligations")}</h3>
                <p className="mt-2 text-2xl font-bold text-gray-900">{obligations.length}</p>
              </Card>
            </div>
          </TabPanel>

          <TabPanel value="aiSummary">
            <AiSummaryPanel
              contractId={id}
              initialStatus={detail.summary_status}
              isStale={detail.summary_is_stale}
              onCitation={(t) => jump(t)}
            />
          </TabPanel>

          <TabPanel value="clauses">
            <div className="h-[min(70vh,720px)] min-w-0">
              <SourceViewer contractId={id} target={target} />
            </div>
          </TabPanel>

          <TabPanel value="obligations">
                <div className="max-h-[420px] overflow-auto">
                  {obligations.length === 0 && <p className="py-6 text-center text-sm text-gray-400">{t("common.empty")}</p>}
                  {obligations.length > 0 && (
                    <table className="w-full text-sm">
                      <thead className="sticky top-0 z-10 bg-white text-gray-500 shadow-sm">
                        <tr>
                          <th className="px-3 py-3 text-start font-semibold">{t("obligation.desc")}</th>
                          <th className="px-3 py-3 text-start font-semibold">{t("obligation.party")}</th>
                          <th className="px-3 py-3 text-start font-semibold">{t("obligation.due")}</th>
                          <th className="px-3 py-3 text-start font-semibold">{t("obligation.penalty")}</th>
                          <th className="px-3 py-3 text-start font-semibold">{t("obligation.status")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {obligations.map((o) => (
                          <tr key={o.id} className="border-t align-top hover:bg-muted-50/50">
                            <td className="px-3 py-3.5">
                              <p>{o.description}</p>
                              <div className="mt-1 flex items-center gap-1.5">
                                <SourceButton src={o.source} />
                                {o.confidence != null && <ConfidenceChip confidence={o.confidence} />}
                              </div>
                            </td>
                            <td className="px-3 py-3.5 text-gray-600">{o.responsible_party ?? "—"}</td>
                            <td className="px-3 py-3.5">{o.due_date ? <DualDate date={o.due_date} /> : <span className="text-gray-400">{t("obligation.noDue")}</span>}</td>
                            <td className="px-3 py-3.5 text-gray-600">{o.penalty_text ?? "—"}</td>
                            <td className="px-3 py-3.5">
                              <button
                                onClick={() => toggleObligation(o)}
                                className="rounded-full focus-visible:focus-ring"
                              >
                                <Badge
                                  tone={o.status === "done" ? "success" : o.status === "overdue" ? "danger" : "neutral"}
                                >
                                  {t(`obligation.${o.status}` as TKey)}
                                </Badge>
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
          </TabPanel>

          <TabPanel value="notice">
                <div>
                  <div className="mb-3 flex items-center justify-between">
                    <h3 className="text-sm font-semibold">{t("detail.noticeTitle")}</h3>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() =>
                        rebuildContractIntelligence(id).then(() => {
                          invalidateContract(id);
                          load();
                        })
                      }
                    >
                      {t("intelligence.rebuild")}
                    </Button>
                  </div>
                  {notices.length === 0 && <p className="py-6 text-center text-sm text-gray-400">{t("common.empty")}</p>}
                  <ul className="space-y-2">
                    {notices.map((n, i) => {
                      const resolved = noticeDeadlineByPurpose.get((n.purpose || "").toLowerCase());
                      return (
                      <li key={i} className="rounded-lg border p-3">
                        <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-medium">{n.purpose}</p>
                          <p className="text-xs text-gray-500">
                            {t("notice.days")}: {n.days} {t("common.days")}
                          </p>
                          {resolved?.responsible_party && (
                            <p className="text-xs text-gray-500">
                              {t("deadline.responsibleParty")}: {resolved.responsible_party}
                            </p>
                          )}
                          {resolved?.calculation_explanation && (
                            <p className="mt-1 text-xs text-gray-600">{resolved.calculation_explanation}</p>
                          )}
                          {resolved?.computed_date && (
                            <p className="mt-1 text-xs font-medium text-gray-800">
                              {t("detail.noticeResolved")}: <DualDate date={resolved.computed_date} />
                            </p>
                          )}
                          {resolved?.status === "inactive" && (
                            <p className="mt-1 text-xs text-amber-700">{t("detail.noticeAwaitingTrigger")}</p>
                          )}
                          {resolved?.needs_review && (
                            <p className="mt-1 text-xs text-amber-700">{t("detail.noticeRequiresReview")}</p>
                          )}
                        </div>
                        <div className="flex items-center gap-1.5">
                          {resolved?.status && (
                            <Badge tone={resolved.status === "inactive" ? "neutral" : "info"}>
                              {t(`deadline.status.${resolved.status}` as TKey)}
                            </Badge>
                          )}
                          <ConfidenceChip confidence={n.confidence} />
                          {n.verified && n.char_start != null ? (
                            <button
                              onClick={() => jump(n)}
                              className="rounded-md bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700 hover:bg-brand-100"
                            >
                              {t("detail.clause")} {n.clause_ref ?? "؟"}
                            </button>
                          ) : (
                            <span className="rounded-md bg-gray-100 px-2 py-0.5 text-xs text-gray-500">{t("detail.sourceUnverified")}</span>
                          )}
                        </div>
                        </div>
                      </li>
                    );})}
                  </ul>
                </div>
          </TabPanel>

          <TabPanel value="deadlines">
                <div>
                  <DemoClockControl onChange={setDemoToday} />
                  {demoToday && (
                    <>
                      <LogEventDialog
                        contractId={id}
                        demoToday={demoToday}
                        onLogged={() => setTimelineRefresh((k) => k + 1)}
                      />
                      <DeadlineTimeline
                        contractId={id}
                        demoToday={demoToday}
                        contractStatus={detail.status}
                        refreshKey={timelineRefresh}
                        onSourceClick={setTarget}
                      />
                    </>
                  )}
                </div>
          </TabPanel>

          <TabPanel value="milestones">
            {demoToday ? (
                <PaymentTracker
                  contractId={id}
                  demoToday={demoToday}
                  contractStatus={detail.status}
                  refreshKey={timelineRefresh}
                  onSourceClick={setTarget}
                />
            ) : (
              <p className="text-sm text-gray-500">{t("common.loading")}</p>
            )}
          </TabPanel>

          <TabPanel value="review">
                <div>
                  <h3 className="mb-3 text-sm font-semibold">{t("review.history")}</h3>
                  <ReviewHistoryPanel contractId={id} highlightId={highlightReview} contractStage={detail.stage} />
                </div>
          </TabPanel>

          <TabPanel value="negotiation">
            <NegotiationOpportunitiesPanel contractId={id} />
            <NegotiationPanel
              contractId={id}
              contractStage={detail.stage}
              highlightId={highlightNegotiation}
              onLifecycleChanged={load}
              onGoToApproval={() => setTab("approvals")}
            />
          </TabPanel>

          <TabPanel value="approvals">
            <ApprovalsPanel
              contractId={id}
              contractStage={detail.stage}
              highlightId={highlightWorkflow}
              onLifecycleChange={load}
              onGoToNegotiation={() => setTab("negotiation")}
            />
          </TabPanel>

          <TabPanel value="signature">
            <SignaturePanel
              contractId={id}
              contractStage={detail.stage}
              highlightId={highlightSignature}
              onLifecycleChange={load}
            />
          </TabPanel>

          <TabPanel value="versions">
            <VersionsPanel contractId={id} />
          </TabPanel>

          <TabPanel value="risk">
            <div className="flex flex-col items-center gap-6 py-6 md:flex-row md:items-start">
              <RiskScoreRing score={riskScore} size={120} label={t("detail.tab.risk")} />
              <div className="flex-1 space-y-3 text-sm">
                <h4 className="font-semibold text-gray-800">{t("detail.riskWhy")}</h4>
                {riskBreakdown.length === 0 && (
                  <p className="text-hint">{t("detail.riskEmpty")}</p>
                )}
                <ul className="space-y-2">
                  {riskBreakdown.map((b) => (
                    <li key={b.category} className="surface-card p-3">
                      <p className="font-medium text-gray-900">
                        {b.category} · +{b.points}
                      </p>
                      <p className="text-xs text-gray-600">{b.explanation}</p>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </TabPanel>

          <TabPanel value="documents">
            <ContractDocumentsTab contractId={id} />
          </TabPanel>

          <TabPanel value="activity">
            <ContractActivityTab contractId={id} />
          </TabPanel>
        </Tabs>
      </Card>
    </div>
  );
}

function ContractActivityTab({ contractId }: { contractId: string }) {
  const { t, lang } = useI18n();
  const { data, isLoading } = useCachedFetch(`activity:${contractId}`, () =>
    fetchActivity(contractId).then((r) => r.events ?? [])
  );
  const items = useMemo(
    () => mapActivityEvents(data ?? [], t),
    [data, t]
  );

  if (isLoading && !data) return <p className="text-sm text-gray-500">{t("common.loading")}</p>;
  if (!data?.length) return <EmptyState title={t("common.empty")} />;

  return <Timeline items={items} />;
}

const ContractDocumentsTab = dynamic(
  () =>
    Promise.resolve(function ContractDocumentsTabInner({ contractId }: { contractId: string }) {
      const { t, lang } = useI18n();
      const [versions, setVersions] = useState<import("@/lib/types").ContractVersionRow[]>([]);

      useEffect(() => {
        fetchVersions(contractId)
          .then((r) => setVersions(r.versions))
          .catch(() => setVersions([]));
      }, [contractId]);

      if (versions.length === 0) return <EmptyState title={t("common.empty")} />;

      return (
        <ul className="divide-y divide-neutral-100">
          {versions.map((v) => (
            <li key={v.id} className="flex items-center justify-between py-3">
              <span className="font-medium">{v.version_label}</span>
              <span className="text-sm text-neutral-500">{formatDate(v.created_at, lang)}</span>
            </li>
          ))}
        </ul>
      );
    }),
  { ssr: false, loading: panelLoading }
);
