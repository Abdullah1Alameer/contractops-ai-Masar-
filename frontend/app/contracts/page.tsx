"use client";
import Link from "next/link";
import { useEffect, useState } from "react";

import CategoryBadge from "@/components/CategoryBadge";
import { useConfirm } from "@/components/feedback/ConfirmDialog";
import { useToast } from "@/components/feedback/ToastProvider";
import StatusChip from "@/components/StatusChip";
import TypeBadge from "@/components/TypeBadge";
import Button from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import { SkeletonTable } from "@/components/ui/Skeleton";
import { api, deleteContract } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { ContractListItem } from "@/lib/types";
import { formatSAR } from "@/lib/utils";

export default function ContractsPage() {
  const { t, lang } = useI18n();
  const { confirm } = useConfirm();
  const toast = useToast();
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
    await confirm({
      title: t("confirm.deleteContract.title"),
      body: t("confirm.deleteContract.body"),
      confirmLabel: t("common.delete"),
      danger: true,
      onConfirm: async () => {
        setDeletingId(id);
        try {
          await deleteContract(id);
          setRows((prev) => prev?.filter((r) => r.id !== id) ?? null);
          toast.success(t("toast.contractDeleted"));
        } catch {
          toast.error(t("common.error"));
          throw new Error("delete failed");
        } finally {
          setDeletingId(null);
        }
      },
    });
  };

  return (
    <div className="space-y-6 motion-safe:animate-fadeIn">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-gray-900 md:text-3xl">{t("list.title")}</h1>
        <Link href="/upload">
          <Button variant="primary">{t("nav.upload")}</Button>
        </Link>
      </div>

      {error && (
        <div className="card-surface p-8 text-center">
          <p className="mb-3 text-danger-600">{t("common.error")}</p>
          <Button variant="secondary" onClick={load}>
            {t("common.retry")}
          </Button>
        </div>
      )}
      {!error && rows === null && <SkeletonTable rows={6} />}
      {!error && rows?.length === 0 && (
        <div className="card-surface">
          <EmptyState
            title={t("empty.contracts")}
            description={t("list.empty")}
            actionLabel={t("nav.upload")}
            onAction={() => (window.location.href = "/upload")}
          />
        </div>
      )}
      {!error && rows && rows.length > 0 && (
        <div className="max-h-[70vh] overflow-auto rounded-xl border border-gray-200 bg-white shadow-card">
          <table className="w-full text-sm">
            <thead className="sticky top-0 z-10 border-b bg-muted-50 text-start text-gray-600 shadow-sm">
              <tr>
                {(["list.col.title", "list.col.type", "list.col.party", "list.col.value", "list.col.obligations", "list.col.status"] as const).map((k) => (
                  <th key={k} className="px-4 py-3.5 text-start font-semibold">
                    {t(k)}
                  </th>
                ))}
                <th className="px-4 py-3.5 text-start font-semibold sr-only">{t("list.delete")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c, i) => (
                <tr key={c.id} className={`border-b last:border-0 hover:bg-muted-50/80 ${i % 2 === 1 ? "bg-muted-50/40" : ""}`}>
                  <td className="px-4 py-3.5">
                    <Link href={`/contracts/${c.id}`} className="font-semibold text-brand-700 hover:underline">
                      {c.title}
                    </Link>
                  </td>
                  <td className="px-4 py-3.5">
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
                  <td className="px-4 py-3.5 text-gray-700">{c.party_b ?? "—"}</td>
                  <td className="px-4 py-3.5 tabular-nums">{formatSAR(c.value_sar, lang)}</td>
                  <td className="px-4 py-3.5 text-gray-600">
                    {c.obligation_counts.pending} {t("list.pending")}
                    {c.obligation_counts.overdue > 0 && (
                      <span className="ms-2 font-semibold text-danger-600">
                        {c.obligation_counts.overdue} {t("list.overdue")}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3.5">
                    <StatusChip status={c.status} />
                  </td>
                  <td className="px-4 py-3.5 text-end">
                    <Button variant="danger" size="sm" loading={deletingId === c.id} onClick={() => onDelete(c.id)}>
                      {t("list.delete")}
                    </Button>
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
