"use client";
// F1 money screen. Two panes:
//  - data pane (first in DOM = RIGHT in RTL): header cards + obligations +
//    extracted notice periods + F2 timeline tab + F3 payment tracker
//  - source viewer (LEFT): raw page text with the exact quote highlighted.
// Every extracted value either opens its highlighted source (verified quote)
// or shows a "source unverified" badge — never a wrong highlight.
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";

import ConfidenceChip from "@/components/ConfidenceChip";
import DeadlineTimeline from "@/components/DeadlineTimeline";
import DemoClockControl from "@/components/DemoClockControl";
import DualDate from "@/components/DualDate";
import LogEventDialog from "@/components/LogEventDialog";
import PaymentTracker from "@/components/PaymentTracker";
import SourceViewer from "@/components/SourceViewer";
import StatusChip from "@/components/StatusChip";
import TypeBadge from "@/components/TypeBadge";
import UnsupportedContractWarning from "@/components/UnsupportedContractWarning";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { api, apiJson, getDemoToday } from "@/lib/api";
import { useI18n, type TKey } from "@/lib/i18n";
import type {
  ClauseSource,
  ContractDetail,
  NoticePeriodItem,
  ObligationRow,
  SourceTarget,
} from "@/lib/types";
import { cn, formatSAR } from "@/lib/utils";

type Tab = "obligations" | "notice" | "deadlines" | "milestones";

export default function ContractDetailPage() {
  const { t, lang } = useI18n();
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [detail, setDetail] = useState<ContractDetail | null>(null);
  const [obligations, setObligations] = useState<ObligationRow[]>([]);
  const [target, setTarget] = useState<SourceTarget | null>(null);
  const [tab, setTab] = useState<Tab>("obligations");
  const [error, setError] = useState(false);
  const [demoToday, setDemoToday] = useState("");
  const [timelineRefresh, setTimelineRefresh] = useState(0);

  const load = useCallback(() => {
    setError(false);
    api<ContractDetail>(`/api/contracts/${id}`).then(setDetail).catch(() => setError(true));
    api<ObligationRow[]>(`/api/contracts/${id}/obligations`).then(setObligations).catch(() => {});
  }, [id]);
  useEffect(load, [load]);

  useEffect(() => {
    getDemoToday()
      .then((r) => setDemoToday(r.today))
      .catch(() => {});
  }, []);

  const extraction = (field: string) => detail?.extractions.find((e) => e.field_name === field);
  const notices: NoticePeriodItem[] = (extraction("notice_periods")?.value_json as NoticePeriodItem[]) ?? [];

  const jump = (src: ClauseSource | { page: number; char_start: number | null; char_end: number | null } | null) => {
    if (src && src.char_start != null && src.char_end != null)
      setTarget({ page: src.page, char_start: src.char_start, char_end: src.char_end });
  };

  const toggleObligation = async (o: ObligationRow) => {
    const next = o.status === "done" ? "pending" : "done";
    setObligations((rows) => rows.map((r) => (r.id === o.id ? { ...r, status: next } : r)));
    try {
      await apiJson(`/api/obligations/${o.id}`, "PATCH", { status: next });
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

  const tabs: { key: Tab; label: TKey }[] = [
    { key: "obligations", label: "detail.tab.obligations" },
    { key: "notice", label: "detail.tab.notice" },
    { key: "deadlines", label: "detail.tab.deadlines" },
    { key: "milestones", label: "detail.tab.milestones" },
  ];

  return (
    <div className="space-y-6 motion-safe:animate-fadeIn">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold text-gray-900">{detail.title}</h1>
        <TypeBadge type={detail.type} />
        <StatusChip status={detail.status} />
        {detail.language && <Badge tone="neutral">{detail.language === "ar" ? "عربي" : detail.language === "en" ? "EN" : "AR/EN"}</Badge>}
        {detail.calendar && <Badge tone="neutral">{detail.calendar === "hijri" ? "هجري" : detail.calendar === "gregorian" ? "ميلادي" : "هجري/ميلادي"}</Badge>}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="min-w-0 space-y-6">
          <div className="grid gap-4 sm:grid-cols-2">
            {card(
              t("detail.parties"),
              <div className="space-y-1">
                <p><span className="text-gray-500">{t("detail.partyA")}: </span>{detail.party_a ?? "—"}</p>
                <p><span className="text-gray-500">{t("detail.partyB")}: </span>{detail.party_b ?? "—"}</p>
              </div>,
              "party_a"
            )}
            {card(t("detail.value"), formatSAR(detail.value_sar, lang), "value_sar")}
            {card(
              t("detail.duration"),
              <div className="space-y-1">
                <p><span className="text-gray-500">{t("detail.from")}: </span><DualDate date={detail.start_date} /></p>
                <p><span className="text-gray-500">{t("detail.to")}: </span><DualDate date={detail.end_date} /></p>
              </div>,
              "start_date"
            )}
            {card(t("detail.law"), detail.governing_law ?? "—", "governing_law")}
            {card(t("detail.retention"), detail.retention_pct != null ? `${detail.retention_pct}٪` : "—", "retention_pct")}
            {card(t("detail.bond"), <DualDate date={detail.bond_expiry} />, "bond_expiry")}
          </div>

          <Card className="overflow-hidden">
            <div className="flex flex-wrap gap-1 border-b border-gray-100 bg-muted-50/50 p-2">
              {tabs.map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => setTab(key)}
                  className={cn(
                    "relative rounded-lg px-4 py-2.5 text-sm font-semibold motion-safe:transition-colors",
                    tab === key ? "bg-white text-brand-700 shadow-sm" : "text-gray-500 hover:text-gray-800"
                  )}
                >
                  {t(label)}
                  {tab === key && <span className="absolute inset-x-3 -bottom-0.5 h-0.5 rounded-full bg-brand-600" />}
                </button>
              ))}
            </div>
            <div className="p-5 motion-safe:animate-fadeIn">
              {tab === "obligations" && (
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
              )}

              {tab === "notice" && (
                <div>
                  <div className="mb-3 flex items-center justify-between">
                    <h3 className="text-sm font-semibold">{t("detail.noticeTitle")}</h3>
                    <span className="rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700 ring-1 ring-inset ring-amber-600/20">
                      {t("detail.noticeWaiting")}
                    </span>
                  </div>
                  {notices.length === 0 && <p className="py-6 text-center text-sm text-gray-400">{t("common.empty")}</p>}
                  <ul className="space-y-2">
                    {notices.map((n, i) => (
                      <li key={i} className="flex items-center justify-between gap-3 rounded-lg border p-3">
                        <div>
                          <p className="text-sm font-medium">{n.purpose}</p>
                          <p className="text-xs text-gray-500">
                            {t("notice.days")}: {n.days} {t("common.days")}
                          </p>
                        </div>
                        <div className="flex items-center gap-1.5">
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
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {tab === "deadlines" && (
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
              )}

              {tab === "milestones" && demoToday && (
                <PaymentTracker
                  contractId={id}
                  demoToday={demoToday}
                  contractStatus={detail.status}
                  refreshKey={timelineRefresh}
                  onSourceClick={setTarget}
                />
              )}
            </div>
          </Card>
        </div>

        <div className="h-[calc(100vh-180px)] min-w-0 lg:sticky lg:top-24">
          <SourceViewer contractId={id} target={target} />
        </div>
      </div>
    </div>
  );
}
