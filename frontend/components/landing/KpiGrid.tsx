"use client";

import Link from "next/link";

import Stat from "@/components/ui/Stat";
import { useI18n } from "@/lib/i18n";
import { formatPortfolioSar } from "@/lib/pipeline";

export type HomeKpiData = {
  totalContracts: number;
  portfolioValue: number;
  pendingReviews: number;
  awaitingSignature: number;
  highRisk: number;
  activeNegotiations: number;
};

export default function KpiGrid({ data }: { data: HomeKpiData }) {
  const { t, lang } = useI18n();
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <Link href="/contracts">
        <Stat label={t("home.kpi.totalContracts")} value={data.totalContracts} tone="brand" />
      </Link>
      <Stat label={t("home.kpi.portfolioValue")} value={formatPortfolioSar(data.portfolioValue, lang)} tone="default" />
      <Link href="/reviews">
        <Stat label={t("home.kpi.pendingReviews")} value={data.pendingReviews} tone="info" />
      </Link>
      <Link href="/contracts?stage=awaiting_signature">
        <Stat label={t("home.kpi.awaitingSignature")} value={data.awaitingSignature} tone="success" />
      </Link>
      <Link href="/contracts">
        <Stat label={t("home.kpi.highRisk")} value={data.highRisk} tone="danger" />
      </Link>
      <Link href="/negotiations/monitor">
        <Stat label={t("home.kpi.activeNegotiations")} value={data.activeNegotiations} tone="warning" />
      </Link>
    </div>
  );
}
