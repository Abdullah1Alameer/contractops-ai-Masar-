"use client";
import Link from "next/link";
import { useEffect, useState } from "react";

import CategoryBadge from "@/components/CategoryBadge";
import StatusChip from "@/components/StatusChip";
import TypeBadge from "@/components/TypeBadge";
import { api, deleteContract } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { ContractListItem } from "@/lib/types";
import { formatSAR } from "@/lib/utils";

export default function ContractsPage() {
  const { t, lang } = useI18n();
  const [rows, setRows] = useState<ContractListItem[] | null>(null);
  const [error, setError] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const load = () => {
    setError(false);
    api<ContractListItem[]>("/api/contracts").then(setRows).catch(() => setError(true));
  };
  useEffect(load, []);

  const onDelete = async (id: string) => {
    if (deletingId) return;
    if (!window.confirm(t("list.deleteConfirm"))) return;
    setDeletingId(id);
    try {
      await deleteContract(id);
      setRows((prev) => prev?.filter((r) => r.id !== id) ?? null);
    } catch {
      alert(t("common.error"));
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t("list.title")}</h1>
        <Link href="/upload" className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700">
          {t("nav.upload")}
        </Link>
      </div>

      {error && (
        <div className="rounded-xl border bg-white p-8 text-center">
          <p className="mb-3 text-red-600">{t("common.error")}</p>
          <button onClick={load} className="rounded-md border px-4 py-1.5 text-sm hover:bg-gray-50">
            {t("common.retry")}
          </button>
        </div>
      )}
      {!error && rows === null && <p className="p-8 text-center text-gray-400">{t("common.loading")}</p>}
      {!error && rows?.length === 0 && (
        <div className="rounded-xl border bg-white p-10 text-center text-gray-500">{t("list.empty")}</div>
      )}
      {!error && rows && rows.length > 0 && (
        <div className="overflow-x-auto rounded-xl border bg-white shadow-sm">
          <table className="w-full text-sm">
            <thead className="border-b bg-gray-50 text-start text-gray-600">
              <tr>
                {(["list.col.title", "list.col.type", "list.col.party", "list.col.value", "list.col.obligations", "list.col.status"] as const).map((k) => (
                  <th key={k} className="px-4 py-3 text-start font-medium">
                    {t(k)}
                  </th>
                ))}
                <th className="px-4 py-3 text-start font-medium sr-only">{t("list.delete")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.id} className="border-b last:border-0 hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <Link href={`/contracts/${c.id}`} className="font-semibold text-brand-700 hover:underline">
                      {c.title}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap items-center gap-1.5">
                      {c.status === "unsupported" || c.supported === false ? (
                        <StatusChip status="unsupported" />
                      ) : (
                        <>
                          {c.type && <TypeBadge type={c.type} />}
                          <CategoryBadge category={c.contract_category} />
                        </>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-700">{c.party_b ?? "—"}</td>
                  <td className="px-4 py-3">{formatSAR(c.value_sar, lang)}</td>
                  <td className="px-4 py-3 text-gray-600">
                    {c.obligation_counts.pending} {t("list.pending")}
                    {c.obligation_counts.overdue > 0 && (
                      <span className="ms-2 font-semibold text-red-600">
                        {c.obligation_counts.overdue} {t("list.overdue")}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <StatusChip status={c.status} />
                  </td>
                  <td className="px-4 py-3 text-end">
                    <button
                      onClick={() => onDelete(c.id)}
                      disabled={deletingId === c.id}
                      title={t("list.delete")}
                      aria-label={t("list.delete")}
                      className="inline-flex items-center gap-1 rounded-md border border-red-200 bg-white px-2.5 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
                    >
                      {deletingId === c.id ? t("list.deleting") : t("list.delete")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
