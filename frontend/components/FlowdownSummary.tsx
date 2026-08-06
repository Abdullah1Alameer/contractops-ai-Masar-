"use client";
import { motion, useReducedMotion } from "framer-motion";
import { AlertOctagon, GitCompareArrows, ShieldAlert, ShieldCheck } from "lucide-react";

import { useI18n } from "@/lib/i18n";
import type { FlowdownSummary as FlowdownSummaryType } from "@/lib/types";
import { cn, formatNum, formatPercent } from "@/lib/utils";

const SPRING = { type: "spring" as const, stiffness: 300, damping: 30 };

/** Counter tile. Zero recedes; anything above zero takes its warning colour. */
function CountTile({
  icon: Icon,
  label,
  count,
  tone,
  lang,
  delay,
}: {
  icon: typeof ShieldAlert;
  label: string;
  count: number;
  tone: "rose" | "amber";
  lang: "ar" | "en";
  delay: number;
}) {
  const reduce = useReducedMotion();
  const hot = count > 0;

  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ ...SPRING, delay }}
      className="glass-card glass-card-hover group relative overflow-hidden p-5"
    >
      <span
        className={cn(
          "flex h-9 w-9 items-center justify-center rounded-xl shadow-inner transition-transform duration-300 motion-safe:ease-emphasis group-hover:scale-110",
          !hot && "bg-slate-100 text-slate-400",
          hot && tone === "rose" && "bg-gradient-to-br from-rose-50 to-amber-50 text-rose-600",
          hot && tone === "amber" && "bg-gradient-to-br from-amber-50 to-yellow-50 text-amber-600",
        )}
      >
        <Icon className="h-[18px] w-[18px]" strokeWidth={1.9} aria-hidden />
      </span>
      <p
        className={cn(
          "tnum mt-3 text-3xl font-extrabold leading-none tracking-tight",
          !hot && "text-slate-300",
          hot && tone === "rose" && "text-rose-600",
          hot && tone === "amber" && "text-amber-600",
        )}
      >
        {formatNum(count, lang)}
      </p>
      <p className="mt-2 text-xs font-medium leading-snug text-slate-500">{label}</p>
    </motion.div>
  );
}

/**
 * Flow-down risk header.
 *
 * The overall risk score gets a dial rather than a number in a box — it is the
 * one figure that should be readable across a room during a review meeting.
 * Coverage sits beside it as a bar, and the three defect counts follow as
 * tiles that stay grey until they actually have something to report.
 */
export default function FlowdownSummary({ summary }: { summary: FlowdownSummaryType }) {
  const { t, lang } = useI18n();
  const reduce = useReducedMotion();

  const risk = summary.overall_risk_score;
  const cov = summary.coverage_pct;

  const riskTone = risk >= 60 ? "rose" : risk >= 30 ? "amber" : "emerald";
  const covTone = cov >= 80 ? "emerald" : cov >= 50 ? "amber" : "rose";

  const R = 46;
  const C = 2 * Math.PI * R;

  const gradId = `riskDial-${riskTone}`;
  const stops =
    riskTone === "rose"
      ? ["#E11D48", "#FB7185"]
      : riskTone === "amber"
        ? ["#D97706", "#FBBF24"]
        : ["#059669", "#2DD4BF"];

  return (
    <div className="mb-6 grid gap-4 lg:grid-cols-12">
      {/* Risk dial */}
      <motion.div
        initial={reduce ? false : { opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={SPRING}
        className="glass-card relative overflow-hidden p-6 lg:col-span-5"
      >
        <div className="flex items-center gap-6">
          <div className="relative grid h-32 w-32 shrink-0 place-items-center rounded-full bg-slate-50 shadow-inner">
            <svg viewBox="0 0 110 110" className="h-full w-full -rotate-90" aria-hidden>
              <circle cx="55" cy="55" r={R} fill="none" strokeWidth="8" className="stroke-slate-200/80" />
              <motion.circle
                cx="55"
                cy="55"
                r={R}
                fill="none"
                stroke={`url(#${gradId})`}
                strokeWidth="8"
                strokeLinecap="round"
                strokeDasharray={C}
                initial={reduce ? false : { strokeDashoffset: C }}
                animate={{ strokeDashoffset: C * (1 - Math.min(Math.max(risk, 0), 100) / 100) }}
                transition={{ duration: 1.3, ease: [0.22, 1, 0.36, 1], delay: 0.2 }}
              />
              <defs>
                <linearGradient id={gradId} x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stopColor={stops[0]} />
                  <stop offset="100%" stopColor={stops[1]} />
                </linearGradient>
              </defs>
            </svg>
            <span className="tnum absolute text-2xl font-extrabold tracking-tight text-slate-900">
              {formatPercent(risk, lang)}
            </span>
          </div>

          <div className="min-w-0">
            <p className="text-sm font-extrabold tracking-tight text-slate-900">
              {t("flowdown.summary.risk")}
            </p>
            <span
              className={cn(
                "mt-2 inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold",
                riskTone === "rose" && "border-rose-100 bg-rose-50 text-rose-700",
                riskTone === "amber" && "border-amber-100 bg-amber-50 text-amber-700",
                riskTone === "emerald" && "border-emerald-100 bg-emerald-50 text-emerald-700",
              )}
            >
              {riskTone === "emerald" ? (
                <ShieldCheck className="h-3 w-3" aria-hidden />
              ) : (
                <ShieldAlert className="h-3 w-3" aria-hidden />
              )}
              {riskTone === "rose" ? "مخاطر مرتفعة" : riskTone === "amber" ? "مخاطر متوسطة" : "مخاطر منخفضة"}
            </span>
          </div>
        </div>

        {/* Coverage */}
        <div className="mt-6">
          <div className="flex items-baseline justify-between gap-2">
            <p className="text-xs font-semibold text-slate-500">{t("flowdown.summary.coverage")}</p>
            <p className="tnum text-sm font-extrabold text-slate-900">{formatPercent(cov, lang)}</p>
          </div>
          <div className="mt-2 h-2.5 overflow-hidden rounded-full bg-slate-100 shadow-inner">
            <motion.div
              initial={reduce ? false : { width: 0 }}
              animate={{ width: `${Math.min(Math.max(cov, 0), 100)}%` }}
              transition={{ duration: 1.1, ease: [0.22, 1, 0.36, 1], delay: 0.35 }}
              className={cn(
                "h-full rounded-full",
                covTone === "emerald" && "bg-gradient-to-r from-emerald-500 to-teal-400",
                covTone === "amber" && "bg-gradient-to-r from-amber-400 to-amber-300",
                covTone === "rose" && "bg-gradient-to-r from-rose-500 to-rose-400",
              )}
            />
          </div>
        </div>
      </motion.div>

      {/* Defect counts */}
      <div className="grid gap-4 sm:grid-cols-3 lg:col-span-7">
        <CountTile
          icon={AlertOctagon}
          label={t("flowdown.summary.critical")}
          count={summary.critical_count}
          tone="rose"
          lang={lang}
          delay={0.08}
        />
        <CountTile
          icon={GitCompareArrows}
          label={t("flowdown.summary.missing")}
          count={summary.missing_count}
          tone="amber"
          lang={lang}
          delay={0.14}
        />
        <CountTile
          icon={ShieldAlert}
          label={t("flowdown.summary.conflict")}
          count={summary.conflict_count}
          tone="rose"
          lang={lang}
          delay={0.2}
        />
      </div>
    </div>
  );
}
