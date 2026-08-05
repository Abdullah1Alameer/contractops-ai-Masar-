"use client";

import { useEffect, useState } from "react";

import SectionHeader from "@/components/ui/SectionHeader";
import { useI18n } from "@/lib/i18n";
import type { PipelineBucketSummary } from "@/lib/pipeline";

import PipelineStageCard from "./PipelineStageCard";

function ConnectorArrow({ rtl }: { rtl: boolean }) {
  return (
    <div className="hidden shrink-0 items-center justify-center px-0.5 md:flex" aria-hidden>
      <svg
        className="h-4 w-4 text-neutral-300 dark:text-neutral-600"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      >
        {rtl ? <path d="M15 6l-6 6 6 6" /> : <path d="M9 6l6 6-6 6" />}
      </svg>
    </div>
  );
}

export default function PipelineRail({ buckets }: { buckets: PipelineBucketSummary[] }) {
  const { t, lang } = useI18n();
  const [rtl, setRtl] = useState(true);

  useEffect(() => {
    setRtl(document.documentElement.dir === "rtl");
  }, []);

  return (
    <section className="space-y-4">
      <SectionHeader title={t("home.pipeline.title")} />
      <div className="-mx-1 flex gap-2 overflow-x-auto pb-2 snap-x snap-mandatory px-1 2xl:grid 2xl:grid-cols-10 2xl:overflow-visible 2xl:snap-none">
        {buckets.map((bucket, i) => (
          <div key={bucket.key} className="flex shrink-0 items-stretch 2xl:contents">
            <PipelineStageCard bucket={bucket} index={i} locale={lang} />
            {i < buckets.length - 1 ? <ConnectorArrow rtl={rtl} /> : null}
          </div>
        ))}
      </div>
    </section>
  );
}

export function PipelineRailSkeleton() {
  return (
    <div className="flex gap-3 overflow-hidden">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="surface-glass h-40 min-w-[9.5rem] skeleton-shimmer" />
      ))}
    </div>
  );
}
