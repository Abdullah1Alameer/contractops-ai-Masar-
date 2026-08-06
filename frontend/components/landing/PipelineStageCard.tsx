"use client";

import { ArrowUpLeft } from "lucide-react";
import Link from "next/link";

import { useI18n } from "@/lib/i18n";
import { formatPortfolioSar, pipelineHref, type PipelineBucketSummary } from "@/lib/pipeline";
import { cn, formatNum } from "@/lib/utils";

/**
 * One stage in the contract lifecycle track.
 *
 * Stages holding nothing recede to a quiet outline; stages holding contracts
 * gain an emerald cap, a filled step number and a hover lift — so the eye
 * travels along the pipeline to where work actually is, instead of scanning
 * eleven identical boxes.
 */
export default function PipelineStageCard({
  bucket,
  index,
  locale,
}: {
  bucket: PipelineBucketSummary;
  index: number;
  locale: string;
}) {
  const { t, lang } = useI18n();
  const populated = bucket.count > 0;
  const atRisk = bucket.highRiskCount > 0;

  return (
    <Link
      href={pipelineHref(bucket.key)}
      style={{ "--i": index } as React.CSSProperties}
      className={cn(
        "group relative flex min-w-[10.5rem] shrink-0 snap-center flex-col overflow-hidden rounded-3xl border p-4 pt-5 md:min-w-0",
        "motion-safe:animate-riseIn motion-safe:transition-all motion-safe:duration-300 motion-safe:ease-settle",
        "focus-ring hover:shadow-[0_16px_44px_rgb(0,0,0,0.07)] motion-safe:hover:-translate-y-1",
        populated
          ? "border-white bg-white/70 shadow-[0_8px_30px_rgb(0,0,0,0.04)] backdrop-blur-2xl"
          : "border-white/70 bg-white/40 backdrop-blur-xl hover:bg-white/70",
      )}
    >
      {/* Cap bar. Colour states the stage's condition at a glance. */}
      <span
        className={cn(
          "accent-bar",
          atRisk
            ? "bg-gradient-to-r from-amber-400 to-amber-300"
            : populated
              ? "bg-gradient-to-r from-emerald-500 to-teal-400"
              : "bg-slate-200",
        )}
        aria-hidden
      />

      <div className="flex items-center justify-between gap-2">
        <span
          className={cn(
            "flex h-6 w-6 items-center justify-center rounded-lg text-[11px] font-bold tnum",
            populated
              ? "bg-gradient-to-br from-emerald-500 to-teal-400 text-white shadow-[0_4px_14px_0_rgb(5,150,105,0.39)]"
              : "bg-slate-200 text-slate-500",
          )}
          aria-hidden
        >
          {formatNum(index + 1, lang)}
        </span>
        <ArrowUpLeft
          className="h-3.5 w-3.5 text-neutral-300 opacity-0 motion-safe:transition-all motion-safe:duration-300 group-hover:text-brand-600 group-hover:opacity-100"
          aria-hidden
        />
      </div>

      <p className="mt-3 text-[11px] font-semibold tracking-wide text-slate-500">
        {t(bucket.labelKey)}
      </p>

      <p
        className={cn(
          "tnum mt-1.5 text-4xl font-extrabold leading-none tracking-tight",
          populated ? "text-slate-900" : "text-slate-300",
        )}
      >
        {formatNum(bucket.count, lang)}
      </p>

      <p className="tnum mt-2 text-[11px] font-medium text-slate-500">
        {formatPortfolioSar(bucket.valueSar, locale)}
      </p>

      {atRisk ? (
        <span className="mt-3 inline-flex w-fit items-center gap-1.5 rounded-full border border-amber-100 bg-amber-50 px-2.5 py-1 text-[10.5px] font-semibold text-amber-700">
          <span className="h-1.5 w-1.5 rounded-full bg-amber-400 motion-safe:animate-breathe" aria-hidden />
          {formatNum(bucket.highRiskCount, lang)} {t("home.pipeline.highRisk")}
        </span>
      ) : (
        <span className="mt-3 h-[26px]" aria-hidden />
      )}
    </Link>
  );
}
