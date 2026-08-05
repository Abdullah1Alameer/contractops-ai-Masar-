"use client";
import Link from "next/link";
import { useEffect, useState } from "react";

import EmptyState from "@/components/ui/EmptyState";
import { Card, CardBody } from "@/components/ui/Card";
import { SkeletonTable } from "@/components/ui/Skeleton";
import StatusChip from "@/components/StatusChip";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { ContractListItem } from "@/lib/types";

export default function StageAggregatePage({
  titleKey,
  stage,
}: {
  titleKey: import("@/lib/i18n").TKey;
  stage: string;
}) {
  const { t } = useI18n();
  const [rows, setRows] = useState<ContractListItem[] | null>(null);

  useEffect(() => {
    api<ContractListItem[]>("/api/contracts")
      .then((all) => all.filter((c) => (c.stage ?? "negotiation") === stage))
      .then(setRows)
      .catch(() => setRows([]));
  }, [stage]);

  const href = `/contracts?stage=${encodeURIComponent(stage)}`;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">{t(titleKey)}</h1>
        <Link href={href} className="text-sm font-semibold text-brand-700 hover:underline">
          {t("common.viewAll")}
        </Link>
      </div>
      {rows === null ? (
        <SkeletonTable rows={4} />
      ) : rows.length === 0 ? (
        <EmptyState title={t("common.empty")} actionLabel={t("aggregate.goContracts")} onAction={() => (window.location.href = href)} />
      ) : (
        <Card>
          <CardBody className="divide-y divide-gray-100 p-0">
            {rows.slice(0, 20).map((c) => (
              <Link key={c.id} href={`/contracts/${c.id}`} className="flex items-center justify-between px-4 py-3 hover:bg-muted-50">
                <span className="font-semibold text-gray-900">{c.title}</span>
                <StatusChip status={c.status} />
              </Link>
            ))}
          </CardBody>
        </Card>
      )}
    </div>
  );
}
