"use client";

import { motion, useReducedMotion } from "framer-motion";
import { ArrowUpLeft, BarChart3, Clock4, FileCheck2, Sparkles } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import AuditPreviewCard from "@/components/landing/AuditPreviewCard";
import Logo from "@/components/Logo";
import Guilloche from "@/components/ui/Guilloche";
import { useI18n } from "@/lib/i18n";
import { formatNum } from "@/lib/utils";

const SPRING = { type: "spring" as const, stiffness: 300, damping: 30 };

/**
 * Counts a number up once, respecting reduced-motion.
 *
 * Formatting goes through the locale numeral system, so the Arabic UI counts
 * in ٠١٢٣٤٥٦٧٨٩ with ٫ / ٬ separators rather than Latin digits.
 */
function useCountUp(target: number, lang: "ar" | "en", decimals = 0, duration = 1600) {
  const reduce = useReducedMotion();
  const [value, setValue] = useState(reduce ? target : 0);

  useEffect(() => {
    if (reduce) {
      setValue(target);
      return;
    }
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const p = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      setValue(Number((target * eased).toFixed(decimals)));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, decimals, duration, reduce]);

  return formatNum(value, lang, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function Metric({
  icon: Icon,
  target,
  lang,
  decimals = 0,
  suffix,
  label,
  delay,
}: {
  icon: typeof FileCheck2;
  target: number;
  lang: "ar" | "en";
  decimals?: number;
  suffix?: string;
  label: string;
  delay: number;
}) {
  const reduce = useReducedMotion();
  const value = useCountUp(target, lang, decimals);

  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 20, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ ...SPRING, delay }}
      whileHover={reduce ? undefined : { y: -6, transition: { ...SPRING, delay: 0 } }}
      className="glass-card group relative overflow-hidden p-5"
    >
      <span
        className="pointer-events-none absolute inset-0 bg-gradient-to-t from-emerald-50/80 to-transparent opacity-0 transition-opacity duration-500 group-hover:opacity-100"
        aria-hidden
      />
      <span className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-50 to-teal-50 text-emerald-600 shadow-inner transition-transform duration-300 motion-safe:ease-emphasis group-hover:scale-110 group-hover:rotate-6">
        <Icon className="h-4 w-4" strokeWidth={2} aria-hidden />
      </span>
      <p className="tnum relative mt-4 text-3xl font-extrabold leading-none tracking-tight text-slate-900">
        {value}
        {suffix ? <span className="ms-1 text-lg font-bold text-emerald-600">{suffix}</span> : null}
      </p>
      <p className="relative mt-2 text-xs font-medium leading-snug text-slate-500">{label}</p>
    </motion.div>
  );
}

/**
 * Hero for ميثاق / MITHAQ.
 *
 * Frosted glass over the shell's ambient light field. All decoration is
 * aria-hidden and positioned with logical inset-inline, so the composition
 * follows RTL without a mirrored variant.
 */
export default function HeroGreeting() {
  const reduce = useReducedMotion();
  const { lang } = useI18n();

  return (
    <section className="glass-card relative isolate overflow-hidden">
      <div className="pointer-events-none absolute inset-0 -z-10" aria-hidden>
        {/* Organic light volumes inside the pane itself, so the glass has
            something to refract even where the page field is thin. */}
        <div className="absolute -top-24 end-[-4rem] h-80 w-80 rounded-full bg-emerald-100/50 blur-[100px]" />
        <div className="absolute -bottom-32 start-[-4rem] h-80 w-80 rounded-full bg-blue-50/70 blur-[120px]" />
        <div
          className="absolute inset-0 opacity-60"
          style={{
            backgroundImage:
              "linear-gradient(to right, rgb(15 23 42 / 0.025) 1px, transparent 1px), linear-gradient(to bottom, rgb(15 23 42 / 0.025) 1px, transparent 1px)",
            backgroundSize: "56px 56px",
            maskImage: "radial-gradient(120% 90% at 70% 0%, black 0%, transparent 72%)",
            WebkitMaskImage: "radial-gradient(120% 90% at 70% 0%, black 0%, transparent 72%)",
          }}
        />
        <Guilloche
          className="absolute -bottom-40 start-[-10rem] h-[34rem] w-[34rem] text-emerald-700"
          opacity={0.08}
          petals={9}
        />
      </div>

      <div className="grid items-center gap-12 p-7 md:p-12 lg:grid-cols-12 lg:p-14">
        <div className="lg:col-span-6">
          <motion.div
            initial={reduce ? false : { opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={SPRING}
          >
            <Logo size="lg" tone="brand" />
          </motion.div>

          <motion.p
            initial={reduce ? false : { opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...SPRING, delay: 0.06 }}
            className="mt-7 inline-flex items-center gap-2 rounded-full border border-white bg-white/70 px-3.5 py-1.5 text-[11px] font-bold tracking-wide text-emerald-700 shadow-[0_4px_14px_0_rgb(0,0,0,0.04)] backdrop-blur-2xl"
          >
            <Sparkles className="h-3.5 w-3.5" aria-hidden />
            منصة عمليات العقود بالذكاء الاصطناعي
          </motion.p>

          <motion.h1
            initial={reduce ? false : { opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...SPRING, delay: 0.12 }}
            // Balanced wrap and a capped measure, so the display line breaks at
            // a deliberate point instead of stranding a single word.
            className="mt-5 max-w-[16ch] text-balance text-4xl font-extrabold leading-[1.22] tracking-tight text-slate-900 md:text-5xl md:leading-[1.18]"
          >
            منصة إدارة وحوكمة العقود{" "}
            <span className="bg-gradient-to-r from-emerald-600 to-teal-500 bg-clip-text text-transparent">
              بالذكاء الاصطناعي
            </span>
          </motion.h1>

          <motion.p
            initial={reduce ? false : { opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...SPRING, delay: 0.18 }}
            className="mt-6 max-w-xl text-lg font-medium leading-[1.85] text-slate-500 md:text-xl"
          >
            تحليل، تدقيق، وإدارة دورة حياة العقود وفق الأنظمة واللوائح السعودية خلال ثوانٍ
          </motion.p>

          <motion.div
            initial={reduce ? false : { opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...SPRING, delay: 0.24 }}
            className="mt-9 flex flex-wrap items-center gap-3"
          >
            <Link href="/upload" className="focus-ring btn-primary-3d group relative overflow-hidden">
              <span
                className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/25 to-transparent transition-transform duration-700 group-hover:translate-x-full"
                aria-hidden
              />
              <Sparkles className="h-4 w-4" aria-hidden />
              بدء تحليل عقد جديد
              <ArrowUpLeft
                className="h-4 w-4 transition-transform duration-200 group-hover:-translate-y-0.5"
                aria-hidden
              />
            </Link>

            <Link href="/dashboard" className="focus-ring btn-secondary-glass">
              استعراض السجل والتحليلات
            </Link>
          </motion.div>

          <div className="mt-10 grid gap-3 sm:grid-cols-3">
            <Metric icon={FileCheck2} target={1284} lang={lang} label="العقود الموثقة" delay={0.3} />
            <Metric
              icon={Clock4}
              target={4.2}
              lang={lang}
              decimals={1}
              suffix={lang === "ar" ? "ث" : "s"}
              label="متوسط زمن المراجعة"
              delay={0.36}
            />
            <Metric
              icon={BarChart3}
              target={98}
              lang={lang}
              suffix={lang === "ar" ? "٪" : "%"}
              label="دقة تقييم المخاطر"
              delay={0.42}
            />
          </div>
        </div>

        <div className="lg:col-span-6">
          <AuditPreviewCard score={98} />
        </div>
      </div>
    </section>
  );
}
