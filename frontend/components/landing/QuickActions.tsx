"use client";

import { motion, useReducedMotion } from "framer-motion";
import {
  BarChart3,
  FilePlus2,
  LayoutDashboard,
  LayoutTemplate,
  Scale,
  UploadCloud,
} from "lucide-react";
import Link from "next/link";

import { useI18n, type TKey } from "@/lib/i18n";

const SPRING = { type: "spring" as const, stiffness: 300, damping: 30 };

type Action = { href: string; labelKey: TKey; icon: typeof FilePlus2 };

const ACTIONS: Action[] = [
  { href: "/upload", labelKey: "home.quick.newContract", icon: FilePlus2 },
  { href: "/upload", labelKey: "home.quick.upload", icon: UploadCloud },
  { href: "/negotiations/monitor", labelKey: "home.quick.negotiations", icon: Scale },
  { href: "/templates", labelKey: "home.quick.templates", icon: LayoutTemplate },
  { href: "/reports", labelKey: "home.quick.reports", icon: BarChart3 },
  { href: "/dashboard", labelKey: "home.quick.dashboard", icon: LayoutDashboard },
];

export default function QuickActions() {
  const { t } = useI18n();
  const reduce = useReducedMotion();

  return (
    <section className="glass-card p-6 md:p-7">
      <h2 className="text-lg font-extrabold tracking-tight text-slate-900">{t("home.quick.title")}</h2>

      <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3">
        {ACTIONS.map((a, i) => {
          const Icon = a.icon;
          return (
            <motion.div
              key={`${a.href}-${a.labelKey}`}
              initial={reduce ? false : { opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ ...SPRING, delay: i * 0.05 }}
            >
              <Link
                href={a.href}
                className="focus-ring group relative flex h-full flex-col items-center gap-3 overflow-hidden rounded-3xl border border-white bg-white/60 p-5 text-center text-sm font-bold text-slate-700 shadow-[0_4px_14px_0_rgb(0,0,0,0.03)] backdrop-blur-2xl transition-all duration-300 hover:text-emerald-700 hover:shadow-[0_12px_32px_rgb(0,0,0,0.07)] motion-safe:hover:-translate-y-1"
              >
                <span
                  className="pointer-events-none absolute inset-0 bg-gradient-to-t from-emerald-50/90 to-transparent opacity-0 transition-opacity duration-500 group-hover:opacity-100"
                  aria-hidden
                />
                <span className="relative flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-50 to-teal-50 text-emerald-600 shadow-inner transition-transform duration-300 motion-safe:ease-emphasis group-hover:scale-110 group-hover:rotate-6">
                  <Icon className="h-5 w-5" strokeWidth={1.9} aria-hidden />
                </span>
                <span className="relative leading-snug">{t(a.labelKey)}</span>
              </Link>
            </motion.div>
          );
        })}
      </div>
    </section>
  );
}
