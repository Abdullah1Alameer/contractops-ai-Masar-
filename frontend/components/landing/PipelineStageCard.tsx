"use client";

import Link from "next/link";

import Button from "@/components/ui/Button";
import { useI18n } from "@/lib/i18n";
import { formatPortfolioSar, pipelineHref, type PipelineBucketSummary } from "@/lib/pipeline";
import { cn } from "@/lib/utils";

export default function PipelineStageCard({
  bucket,
  index,
  locale,
}: {
  bucket: PipelineBucketSummary;
  index: number;
  locale: string;
}) {
  const { t } = useI18n();
  return (
    <article
      className={cn(
        "surface-glass hover-lift flex min-w-[9.5rem] shrink-0 snap-center flex-col p-4 motion-safe:animate-slideUp md:min-w-0",
        "dark:border-neutral-700/60"
      )}
      style={{ animationDelay: `${Math.min(index * 40, 320)}ms` }}
    >
      <p className="text-xs font-semibold text-neutral-600 dark:text-neutral-400">{t(bucket.labelKey)}</p>
      <p className="mt-2 text-3xl font-bold tabular-nums text-neutral-900 dark:text-neutral-50">{bucket.count}</p>
      <p className="mt-1 text-xs tabular-nums text-neutral-500">{formatPortfolioSar(bucket.valueSar, locale)}</p>
      {bucket.highRiskCount > 0 ? (
        <span className="mt-2 inline-flex w-fit rounded-full bg-danger-50 px-2 py-0.5 text-[10px] font-bold text-danger-700 dark:bg-danger-950/50 dark:text-danger-300">
          {bucket.highRiskCount} {t("home.pipeline.highRisk")}
        </span>
      ) : (
        <span className="mt-2 h-5" />
      )}
      <Link href={pipelineHref(bucket.key)} className="mt-3">
        <Button variant="secondary" size="sm" className="w-full">
          {t("home.pipeline.view")}
        </Button>
      </Link>
    </article>
  );
}
