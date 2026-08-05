"use client";
import Link from "next/link";
import { useEffect, useState } from "react";

import { ReviewStatusBadge } from "@/components/SendForReviewDialog";
import EmptyState from "@/components/ui/EmptyState";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { fetchReviewsSummary } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { ContractListItem, ReviewRequestRow } from "@/lib/types";

export default function ReviewsPage() {
  const { t } = useI18n();
  const [items, setItems] = useState<ReviewRequestRow[] | null>(null);

  useEffect(() => {
    fetchReviewsSummary()
      .then((r) => setItems(r.items ?? []))
      .catch(() => setItems([]));
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">{t("nav.reviews")}</h1>
      {items === null ? (
        <SkeletonCard />
      ) : items.length === 0 ? (
        <EmptyState title={t("review.dashboard.empty")} actionLabel={t("nav.contracts")} onAction={() => (window.location.href = "/contracts")} />
      ) : (
        <Card>
          <CardHeader>
            <h2 className="font-bold">{t("review.dashboard.title")}</h2>
          </CardHeader>
          <CardBody className="pt-0">
            <ul className="divide-y divide-gray-100">
              {items.map((r) => (
                <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                  <div>
                    <Link href={`/contracts/${r.contract_id}`} className="text-sm font-semibold text-brand-700 hover:underline">
                      {r.contract_title ?? r.contract_id}
                    </Link>
                    <p className="text-xs text-gray-500">
                      {t("review.dashboard.recipient")}: {r.recipient_name}
                    </p>
                  </div>
                  <ReviewStatusBadge status={r.status} />
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>
      )}
    </div>
  );
}
