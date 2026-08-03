"use client";
// F1 money screen. Two panes:
//  - data pane (first in DOM = RIGHT in RTL): header cards + obligations +
//    extracted notice periods + F2/F3 placeholder tabs
//  - source viewer (LEFT): raw page text with the exact quote highlighted.
// Every extracted value either opens its highlighted source (verified quote)
// or shows a "source unverified" badge — never a wrong highlight.
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";

import ConfidenceChip from "@/components/ConfidenceChip";
import DualDate from "@/components/DualDate";
import SourceViewer from "@/components/SourceViewer";
import StatusChip from "@/components/StatusChip";
import TypeBadge from "@/components/TypeBadge";
import UnsupportedContractWarning from "@/components/UnsupportedContractWarning";
import { api, apiJson, apiWithMeta } from "@/lib/api";
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
  const [deadlines, setDeadlines] = useState<{ data: any[]; placeholder: boolean } | null>(null);
  const [milestones, setMilestones] = useState<{ data: any[]; placeholder: boolean } | null>(null);
  const [target, setTarget] = useState<SourceTarget | null>(null);
  const [tab, setTab] = useState<Tab>("obligations");
  const [error, setError] = useState(false);

  const load = useCallback(() => {
    setError(false);
    api<ContractDetail>(`/api/contracts/${id}`).then(setDetail).catch(() => setError(true));
    api<ObligationRow[]>(`/api/contracts/${id}/obligations`).then(setObligations).catch(() => {});
    apiWithMeta<any[]>(`/api/contracts/${id}/deadlines`).then(setDeadlines).catch(() => {});
    apiWithMeta<any[]>(`/api/contracts/${id}/milestones`).then(setMilestones).catch(() => {});
  }, [id]);
  useEffect(load, [load]);

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
      <div className="rounded-xl border bg-white p-8 text-center">
        <p className="mb-3 text-red-600">{t("common.error")}</p>
        <button onClick={load} className="rounded-md border px-4 py-1.5 text-sm hover:bg-gray-50">
          {t("common.retry")}
        </button>
      </div>
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
      <div className="rounded-xl border bg-white p-4 shadow-sm">
        <div className="mb-1 flex items-center justify-between gap-2">
          <h3 className="text-xs font-medium text-gray-500">{title}</h3>
          <div className="flex items-center gap-1.5">
            {e && <ConfidenceChip confidence={e.confidence} />}
            {e?.clause && <SourceButton src={e.clause} />}
          </div>
        </div>
        <div className="text-sm font-semibold text-gray-800">{body}</div>
      </div>
    );
  };

  const tabs: { key: Tab; label: TKey }[] = [
    { key: "obligations", label: "detail.tab.obligations" },
    { key: "notice", label: "detail.tab.notice" },
    { key: "deadlines", label: "detail.tab.deadlines" },
    { key: "milestones", label: "detail.tab.milestones" },
  ];

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-bold">{detail.title}</h1>
        <TypeBadge type={detail.type} />
        <StatusChip status={detail.status} />
        {detail.language && <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs text-gray-600">{detail.language === "ar" ? "عربي" : detail.language === "en" ? "EN" : "AR/EN"}</span>}
        {detail.calendar && <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs text-gray-600">{detail.calendar === "hijri" ? "هجري" : detail.calendar === "gregorian" ? "ميلادي" : "هجري/ميلادي"}</span>}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* ===== data pane (RIGHT in RTL) ===== */}
        <div className="min-w-0 space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
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

          <div className="rounded-xl border bg-white shadow-sm">
            <div className="flex border-b">
              {tabs.map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => setTab(key)}
                  className={cn(
                    "px-4 py-2.5 text-sm font-medium",
                    tab === key ? "border-b-2 border-brand-600 text-brand-700" : "text-gray-500 hover:text-gray-700"
                  )}
                >
                  {t(label)}
                </button>
              ))}
            </div>
            <div className="p-4">
              {tab === "obligations" && (
                <div className="overflow-x-auto">
                  {obligations.length === 0 && <p className="py-6 text-center text-sm text-gray-400">{t("common.empty")}</p>}
                  {obligations.length > 0 && (
                    <table className="w-full text-sm">
                      <thead className="text-gray-500">
                        <tr>
                          <th className="px-2 py-2 text-start font-medium">{t("obligation.desc")}</th>
                          <th className="px-2 py-2 text-start font-medium">{t("obligation.party")}</th>
                          <th className="px-2 py-2 text-start font-medium">{t("obligation.due")}</th>
                          <th className="px-2 py-2 text-start font-medium">{t("obligation.penalty")}</th>
                          <th className="px-2 py-2 text-start font-medium">{t("obligation.status")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {obligations.map((o) => (
                          <tr key={o.id} className="border-t align-top">
                            <td className="px-2 py-2.5">
                              <p>{o.description}</p>
                              <div className="mt-1 flex items-center gap-1.5">
                                <SourceButton src={o.source} />
                                {o.confidence != null && <ConfidenceChip confidence={o.confidence} />}
                              </div>
                            </td>
                            <td className="px-2 py-2.5 text-gray-600">{o.responsible_party ?? "—"}</td>
                            <td className="px-2 py-2.5">{o.due_date ? <DualDate date={o.due_date} /> : <span className="text-gray-400">{t("obligation.noDue")}</span>}</td>
                            <td className="px-2 py-2.5 text-gray-600">{o.penalty_text ?? "—"}</td>
                            <td className="px-2 py-2.5">
                              <button
                                onClick={() => toggleObligation(o)}
                                className={cn(
                                  "rounded-full px-2.5 py-0.5 text-xs font-medium",
                                  o.status === "done" && "bg-emerald-100 text-emerald-800",
                                  o.status === "pending" && "bg-gray-100 text-gray-700 hover:bg-gray-200",
                                  o.status === "overdue" && "bg-red-100 text-red-700"
                                )}
                              >
                                {t(`obligation.${o.status}` as TKey)}
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
                <PlaceholderList
                  meta={deadlines}
                  note={t("detail.deadlinesWaiting")}
                  render={(d: any) => (
                    <li key={d.id} className="flex items-center justify-between rounded-lg border p-3 text-sm">
                      <span>{d.label}</span>
                      <span className="flex items-center gap-2">
                        <DualDate date={d.deadline_date} />
                        <span className={cn("rounded-full px-2 py-0.5 text-xs", d.severity === "critical" ? "bg-red-100 text-red-700" : d.severity === "warning" ? "bg-amber-100 text-amber-700" : "bg-gray-100 text-gray-600")}>
                          {t(`deadline.severity.${d.severity}` as TKey)}
                        </span>
                      </span>
                    </li>
                  )}
                />
              )}

              {tab === "milestones" && (
                <PlaceholderList
                  meta={milestones}
                  note={t("detail.milestonesWaiting")}
                  render={(m: any) => (
                    <li key={m.id} className="flex items-center justify-between rounded-lg border p-3 text-sm">
                      <div>
                        <p className="font-medium">{m.seq}. {m.label}</p>
                        {m.preconditions?.length > 0 && (
                          <p className="text-xs text-gray-500">{t("milestone.preconditions")}: {m.preconditions.join("، ")}</p>
                        )}
                      </div>
                      <span className="flex items-center gap-2">
                        <span>{formatSAR(m.amount_sar, lang)}</span>
                        <span className={cn("rounded-full px-2 py-0.5 text-xs", m.status === "paid" ? "bg-emerald-100 text-emerald-700" : m.status === "claimable" ? "bg-blue-100 text-blue-700" : "bg-gray-100 text-gray-600")}>
                          {t(`milestone.status.${m.status}` as TKey)}
                        </span>
                      </span>
                    </li>
                  )}
                />
              )}
            </div>
          </div>
        </div>

        {/* ===== source viewer (LEFT in RTL) ===== */}
        <div className="h-[calc(100vh-180px)] min-w-0 lg:sticky lg:top-4">
          <SourceViewer contractId={id} target={target} />
        </div>
      </div>
    </div>
  );
}

function PlaceholderList({
  meta,
  note,
  render,
}: {
  meta: { data: any[]; placeholder: boolean } | null;
  note: string;
  render: (item: any) => React.ReactNode;
}) {
  const { t } = useI18n();
  if (!meta) return <p className="py-6 text-center text-sm text-gray-400">{t("common.loading")}</p>;
  return (
    <div>
      {meta.placeholder && (
        <p className="mb-3 rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-700 ring-1 ring-inset ring-amber-600/20">
          {note} — {t("common.placeholderData")}
        </p>
      )}
      {meta.data.length === 0 && <p className="py-6 text-center text-sm text-gray-400">{t("common.empty")}</p>}
      <ul className="space-y-2">{meta.data.map(render)}</ul>
    </div>
  );
}
