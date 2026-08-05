"use client";

import { useI18n } from "@/lib/i18n";
import type { PipelineBucketSummary } from "@/lib/pipeline";
import { formatNum } from "@/lib/utils";

import PipelineStageCard from "./PipelineStageCard";

/**
 * The contract lifecycle, read as one track.
 *
 * A spine runs behind the cards, filled up to the furthest stage that actually
 * holds contracts, so the pipeline reads as progress rather than as a row of
 * tiles. The fill is a child of a normal flex container, so it inherits the
 * writing direction and grows from the correct edge in both RTL and LTR — the
 * previous mirrored-arrow approach needed a JS direction check and a re-render.
 */
export default function PipelineRail({ buckets }: { buckets: PipelineBucketSummary[] }) {
  const { t, lang } = useI18n();

  const lastPopulated = buckets.reduce((acc, b, i) => (b.count > 0 ? i : acc), -1);
  const progressPct = buckets.length > 0 ? ((lastPopulated + 0.5) / buckets.length) * 100 : 0;
  const totalCount = buckets.reduce((sum, b) => sum + b.count, 0);

  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-extrabold tracking-tight text-slate-900 md:text-3xl">
            {t("home.pipeline.title")}
          </h2>
          <p className="mt-1.5 text-base font-medium text-slate-500">
            <span className="tnum font-bold text-emerald-600">{formatNum(totalCount, lang)}</span>
            {" · "}
            {t("home.kpi.totalContracts")}
          </p>
        </div>
      </div>

      <div className="relative">
        {/* Spine, aligned with the step numbers on the cards. */}
        <div
          className="pointer-events-none absolute inset-x-0 top-[3.4rem] hidden h-px bg-slate-200 2xl:block"
          aria-hidden
        >
          <div
            className="h-full bg-gradient-to-r from-emerald-500 to-teal-400 motion-safe:transition-[width] motion-safe:duration-700 motion-safe:ease-settle"
            style={{ width: `${Math.max(progressPct, 0)}%` }}
          />
        </div>

        <div className="stagger -mx-1 flex snap-x snap-mandatory gap-3 overflow-x-auto px-1 pb-3 2xl:grid 2xl:grid-cols-10 2xl:snap-none 2xl:overflow-visible">
          {buckets.map((bucket, i) => (
            <PipelineStageCard key={bucket.key} bucket={bucket} index={i} locale={lang} />
          ))}
        </div>
      </div>
    </section>
  );
}

export function PipelineRailSkeleton() {
  return (
    <div className="flex gap-3 overflow-hidden">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="skeleton-shimmer h-44 min-w-[10.5rem] rounded-xl2" />
      ))}
    </div>
  );
}
