"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import CategoryBadge from "@/components/CategoryBadge";
import { useConfirm } from "@/components/feedback/ConfirmDialog";
import { useToast } from "@/components/feedback/ToastProvider";
import { useShell } from "@/components/shell/ShellContext";
import StatusChip from "@/components/StatusChip";
import TypeBadge from "@/components/TypeBadge";
import Button from "@/components/ui/Button";
import ActionMenu from "@/components/ui/ActionMenu";
import StageBadge from "@/components/ui/StageBadge";
import DataTable, { type DataTableColumn } from "@/components/ui/DataTable";
import EmptyState from "@/components/ui/EmptyState";
import { SkeletonTable } from "@/components/ui/Skeleton";
import { useCachedFetch, invalidateByPrefix } from "@/lib/cache";
import { api, deleteContract } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { ContractListItem } from "@/lib/types";
import { formatSAR } from "@/lib/utils";

const PAGE_SIZE = 25;

type SortKey = "title" | "party";

export default function ContractsPage() {
  return (
    <Suspense fallback={<SkeletonTable rows={6} />}>
      <ContractsPageContent />
    </Suspense>
  );
}

function ContractsPageContent() {
  const { t, lang } = useI18n();
  const router = useRouter();
  const searchParams = useSearchParams();
  const stageFilter = searchParams.get("stage");
  const { setPrimaryAction } = useShell();
  const { confirm } = useConfirm();
  const toast = useToast();
  const { data: rows, isLoading, isValidating, error, refresh, mutate } = useCachedFetch(
    "contracts:list",
    () => api<ContractListItem[]>("/api/contracts?include=workflow_summary")
  );
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [statusChip, setStatusChip] = useState<string | null>(null);
  const [typeChip, setTypeChip] = useState<string | null>(null);
  const [sort, setSort] = useState<SortKey>("title");
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  useEffect(() => {
    setPrimaryAction(
      <Link href="/upload">
        <Button variant="primary" size="sm">
          {t("nav.upload")}
        </Button>
      </Link>
    );
    return () => setPrimaryAction(null);
  }, [setPrimaryAction, t]);

  const filtered = useMemo(() => {
    if (!rows) return [];
    let list = rows;
    if (stageFilter) list = list.filter((r) => (r.stage ?? "negotiation") === stageFilter);
    if (statusChip) list = list.filter((r) => r.status === statusChip);
    if (typeChip) list = list.filter((r) => r.type === typeChip);
    if (q.trim()) {
      const needle = q.trim().toLowerCase();
      list = list.filter(
        (r) =>
          r.title.toLowerCase().includes(needle) ||
          (r.party_b ?? "").toLowerCase().includes(needle)
      );
    }
    list = [...list].sort((a, b) => {
      if (sort === "title") return a.title.localeCompare(b.title);
      return (a.party_b ?? "").localeCompare(b.party_b ?? "");
    });
    return list;
  }, [rows, stageFilter, statusChip, typeChip, q, sort]);

  const pageRows = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));

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
          mutate((prev) => (prev ?? []).filter((r) => r.id !== id));
          invalidateByPrefix("dashboard:");
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

  const bulkExport = () => {
    const picked = filtered.filter((r) => selected.has(r.id));
    const blob = new Blob([JSON.stringify(picked, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "contracts-export.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const bulkDelete = async () => {
    if (selected.size === 0) return;
    await confirm({
      title: t("confirm.deleteContract.title"),
      body: t("confirm.deleteContract.body"),
      confirmLabel: t("common.delete"),
      danger: true,
      onConfirm: async () => {
        for (const id of Array.from(selected)) {
          await deleteContract(id);
        }
        mutate((prev) => (prev ?? []).filter((r) => !selected.has(r.id)));
        invalidateByPrefix("dashboard:");
        setSelected(new Set());
        toast.success(t("common.deleted"));
      },
    });
  };

  const columns: DataTableColumn<ContractListItem>[] = [
    {
      id: "title",
      header: t("list.col.title"),
      cell: (c) => (
        <Link href={`/contracts/${c.id}`} className="font-semibold text-brand-700 hover:underline" onClick={(e) => e.stopPropagation()}>
          {c.title}
        </Link>
      ),
    },
    {
      id: "party",
      header: t("list.col.party"),
      cell: (c) => c.party_b ?? "—",
    },
    {
      id: "type",
      header: t("list.col.type"),
      cell: (c) => (
        <div className="flex flex-wrap gap-1">
          {c.type && <TypeBadge type={c.type} />}
          <CategoryBadge category={c.contract_category} />
        </div>
      ),
    },
    {
      id: "version",
      header: t("versions.col.version"),
      cell: (c) => `${c.current_version_number ?? 1}/${c.total_versions ?? 1}`,
    },
    {
      id: "stage",
      header: t("list.col.stage"),
      cell: (c) => <StageBadge stage={c.stage} />,
    },
    {
      id: "owner",
      header: t("list.col.owner"),
      cell: (c) => c.created_by ?? "—",
    },
    {
      id: "created",
      header: t("list.col.created"),
      cell: (c) => c.created_at?.slice(0, 10) ?? "—",
    },
    {
      id: "status",
      header: t("list.col.status"),
      cell: (c) => <StatusChip status={c.status} />,
    },
    {
      id: "value",
      header: t("list.col.value"),
      cell: (c) => formatSAR(c.value_sar, lang),
      className: "tabular-nums",
    },
    {
      id: "obligations",
      header: t("list.col.obligations"),
      cell: (c) => (
        <>
          {c.obligation_counts.pending} {t("list.pending")}
          {c.obligation_counts.overdue > 0 && (
            <span className="ms-1 text-danger-600">{c.obligation_counts.overdue}</span>
          )}
        </>
      ),
    },
    {
      id: "actions",
      header: "",
      cell: (c) => (
        <ActionMenu
          items={[
            { id: "open", label: t("versions.open"), onSelect: () => router.push(`/contracts/${c.id}`) },
            {
              id: "del",
              label: t("list.delete"),
              danger: true,
              onSelect: () => onDelete(c.id),
            },
          ]}
        />
      ),
    },
  ];

  const statusOptions = ["ready", "needs_review", "processing", "failed"] as const;

  return (
    <div className="space-y-4 motion-safe:animate-fadeIn">
      <h1 className="text-2xl font-bold text-gray-900">{t("list.title")}</h1>

      <div className="flex flex-wrap items-center gap-2">
        <input
          className="min-w-[200px] flex-1 rounded-lg border border-gray-200 px-3 py-2 text-sm"
          placeholder={t("shell.search")}
          value={q}
          onChange={(e) => { setQ(e.target.value); setPage(0); }}
        />
        <select
          className="rounded-lg border border-gray-200 px-3 py-2 text-sm"
          value={sort}
          onChange={(e) => setSort(e.target.value as SortKey)}
          aria-label={t("common.sort")}
        >
          <option value="title">{t("list.col.title")}</option>
          <option value="party">{t("list.col.party")}</option>
        </select>
        {selected.size > 0 && (
          <>
            <Button variant="danger" size="sm" onClick={bulkDelete}>
              {t("common.delete")} ({selected.size})
            </Button>
            <Button variant="secondary" size="sm" onClick={bulkExport}>
              {t("list.exportSelected")}
            </Button>
          </>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        <span className="text-xs font-semibold text-gray-500">{t("common.filters")}:</span>
        {stageFilter && (
          <button type="button" className="chip chip-active" onClick={() => router.push("/contracts")}>
            {stageFilter} ×
          </button>
        )}
        {statusOptions.map((s) => (
          <button
            key={s}
            type="button"
            className={statusChip === s ? "chip chip-active" : "chip"}
            onClick={() => { setStatusChip(statusChip === s ? null : s); setPage(0); }}
          >
            {t(`status.${s}` as import("@/lib/i18n").TKey)}
          </button>
        ))}
        <button
          type="button"
          className={typeChip === "main" ? "chip chip-active" : "chip"}
          onClick={() => { setTypeChip(typeChip === "main" ? null : "main"); setPage(0); }}
        >
          {t("type.main")}
        </button>
        <button
          type="button"
          className={typeChip === "subcontract" ? "chip chip-active" : "chip"}
          onClick={() => { setTypeChip(typeChip === "subcontract" ? null : "subcontract"); setPage(0); }}
        >
          {t("type.subcontract")}
        </button>
        {(statusChip || typeChip || q) && (
          <button type="button" className="chip" onClick={() => { setStatusChip(null); setTypeChip(null); setQ(""); setPage(0); }}>
            {t("common.clear")}
          </button>
        )}
      </div>

      {error && (
        <div className="card-surface p-8 text-center">
          <p className="mb-3 text-danger-600">{t("common.error")}</p>
          <Button variant="secondary" onClick={() => refresh()}>
            {t("common.retry")}
          </Button>
        </div>
      )}
      {!error && isLoading && !rows && <SkeletonTable rows={6} />}
      {!error && rows?.length === 0 && (
        <EmptyState title={t("empty.contracts")} actionLabel={t("nav.upload")} onAction={() => (window.location.href = "/upload")} />
      )}
      {!error && rows && filtered.length === 0 && rows.length > 0 && (
        <p className="text-sm text-gray-600">{t("list.empty")}</p>
      )}
      {!error && filtered.length > 0 && (
        <>
          <DataTable
            columns={columns}
            rows={pageRows}
            getRowKey={(c) => c.id}
            onRowClick={(c) => router.push(`/contracts/${c.id}`)}
            selectable
            selectedKeys={selected}
            onSelectionChange={setSelected}
          />
          <div className="flex items-center justify-between text-sm text-gray-600">
            <span>
              {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, filtered.length)} / {filtered.length}
            </span>
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
                ←
              </Button>
              <Button variant="secondary" size="sm" disabled={page >= pageCount - 1} onClick={() => setPage((p) => p + 1)}>
                →
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
