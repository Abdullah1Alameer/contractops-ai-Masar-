"use client";
import Link from "next/link";
import { useEffect, useState } from "react";

import EmptyState from "@/components/ui/EmptyState";
import { Card, CardBody } from "@/components/ui/Card";
import { SkeletonTable } from "@/components/ui/Skeleton";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { ContractListItem } from "@/lib/types";

export default function VersionsHubPage() {
  const { t } = useI18n();
  const [rows, setRows] = useState<ContractListItem[] | null>(null);

  useEffect(() => {
    api<ContractListItem[]>("/api/contracts")
      .then((all) => all.filter((c) => (c.total_versions ?? 1) > 1))
      .then(setRows)
      .catch(() => setRows([]));
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">{t("nav.versions")}</h1>
      {rows === null ? (
        <SkeletonTable rows={4} />
      ) : rows.length === 0 ? (
        <EmptyState
          title={t("versions.empty")}
          actionLabel={t("nav.contracts")}
          onAction={() => (window.location.href = "/contracts")}
        />
      ) : (
        <Card>
          <CardBody className="divide-y divide-gray-100 p-0">
            {rows.map((c) => (
              <Link key={c.id} href={`/contracts/${c.id}`} className="flex items-center justify-between px-4 py-3 hover:bg-muted-50">
                <span className="font-semibold">{c.title}</span>
                <span className="text-sm text-gray-600">
                  v{c.current_version_number ?? 1}/{c.total_versions ?? 1}
                </span>
              </Link>
            ))}
          </CardBody>
        </Card>
      )}
    </div>
  );
}
