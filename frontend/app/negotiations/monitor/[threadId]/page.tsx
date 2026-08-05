"use client";

import { useEffect, useState } from "react";

import ReviewPackagePanel from "@/components/negotiation-monitor/ReviewPackagePanel";
import EmailThreadTimeline from "@/components/negotiation-monitor/EmailThreadTimeline";
import ThreeWayComparisonPanel from "@/components/negotiation-monitor/ThreeWayComparisonPanel";
import CounterpartyMemoryCard from "@/components/negotiation-monitor/CounterpartyMemoryCard";
import RoundsRail from "@/components/negotiation-monitor/RoundsRail";
import Button from "@/components/ui/Button";
import SectionHeader from "@/components/ui/SectionHeader";
import { useCachedFetch, invalidateByPrefix } from "@/lib/cache";
import { analyzeNegotiationThread, getNegotiationMonitorThread } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function ThreadWorkspacePage({ params }: { params: { threadId: string } }) {
  const { t } = useI18n();
  const threadId = params.threadId;
  const [pkgId, setPkgId] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);

  const { data, isLoading, refresh } = useCachedFetch(`negotiation:thread:${threadId}`, () =>
    getNegotiationMonitorThread(threadId)
  );

  useEffect(() => {
    const rounds = (data?.rounds ?? []) as { review_package_id?: string | null }[];
    const last = rounds[rounds.length - 1];
    if (last?.review_package_id) setPkgId(last.review_package_id);
  }, [data]);

  async function onAnalyze() {
    setAnalyzing(true);
    try {
      const pkg = await analyzeNegotiationThread(threadId);
      setPkgId(pkg.id);
      invalidateByPrefix("negotiation:");
      refresh();
    } finally {
      setAnalyzing(false);
    }
  }

  if (isLoading && !data) {
    return <p className="text-hint">{t("common.loading")}</p>;
  }

  return (
    <div className="space-y-6">
      <SectionHeader
        title={data?.contract_title ?? t("monitor.title")}
        eyebrow={data?.counterparty_name ?? data?.counterparty_email ?? ""}
        actions={
          <Button variant="primary" onClick={onAnalyze} disabled={analyzing}>
            {t("monitor.analyze")}
          </Button>
        }
      />
      <div className="grid gap-4 lg:grid-cols-12">
        <div className="space-y-4 lg:col-span-3">
          <EmailThreadTimeline emails={(data?.emails ?? []) as never[]} />
          <RoundsRail rounds={(data?.rounds ?? []) as never[]} />
          {data?.counterparty_email ? (
            <CounterpartyMemoryCard email={data.counterparty_email as string} />
          ) : null}
        </div>
        <div className="lg:col-span-5">
          <ThreeWayComparisonPanel packageId={pkgId} />
        </div>
        <div className="lg:col-span-4">
          <ReviewPackagePanel packageId={pkgId} threadId={threadId} onSent={() => refresh()} />
        </div>
      </div>
    </div>
  );
}
