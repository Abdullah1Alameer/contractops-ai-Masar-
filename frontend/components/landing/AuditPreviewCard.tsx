"use client";

import { motion, useReducedMotion } from "framer-motion";
import { AlertTriangle, FileCheck2, ScanLine, ShieldCheck, TriangleAlert } from "lucide-react";

import Guilloche from "@/components/ui/Guilloche";
import { useI18n } from "@/lib/i18n";
import { cn, formatPercent } from "@/lib/utils";

const SPRING = { type: "spring" as const, stiffness: 300, damping: 30 };

/** Clause rows in the audit preview. Widths drive the skeleton bars. */
const CLAUSES: { w: string; state: "ok" | "flag" | "risk" }[] = [
  { w: "92%", state: "ok" },
  { w: "78%", state: "ok" },
  { w: "86%", state: "flag" },
  { w: "64%", state: "ok" },
  { w: "88%", state: "risk" },
  { w: "72%", state: "ok" },
];

/**
 * The contract sheet under live AI audit.
 *
 * Stacked translucent planes give physical depth, a guilloche lattice supplies
 * the security-paper texture, and a light bar sweeps the page as the audit
 * pass. The compliance ring is inset into a soft well rather than drawn as a
 * flat stroke, and flagged clauses surface as tinted pills — the same semantic
 * colour mapping used across the app: gold = a clock is running, rose = breach.
 */
export default function AuditPreviewCard({ score = 98 }: { score?: number }) {
  const reduce = useReducedMotion();
  const { lang } = useI18n();

  const R = 42;
  const C = 2 * Math.PI * R;

  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 28, rotate: -1.5 }}
      animate={{ opacity: 1, y: 0, rotate: 0 }}
      transition={{ ...SPRING, delay: 0.15 }}
      whileHover={reduce ? undefined : { y: -8, rotate: 0.4 }}
      className="relative mx-auto w-full max-w-md"
    >
      {/* The rest of the contract set, receding behind the active sheet. */}
      <div className="absolute inset-x-7 -top-5 h-full rounded-3xl border border-white bg-white/40 backdrop-blur-2xl" aria-hidden />
      <div className="absolute inset-x-3.5 -top-2.5 h-full rounded-3xl border border-white bg-white/60 backdrop-blur-2xl" aria-hidden />

      <div className="glass-card relative overflow-hidden">
        <Guilloche className="absolute -end-16 -top-16 h-64 w-64 text-emerald-600" opacity={0.12} petals={7} />

        {/* AI audit pass. Y-axis only, so it is direction-agnostic in RTL. */}
        {!reduce && (
          <div className="pointer-events-none absolute inset-x-0 top-0 h-full overflow-hidden" aria-hidden>
            <div className="h-20 w-full bg-gradient-to-b from-transparent via-emerald-300/25 to-transparent blur-[3px] motion-safe:animate-laser" />
          </div>
        )}

        <div className="relative flex items-center justify-between gap-3 border-b border-white/80 px-6 py-4">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-400 text-white shadow-[0_4px_14px_0_rgb(5,150,105,0.39)]">
              <FileCheck2 className="h-5 w-5" aria-hidden />
            </span>
            <div>
              <p className="text-[13.5px] font-bold leading-tight text-slate-900">عقد مقاولات الباطن</p>
              <p className="mt-0.5 text-[11px] font-medium text-slate-500">
                {lang === "ar" ? "مرجع ٢٠٢٦/٠١٤٧" : "Ref. SUB-2026-0147"}
              </p>
            </div>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-100 bg-emerald-50 px-2.5 py-1 text-[10px] font-bold text-emerald-700">
            <ScanLine className="h-3 w-3" aria-hidden />
            تحليل المخاطر
          </span>
        </div>

        {/* Compliance well */}
        <div className="relative flex flex-col items-center px-6 pt-7">
          <div className="relative grid h-36 w-36 place-items-center rounded-full bg-slate-50 shadow-inner">
            <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90" aria-hidden>
              <circle cx="50" cy="50" r={R} fill="none" strokeWidth="7" className="stroke-slate-200/80" />
              <motion.circle
                cx="50"
                cy="50"
                r={R}
                fill="none"
                stroke="url(#auditRing)"
                strokeWidth="7"
                strokeLinecap="round"
                strokeDasharray={C}
                initial={reduce ? false : { strokeDashoffset: C }}
                animate={{ strokeDashoffset: C * (1 - score / 100) }}
                transition={{ duration: 1.4, ease: [0.22, 1, 0.36, 1], delay: 0.4 }}
              />
              <defs>
                <linearGradient id="auditRing" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stopColor="#059669" />
                  <stop offset="100%" stopColor="#2DD4BF" />
                </linearGradient>
              </defs>
            </svg>
            <div className="absolute grid place-items-center text-center">
              <span className="tnum text-3xl font-extrabold leading-none tracking-tight text-slate-900">
                {formatPercent(score, lang)}
              </span>
              <span className="mt-1.5 text-[11px] font-semibold text-slate-500">نسبة الامتثال</span>
            </div>
          </div>
        </div>

        {/* Clause scan */}
        <div className="relative space-y-2.5 px-6 pt-6">
          {CLAUSES.map((c, i) => (
            <motion.div
              key={i}
              initial={reduce ? false : { opacity: 0, x: 12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ ...SPRING, delay: 0.34 + i * 0.06 }}
              className="flex items-center gap-2"
            >
              <span
                className={cn(
                  "h-2 rounded-full",
                  c.state === "ok" && "bg-slate-200",
                  c.state === "flag" && "bg-gradient-to-r from-amber-400 to-amber-300",
                  c.state === "risk" && "bg-gradient-to-r from-rose-400 to-rose-300",
                )}
                style={{ width: c.w }}
              />
              {c.state !== "ok" && (
                <AlertTriangle
                  className={cn("h-3 w-3 shrink-0", c.state === "flag" ? "text-amber-500" : "text-rose-500")}
                  aria-hidden
                />
              )}
            </motion.div>
          ))}
        </div>

        {/* Findings */}
        <div className="relative flex flex-wrap items-center gap-2 px-6 pt-5">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-100 bg-amber-50 px-3 py-1.5 text-[11px] font-semibold text-amber-700">
            <TriangleAlert className="h-3 w-3" aria-hidden />
            بند غرامة تأخير يحتاج مراجعة
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-rose-100 bg-rose-50 px-3 py-1.5 text-[11px] font-semibold text-rose-700">
            مدة الإشعار أقصر من اللائحة
          </span>
        </div>

        <div className="relative mt-5 flex flex-wrap items-center gap-2 border-t border-white/80 bg-white/50 px-6 py-4">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-100 bg-emerald-50 px-3 py-1.5 text-[11px] font-semibold text-emerald-700">
            <ShieldCheck className="h-3 w-3" aria-hidden />
            مطابق للوائح الأنظمة السعودية
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-teal-100 bg-teal-50 px-3 py-1.5 text-[11px] font-semibold text-teal-700">
            جاهز للتوثيق
          </span>
        </div>
      </div>
    </motion.div>
  );
}
