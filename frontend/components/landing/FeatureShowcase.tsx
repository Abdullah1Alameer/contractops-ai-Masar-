"use client";

import { motion, useReducedMotion } from "framer-motion";
import { GitCompareArrows, ScanText, TimerReset } from "lucide-react";
import Link from "next/link";

import Guilloche from "@/components/ui/Guilloche";
import { useI18n } from "@/lib/i18n";
import { formatNum } from "@/lib/utils";

const SPRING = { type: "spring" as const, stiffness: 300, damping: 30 };

/* ------------------------------------------------------------------ *
 * Each feature gets a purpose-built visual rather than a stock icon —
 * the diagram is the explanation.
 * ------------------------------------------------------------------ */

/** Flow-Down X-Ray: a clause present upstream, missing downstream. */
function FlowDownVisual() {
  const reduce = useReducedMotion();
  const rows = [
    { main: true, sub: true },
    { main: true, sub: true },
    { main: true, sub: false }, // the gap this feature exists to find
    { main: true, sub: true },
  ];

  return (
    <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2.5">
      <div className="space-y-2">
        <p className="text-[10px] font-bold text-slate-400">العقد الرئيسي</p>
        {rows.map((r, i) => (
          <motion.span
            key={i}
            initial={reduce ? false : { opacity: 0, scaleX: 0.6 }}
            whileInView={{ opacity: 1, scaleX: 1 }}
            viewport={{ once: true }}
            transition={{ ...SPRING, delay: 0.1 + i * 0.07 }}
            className="block h-2 origin-[inline-start] rounded-full bg-gradient-to-r from-emerald-400 to-teal-300"
          />
        ))}
      </div>

      <div className="flex flex-col items-center gap-2 pt-5">
        {rows.map((r, i) => (
          <span
            key={i}
            className={
              r.sub
                ? "h-2 w-2 rounded-full bg-slate-200"
                : "h-2 w-2 rounded-full bg-rose-500 shadow-[0_0_10px_rgb(244,63,94,0.7)] motion-safe:animate-breathe"
            }
            aria-hidden
          />
        ))}
      </div>

      <div className="space-y-2">
        <p className="text-[10px] font-bold text-slate-400">عقد الباطن</p>
        {rows.map((r, i) => (
          <motion.span
            key={i}
            initial={reduce ? false : { opacity: 0, scaleX: 0.6 }}
            whileInView={{ opacity: 1, scaleX: r.sub ? 1 : 0.35 }}
            viewport={{ once: true }}
            transition={{ ...SPRING, delay: 0.16 + i * 0.07 }}
            className={
              r.sub
                ? "block h-2 origin-[inline-start] rounded-full bg-slate-200"
                : "block h-2 origin-[inline-start] rounded-full border border-dashed border-rose-300 bg-rose-50"
            }
          />
        ))}
      </div>
    </div>
  );
}

/** Time-Bar Guardian: notice windows, each closing at its own rate. */
function TimeBarVisual({ lang }: { lang: "ar" | "en" }) {
  const reduce = useReducedMotion();
  const bars = [
    { days: 21, pct: 0.75, tone: "emerald" },
    { days: 14, pct: 0.5, tone: "amber" },
    { days: 3, pct: 0.12, tone: "rose" },
  ] as const;

  return (
    <div className="space-y-3">
      {bars.map((b, i) => (
        <div key={i} className="flex items-center gap-3">
          <span
            className={
              "tnum w-9 shrink-0 text-end text-sm font-extrabold " +
              (b.tone === "emerald"
                ? "text-emerald-600"
                : b.tone === "amber"
                  ? "text-amber-600"
                  : "text-rose-600")
            }
          >
            {formatNum(b.days, lang)}
          </span>
          <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-slate-100 shadow-inner">
            <motion.div
              initial={reduce ? false : { width: 0 }}
              whileInView={{ width: `${b.pct * 100}%` }}
              viewport={{ once: true }}
              transition={{ duration: 1.1, ease: [0.22, 1, 0.36, 1], delay: 0.15 + i * 0.12 }}
              className={
                "h-full rounded-full " +
                (b.tone === "emerald"
                  ? "bg-gradient-to-r from-emerald-500 to-teal-400"
                  : b.tone === "amber"
                    ? "bg-gradient-to-r from-amber-400 to-amber-300"
                    : "bg-gradient-to-r from-rose-500 to-rose-400")
              }
            />
          </div>
        </div>
      ))}
      <p className="pt-1 text-[10px] font-semibold text-slate-400">الأيام المتبقية قبل سقوط الحق</p>
    </div>
  );
}

/** AI Reader: prose resolving into structured fields. */
function ReaderVisual() {
  const reduce = useReducedMotion();
  const fields = ["الأطراف", "القيمة", "مدة الإشعار", "الضمان"];

  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        {["88%", "72%", "94%"].map((w, i) => (
          <span key={i} className="block h-1.5 rounded-full bg-slate-200" style={{ width: w }} />
        ))}
      </div>
      <div className="flex flex-wrap gap-1.5 pt-1">
        {fields.map((f, i) => (
          <motion.span
            key={f}
            initial={reduce ? false : { opacity: 0, y: 8, scale: 0.9 }}
            whileInView={{ opacity: 1, y: 0, scale: 1 }}
            viewport={{ once: true }}
            transition={{ ...SPRING, delay: 0.2 + i * 0.08 }}
            className="rounded-full border border-emerald-100 bg-emerald-50 px-2.5 py-1 text-[10.5px] font-semibold text-emerald-700"
          >
            {f}
          </motion.span>
        ))}
      </div>
    </div>
  );
}

export default function FeatureShowcase() {
  const reduce = useReducedMotion();
  const { lang } = useI18n();

  const features = [
    {
      icon: GitCompareArrows,
      title: "الأشعة السينية لتدفق الالتزامات",
      body: "مقارنة العقد الرئيسي بعقود الباطن بندًا ببند، وكشف الالتزامات التي لم تُمرَّر — قبل أن تتحول إلى مسؤولية منفردة.",
      visual: <FlowDownVisual />,
      href: "/flowdown",
    },
    {
      icon: TimerReset,
      title: "حارس المُدد النظامية",
      body: "قراءة مدة الإشعار من كل عقد على حدة وبدء العدّ التنازلي تلقائيًا. تجاوز المدة لا يعني غرامة، بل سقوط المطالبة كاملة.",
      visual: <TimeBarVisual lang={lang} />,
      href: "/dashboard",
    },
    {
      icon: ScanText,
      title: "القارئ الذكي للعقود",
      body: "استخراج الأطراف والقيم والمُدد والضمانات من مستندات عربية أو إنجليزية، مع ربط كل حقل ببنده الأصلي في المستند.",
      visual: <ReaderVisual />,
      href: "/upload",
    },
  ];

  return (
    <section className="relative">
      <div className="mb-7">
        <h2 className="text-2xl font-extrabold tracking-tight text-slate-900 md:text-3xl">
          قدرات المنصة الأساسية
        </h2>
        <p className="mt-2 max-w-2xl text-base font-medium text-slate-500">
          ثلاث طبقات حماية تعمل على كل عقد منذ لحظة رفعه وحتى إغلاقه
        </p>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        {features.map((f, i) => {
          const Icon = f.icon;
          return (
            <motion.div
              key={f.title}
              initial={reduce ? false : { opacity: 0, y: 28 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ ...SPRING, delay: i * 0.1 }}
            >
              <Link
                href={f.href}
                className="glass-card glass-card-hover focus-ring group relative flex h-full flex-col overflow-hidden p-7"
              >
                <Guilloche
                  className="absolute -end-20 -top-20 h-56 w-56 text-emerald-600 opacity-0 transition-opacity duration-500 group-hover:opacity-100"
                  opacity={0.16}
                  petals={7}
                />

                <span className="relative flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-400 text-white shadow-[0_4px_14px_0_rgb(5,150,105,0.39)] transition-transform duration-300 motion-safe:ease-emphasis group-hover:scale-110 group-hover:rotate-6">
                  <Icon className="h-6 w-6" strokeWidth={1.9} aria-hidden />
                </span>

                <h3 className="relative mt-5 text-lg font-extrabold leading-snug tracking-tight text-slate-900">
                  {f.title}
                </h3>
                <p className="relative mt-3 text-sm leading-[1.9] text-slate-500">{f.body}</p>

                <div className="relative mt-auto pt-7">{f.visual}</div>
              </Link>
            </motion.div>
          );
        })}
      </div>
    </section>
  );
}
