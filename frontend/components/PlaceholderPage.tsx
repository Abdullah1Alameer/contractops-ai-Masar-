"use client";
import Link from "next/link";

import EmptyState from "@/components/ui/EmptyState";
import Button from "@/components/ui/Button";
import { useI18n } from "@/lib/i18n";

export default function PlaceholderPage({
  titleKey,
  contractsHref,
}: {
  titleKey: import("@/lib/i18n").TKey;
  contractsHref?: string;
}) {
  const { t } = useI18n();
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">{t(titleKey)}</h1>
      <EmptyState
        title={t("placeholder.comingSoon")}
        description={t("placeholder.comingSoonHint")}
        actionLabel={contractsHref ? t("aggregate.goContracts") : undefined}
        onAction={contractsHref ? () => (window.location.href = contractsHref) : undefined}
      />
    </div>
  );
}
