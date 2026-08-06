"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";

import { ReviewStatusBadge } from "@/components/SendForReviewDialog";
import Logo from "@/components/Logo";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import RiskScoreRing from "@/components/ui/RiskScoreRing";
import DualDate from "@/components/DualDate";
import { useConfirm } from "@/components/feedback/ConfirmDialog";
import { useToast } from "@/components/feedback/ToastProvider";
import {
  apiErrorCode,
  fetchReviewDocumentBlob,
  fetchReviewPortal,
  reviewAddComment,
  reviewApprove,
  reviewReject,
  reviewRequestChanges,
} from "@/lib/api";
import { useI18n, type TKey } from "@/lib/i18n";
import type { ReviewPortalPayload, SummarySections } from "@/lib/types";
import { cn, formatDate, formatSAR, triggerBlobDownload } from "@/lib/utils";

type Tab = "summary" | "risks" | "obligations" | "timeline" | "payments";

// Read-only rendering of the same rich summary structure AiSummaryPanel.tsx
// already renders internally — the public reviewer never sees generate/
// regenerate controls, but sees the exact same purpose/obligations/risks/
// payment/deadline sections with citations.
const SECTION_KEYS = [
  "purpose",
  "key_obligations",
  "notable_risks",
  "financial_terms",
  "term_and_key_dates",
  "termination_renewal",
  "next_steps",
] as const;

const SECTION_I18N: Record<(typeof SECTION_KEYS)[number], TKey> = {
  purpose: "summary.section.purpose",
  key_obligations: "summary.section.obligations",
  notable_risks: "summary.section.risks",
  financial_terms: "summary.section.financial",
  term_and_key_dates: "summary.section.term",
  termination_renewal: "summary.section.termination",
  next_steps: "summary.section.nextSteps",
};

function severityTone(severity: string): "danger" | "orange" | "warning" | "neutral" {
  if (severity === "critical") return "danger";
  if (severity === "high") return "orange";
  if (severity === "medium" || severity === "warning") return "warning";
  return "neutral";
}

// Every field rendered here comes straight from the contract text (a quote,
// an AI-picked category, an Arabic explanation next to an English one) —
// direction must be inferred per element, not inherited from the page's
// overall `lang`, or a Latin amount inside an Arabic sentence (or vice
// versa) renders reversed. `dir="auto"` lets the browser's bidi algorithm
// decide per element from its own first strong character.
function Bidi({ children, className }: { children: React.ReactNode; className?: string }) {
  if (children === null || children === undefined || children === "") return null;
  return (
    <span dir="auto" className={className}>
      {children}
    </span>
  );
}

// Every extracted item's "where did this come from?" answer: the original
// clause quote, its reference/page, and a jump action into the embedded
// document viewer above — the traceability the whole portal audit asked
// for, applied uniformly across risks/obligations/timeline/payments.
function SourceRef({
  clauseRef,
  page,
  quote,
  t,
  onJump,
}: {
  clauseRef?: string | null;
  page?: number | null;
  quote?: string | null;
  t: (k: TKey) => string;
  onJump?: (page: number | null | undefined) => void;
}) {
  if (!clauseRef && !page && !quote) return null;
  return (
    <div className="mt-2 space-y-1 text-xs">
      <p className="text-gray-400">
        {t("review.portal.source")}: {clauseRef ? `${t("detail.clause")} ${clauseRef}` : null}
        {clauseRef && page ? " · " : null}
        {page ? `${t("detail.viewer.page")} ${page}` : null}
        {onJump && (clauseRef || page) && (
          <button
            type="button"
            className="ms-2 font-medium text-brand-600 underline hover:text-brand-700"
            onClick={() => onJump(page)}
          >
            {t("evidence.jumpToClause")}
          </button>
        )}
      </p>
      {quote && (
        <Bidi className="block rounded border border-gray-200 bg-gray-50 p-2 italic text-gray-600">
          &ldquo;{quote}&rdquo;
        </Bidi>
      )}
    </div>
  );
}

function BusinessSummary({
  sections,
  lang,
  t,
  onJump,
}: {
  sections: SummarySections;
  lang: "ar" | "en";
  t: (k: TKey) => string;
  onJump: (page: number | null | undefined) => void;
}) {
  return (
    <div className="space-y-5">
      {SECTION_KEYS.map((key) => {
        const sec = sections[key];
        if (!sec) return null;
        return (
          <section key={key}>
            <h3 className="mb-1.5 text-sm font-semibold text-gray-800">{t(SECTION_I18N[key])}</h3>
            {sec.status === "not_stated" ? (
              <p className="text-sm text-gray-500">{t("summary.notStated")}</p>
            ) : (
              <>
                {sec.overview && (
                  <p dir="auto" className="mb-1.5 text-sm leading-relaxed text-gray-800">
                    {sec.overview}
                  </p>
                )}
                <ul className="list-disc space-y-1.5 ps-5 text-sm text-gray-800">
                  {sec.items.map((item, i) => (
                    <li key={i} dir="auto">
                      {item.text}
                      {item.citations?.length > 0 && (
                        <div className="mt-1 flex flex-wrap gap-1">
                          {item.citations.map((c, j) => (
                            <button
                              key={j}
                              type="button"
                              className="rounded bg-brand-50 px-1.5 py-0.5 text-xs text-brand-700 hover:bg-brand-100"
                              onClick={() => onJump(c.page)}
                            >
                              {c.clause_ref ? `${t("detail.clause")} ${c.clause_ref} · ` : ""}
                              {t("summary.citation")} p.{c.page}
                            </button>
                          ))}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </section>
        );
      })}
    </div>
  );
}

export default function ReviewPortalPage() {
  const { t, lang } = useI18n();
  const params = useParams<{ token: string }>();
  const token = params.token;
  const { confirm } = useConfirm();
  const { success: toastSuccess, error: toastError } = useToast();

  const [data, setData] = useState<ReviewPortalPayload | null>(null);
  const [tab, setTab] = useState<Tab>("summary");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [docBusy, setDocBusy] = useState(false);
  const [clauseRef, setClauseRef] = useState("");
  const [clauseComment, setClauseComment] = useState("");
  const [overallComment, setOverallComment] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const [showReject, setShowReject] = useState(false);
  const [showChanges, setShowChanges] = useState(false);
  const [docPage, setDocPage] = useState<number | null>(null);
  const docRef = useRef<HTMLDivElement | null>(null);
  // The iframe must never be pointed straight at the API URL: if that
  // request ever fails (expired mid-session, storage file missing,
  // wrong contract) the browser renders the raw JSON error body inline,
  // which is exactly the reported bug. Instead the PDF is fetched and
  // verified as a blob first, and the iframe only ever gets a src once
  // that succeeded — any failure shows an honest "Document unavailable"
  // state instead.
  const [docState, setDocState] = useState<"loading" | "ready" | "unavailable">("loading");
  const [docBlobUrl, setDocBlobUrl] = useState<string | null>(null);

  const load = useCallback(() => {
    setError(null);
    fetchReviewPortal(token)
      .then(setData)
      .catch((caught) => setError(apiErrorCode(caught)));
  }, [token]);

  useEffect(load, [load]);

  useEffect(() => {
    if (!data) return;
    let cancelled = false;
    let objectUrl: string | null = null;
    setDocState("loading");
    fetchReviewDocumentBlob(token)
      .then((blob) => {
        if (cancelled) return;
        if (blob.type && blob.type !== "application/pdf") {
          setDocState("unavailable");
          return;
        }
        objectUrl = URL.createObjectURL(blob);
        setDocBlobUrl(objectUrl);
        setDocState("ready");
      })
      .catch(() => {
        if (!cancelled) setDocState("unavailable");
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [data, token]);

  const readOnly = data?.read_only ?? false;
  const responded = data?.status === "approved" || data?.status === "rejected" || data?.status === "changes_requested";

  const tabs: { key: Tab; label: TKey }[] = [
    { key: "summary", label: "review.portal.tab.summary" },
    { key: "risks", label: "review.portal.tab.risks" },
    { key: "obligations", label: "review.portal.tab.obligations" },
    { key: "timeline", label: "review.portal.tab.timeline" },
    { key: "payments", label: "review.portal.tab.payments" },
  ];

  const jumpToDocument = useCallback((page: number | null | undefined) => {
    if (page) setDocPage(page);
    docRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  const downloadDocument = async () => {
    setDocBusy(true);
    try {
      const blob = await fetchReviewDocumentBlob(token);
      triggerBlobDownload(blob, `${data?.contract.title || "contract"}.pdf`);
    } catch (caught) {
      toastError(apiErrorCode(caught, t("common.error")));
    } finally {
      setDocBusy(false);
    }
  };

  const openDocument = async () => {
    setDocBusy(true);
    try {
      const blob = await fetchReviewDocumentBlob(token);
      window.open(URL.createObjectURL(blob), "_blank");
    } catch (caught) {
      toastError(apiErrorCode(caught, t("common.error")));
    } finally {
      setDocBusy(false);
    }
  };

  const onApprove = () => {
    confirm({
      title: t("review.decision.approve"),
      body: t("review.portal.submitApprove"),
      confirmLabel: t("review.decision.approve"),
      onConfirm: async () => {
        setBusy(true);
        try {
          await reviewApprove(token);
          toastSuccess(t("review.portal.thanks"));
          load();
        } catch (caught) {
          toastError(apiErrorCode(caught, t("common.error")));
          throw new Error("approve failed");
        } finally {
          setBusy(false);
        }
      },
    });
  };

  const onReject = async () => {
    if (!rejectReason.trim()) return;
    setBusy(true);
    try {
      await reviewReject(token, rejectReason);
      toastSuccess(t("review.portal.thanks"));
      setShowReject(false);
      load();
    } catch (caught) {
      toastError(apiErrorCode(caught, t("common.error")));
    } finally {
      setBusy(false);
    }
  };

  const onChanges = async () => {
    if (!overallComment.trim()) return;
    setBusy(true);
    try {
      await reviewRequestChanges(token, overallComment);
      toastSuccess(t("review.portal.thanks"));
      setShowChanges(false);
      load();
    } catch (caught) {
      toastError(apiErrorCode(caught, t("common.error")));
    } finally {
      setBusy(false);
    }
  };

  const onAddComment = async () => {
    if (!clauseComment.trim()) return;
    setBusy(true);
    try {
      await reviewAddComment(token, {
        comment: clauseComment,
        clause_ref: clauseRef || undefined,
        page: undefined,
      });
      setClauseComment("");
      setClauseRef("");
      load();
    } catch (caught) {
      toastError(apiErrorCode(caught, t("common.error")));
    } finally {
      setBusy(false);
    }
  };

  if (error) {
    return (
      <Card>
        <CardBody className="text-center">
          <p className="font-semibold text-danger-600">{t("review.portal.loadFailed")}</p>
          <p className="mt-1 text-xs text-gray-500">{error}</p>
          <Button variant="secondary" className="mt-3" onClick={load}>
            {t("common.retry")}
          </Button>
        </CardBody>
      </Card>
    );
  }

  if (!data) return <p className="p-8 text-center text-gray-400">{t("common.loading")}</p>;

  const summaryLang: "ar" | "en" = lang === "ar" ? "ar" : "en";
  const businessSections: SummarySections | null =
    summaryLang === "ar" ? data.business_summary?.summary_ar ?? null : data.business_summary?.summary_en ?? null;
  const docSrc = docBlobUrl && docPage ? `${docBlobUrl}#page=${docPage}` : docBlobUrl;

  return (
    <div className="relative min-h-screen bg-[#F8FAFC]">
      {/* Matches the ambient wash of the authenticated shell and the signer
          portal, so all three public/private surfaces read as one product. */}
      <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden" aria-hidden>
        <div className="absolute -top-40 end-[-6rem] h-96 w-96 rounded-full bg-emerald-100/50 blur-[100px]" />
        <div className="absolute bottom-[-10rem] start-[-8rem] h-[28rem] w-[28rem] rounded-full bg-teal-50/60 blur-[120px]" />
      </div>

      <div className="border-b border-white bg-white/70 px-4 py-6 backdrop-blur-2xl">
        <div className="mx-auto max-w-6xl">
          <div className="mb-3 flex items-center justify-between gap-4">
            <Logo size="sm" tone="brand" />
          </div>
          <p className="text-sm font-semibold text-emerald-700">{t("review.portal.title")}</p>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">{data.contract.title}</h1>
          <div className="mt-2 flex flex-wrap gap-2">
            <ReviewStatusBadge status={data.status} />
            {data.expires_at && <Badge tone="subtle">{formatDate(data.expires_at, lang)}</Badge>}
          </div>
        </div>
      </div>

      <div className="mx-auto grid max-w-6xl gap-6 px-4 py-6 pb-28 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {(readOnly || data.status === "expired") && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              {data.status === "expired" ? t("review.portal.expired") : responded ? t("review.portal.thanks") : t("review.portal.readOnly")}
            </div>
          )}

          {/* This dossier is contract-wide, not version-snapshotted (obligations/
              deadlines/payments/risk findings have no per-version history in the
              schema — a newer version overwrites them in place). When the review
              is stale, say so plainly rather than silently showing newer-version
              data as if it were what was originally sent. */}
          {data.is_stale && (
            <div className="rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900">
              {t("review.portal.staleDossierNotice")}
            </div>
          )}

          {/* A contract review portal must always expose the contract itself —
              not just extracted data. Same guaranteed-renderable document the
              signature flow already uses, token-gated the same way as every
              other public review route. See
              docs/review-portal-document-access-redesign.md. */}
          <div ref={docRef}>
          <Card>
            <CardBody>
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
                  {t("review.portal.document.title")}
                </h2>
                {docState === "ready" && (
                  <div className="flex gap-2">
                    <Button variant="secondary" size="sm" loading={docBusy} onClick={downloadDocument}>
                      {t("review.portal.document.download")}
                    </Button>
                    <Button variant="secondary" size="sm" loading={docBusy} onClick={openDocument}>
                      {t("review.portal.document.open")}
                    </Button>
                  </div>
                )}
              </div>
              {docState === "loading" && (
                <div className="flex h-[70vh] w-full items-center justify-center rounded-lg border border-gray-200 bg-gray-50">
                  <p className="text-sm text-gray-400">{t("common.loading")}</p>
                </div>
              )}
              {docState === "unavailable" && (
                <div className="flex h-[70vh] w-full flex-col items-center justify-center gap-1 rounded-lg border border-gray-200 bg-gray-50 text-center">
                  <p className="text-sm font-medium text-gray-600">{t("review.portal.document.unavailable")}</p>
                  <p className="text-xs text-gray-400">{t("review.portal.document.unavailableHint")}</p>
                </div>
              )}
              {docState === "ready" && docSrc && (
                <iframe
                  key={docSrc}
                  src={docSrc}
                  title={data.contract.title ?? t("review.portal.document.title")}
                  className="h-[70vh] w-full rounded-lg border border-gray-200"
                />
              )}
            </CardBody>
          </Card>
          </div>

          <Card>
            <CardBody>
              <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
                {t("review.portal.summary.business")}
              </h2>
              {data.business_summary?.status === "ready" && businessSections ? (
                <BusinessSummary sections={businessSections} lang={summaryLang} t={t} onJump={jumpToDocument} />
              ) : (
                <p className="text-sm text-gray-500">{t("review.portal.summary.notAvailable")}</p>
              )}
            </CardBody>
          </Card>

      <Card className="overflow-hidden">
        <div className="flex flex-wrap gap-1 border-b bg-muted-50/50 p-2">
          {tabs.map(({ key, label }) => (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              className={cn(
                "rounded-lg px-3 py-2 text-sm font-semibold",
                tab === key ? "bg-white text-brand-700 shadow-sm" : "text-gray-500"
              )}
            >
              {t(label)}
            </button>
          ))}
        </div>
        <CardBody>
          {tab === "summary" && (
            <dl className="grid gap-3 sm:grid-cols-2 text-sm">
              <div className="sm:col-span-2">
                <dt className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-400">
                  {t("review.portal.summary.metadata")}
                </dt>
              </div>
              <div>
                <dt className="text-gray-500">{t("detail.value")}</dt>
                <dd className="font-semibold">{formatSAR(data.contract.value_sar, lang)}</dd>
              </div>
              <div>
                <dt className="text-gray-500">{t("detail.law")}</dt>
                <dd>{data.contract.governing_law ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-gray-500">{t("detail.from")}</dt>
                <dd><DualDate date={data.contract.start_date} /></dd>
              </div>
              <div>
                <dt className="text-gray-500">{t("detail.to")}</dt>
                <dd><DualDate date={data.contract.end_date} /></dd>
              </div>
            </dl>
          )}
          {tab === "risks" && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-4 rounded-lg border p-3">
                <RiskScoreRing score={data.risks.score} label={t("detail.tab.risk")} />
                <div>
                  <p className="text-sm font-semibold text-gray-900">
                    {t("review.portal.riskLevel")}: {t(`review.portal.riskLevelValue.${data.risks.level}` as TKey)}
                  </p>
                  <p className="text-xs text-gray-500">{t("detail.riskWhy")}</p>
                </div>
              </div>
              {data.risks.items.length === 0 ? (
                <p className="text-sm text-gray-500">{t("review.portal.emptyRisks")}</p>
              ) : (
                <ul className="space-y-2">
                  {data.risks.items.map((r, i) => (
                    <li key={i} className="rounded-lg border p-3 text-sm">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone={severityTone(r.severity)}>{r.severity}</Badge>
                        {!r.contributes_to_score && (
                          <Badge tone="subtle">{t("review.portal.additionalContext")}</Badge>
                        )}
                      </div>
                      <Bidi className="mt-1 block font-medium">{r.label}</Bidi>
                      <Bidi className="block text-gray-600">
                        {lang === "ar" ? r.detail_ar || r.detail : r.detail || r.detail_ar}
                      </Bidi>
                      {r.type === "penalty" && (r.rate || r.cap) && (
                        <p className="mt-1 text-xs text-gray-500">
                          {r.rate && <span>{t("obligation.penalty")}: {r.rate}</span>}
                          {r.rate && r.cap && " · "}
                          {r.cap && <span>{t("review.portal.penaltyCap")}: {r.cap}</span>}
                        </p>
                      )}
                      <SourceRef clauseRef={r.clause_ref} page={r.page} quote={r.quote} onJump={jumpToDocument} t={t} />
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {tab === "obligations" && (
            <div className="space-y-2">
              {data.obligations.length === 0 ? (
                <p className="text-sm text-gray-500">{t("review.portal.emptyObligations")}</p>
              ) : (
                <ul className="space-y-2">
                  {data.obligations.map((o) => (
                    <li key={o.id} className="rounded-lg border p-3 text-sm">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <Bidi className="font-medium">{o.title || o.description}</Bidi>
                        <Badge tone={o.status === "overdue" ? "danger" : o.status === "done" ? "success" : "neutral"}>
                          {t(`obligation.status.${o.status}` as TKey)}
                        </Badge>
                      </div>
                      {o.title && o.description && <Bidi className="mt-1 block text-gray-600">{o.description}</Bidi>}
                      <dl className="mt-2 grid gap-1 text-xs text-gray-500 sm:grid-cols-2">
                        <div>
                          <dt className="inline font-semibold">{t("obligation.party")}: </dt>
                          <dd className="inline">{o.responsible_party ?? "—"}</dd>
                          {o.beneficiary && (
                            <dd className="inline"> → {o.beneficiary}</dd>
                          )}
                        </div>
                        <div>
                          <dt className="inline font-semibold">{t("obligation.due")}: </dt>
                          <dd className="inline">{o.due_date ? <DualDate date={o.due_date} /> : t("review.portal.noDateYet")}</dd>
                        </div>
                        {o.trigger_event && (
                          <div className="sm:col-span-2">
                            <dt className="inline font-semibold">{t("review.portal.trigger")}: </dt>
                            <dd className="inline">{o.trigger_type ? `${o.trigger_type} — ` : ""}{o.trigger_event}</dd>
                          </div>
                        )}
                        {o.penalty_text && (
                          <div className="sm:col-span-2">
                            <dt className="inline font-semibold">{t("obligation.penalty")}: </dt>
                            <Bidi className="inline">{o.penalty_text}</Bidi>
                          </div>
                        )}
                      </dl>
                      <SourceRef clauseRef={o.clause_ref} page={o.page} quote={o.quote} onJump={jumpToDocument} t={t} />
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {tab === "timeline" && (
            <div className="space-y-2">
              {data.timeline.deadlines.length === 0 ? (
                <p className="text-sm text-gray-500">{t("review.portal.emptyTimeline")}</p>
              ) : (
                <ul className="space-y-2">
                  {data.timeline.deadlines.map((d) => (
                    <li key={d.id} className="rounded-lg border p-3 text-sm">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <Bidi className="font-medium">{d.title ?? d.type}</Bidi>
                        <Badge tone={severityTone(d.status === "missed" ? "high" : d.severity)}>
                          {t(`deadline.status.${d.status}` as TKey)}
                        </Badge>
                      </div>
                      <p className="mt-1 text-gray-700">
                        {d.deadline_date ? (
                          <DualDate date={d.deadline_date} />
                        ) : (
                          <span className="text-gray-500">{t("review.portal.noDateYet")}</span>
                        )}
                        {d.notice_period_days ? ` · ${t("review.portal.noticeDays")}: ${d.notice_period_days}` : ""}
                      </p>
                      {d.responsible_party && (
                        <p className="text-xs text-gray-500">
                          {t("obligation.party")}: {d.responsible_party}
                        </p>
                      )}
                      {d.source_trigger_date && (
                        <p className="text-xs text-gray-500">
                          {t("detail.noticeReference")}: <DualDate date={d.source_trigger_date} />
                        </p>
                      )}
                      {!d.deadline_date && (d.calculation_explanation || d.calculation_explanation_ar) && (
                        <Bidi className="mt-1 block text-xs text-amber-700">
                          {lang === "ar"
                            ? d.calculation_explanation_ar || d.calculation_explanation
                            : d.calculation_explanation || d.calculation_explanation_ar}
                        </Bidi>
                      )}
                      <SourceRef clauseRef={d.clause_ref} page={d.page} quote={d.quote} onJump={jumpToDocument} t={t} />
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {tab === "payments" && (
            <div className="space-y-2">
              {data.payments.milestones.length === 0 ? (
                <p className="text-sm text-gray-500">{t("review.portal.emptyPayments")}</p>
              ) : (
                <ul className="space-y-2">
                  {data.payments.milestones.map((m) => (
                    <li key={m.id} className="rounded-lg border p-3 text-sm">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <Bidi className="font-medium">{m.label || m.type}</Bidi>
                        <Badge tone={m.status === "overdue" ? "danger" : m.status === "paid" ? "success" : "neutral"}>
                          {t(`payment.status.${m.status}` as TKey)}
                        </Badge>
                      </div>
                      <p className="mt-1 text-gray-700">{formatSAR(m.amount_sar, lang)}</p>
                      <p className="text-xs text-gray-500">
                        {t("obligation.due")}: {m.due_date ? <DualDate date={m.due_date} /> : t("review.portal.noDateYet")}
                      </p>
                      <SourceRef clauseRef={m.clause_ref} page={m.page} quote={m.quote} onJump={jumpToDocument} t={t} />
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </CardBody>
      </Card>

      {data.comments.length > 0 && (
        <Card>
          <CardBody>
            <h3 className="mb-2 font-semibold">{t("review.portal.comments")}</h3>
            <ul className="space-y-2 text-sm">
              {data.comments.map((c) => (
                <li key={c.id} className="rounded border p-2">
                  {c.clause_ref && <span className="font-semibold">{c.clause_ref}: </span>}
                  {c.comment}
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>
      )}
        </div>

      {!readOnly && (
        <aside className="space-y-4 lg:sticky lg:top-6 lg:self-start">
          <Card>
            <CardBody className="space-y-3">
              <h3 className="font-semibold">{t("review.portal.clauseComment")}</h3>
              <input
                className="w-full rounded-lg border px-3 py-2 text-sm"
                placeholder={t("review.portal.clauseRef")}
                value={clauseRef}
                onChange={(e) => setClauseRef(e.target.value)}
              />
              <textarea
                rows={3}
                className="w-full rounded-lg border px-3 py-2 text-sm"
                value={clauseComment}
                onChange={(e) => setClauseComment(e.target.value)}
              />
              <Button variant="secondary" size="sm" loading={busy} onClick={onAddComment}>
                {t("review.portal.addComment")}
              </Button>
            </CardBody>
          </Card>

          <Card className="hidden lg:block">
            <CardBody className="space-y-2">
              <Button variant="primary" className="w-full" loading={busy} onClick={onApprove}>
                {t("review.decision.approve")}
              </Button>
              <Button variant="secondary" className="w-full" onClick={() => { setShowReject(true); setShowChanges(false); }}>
                {t("review.decision.reject")}
              </Button>
              <Button variant="secondary" className="w-full" onClick={() => { setShowChanges(true); setShowReject(false); }}>
                {t("review.decision.changes_requested")}
              </Button>
            </CardBody>
          </Card>

          {showReject && (
            <Card>
              <CardBody className="space-y-2">
                <label className="text-sm font-semibold">{t("review.portal.rejectReason")}</label>
                <textarea className="w-full rounded-lg border px-3 py-2 text-sm" rows={3} value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} />
                <Button variant="danger" size="sm" loading={busy} onClick={onReject}>
                  {t("review.portal.submitReject")}
                </Button>
              </CardBody>
            </Card>
          )}

          {showChanges && (
            <Card>
              <CardBody className="space-y-2">
                <label className="text-sm font-semibold">{t("review.portal.overallComment")}</label>
                <textarea className="w-full rounded-lg border px-3 py-2 text-sm" rows={3} value={overallComment} onChange={(e) => setOverallComment(e.target.value)} />
                <Button variant="primary" size="sm" loading={busy} onClick={onChanges}>
                  {t("review.portal.submitChanges")}
                </Button>
              </CardBody>
            </Card>
          )}
        </aside>
      )}
      </div>

      {!readOnly && (
          <div className="fixed inset-x-0 bottom-0 z-40 border-t bg-white/95 p-4 shadow-lg backdrop-blur lg:hidden">
            <div className="mx-auto flex max-w-5xl flex-wrap items-end justify-center gap-2">
              <Button variant="primary" loading={busy} onClick={onApprove}>
                {t("review.decision.approve")}
              </Button>
              <Button variant="secondary" onClick={() => { setShowReject(true); setShowChanges(false); }}>
                {t("review.decision.reject")}
              </Button>
              <Button variant="secondary" onClick={() => { setShowChanges(true); setShowReject(false); }}>
                {t("review.decision.changes_requested")}
              </Button>
            </div>
          </div>
      )}
    </div>
  );
}
