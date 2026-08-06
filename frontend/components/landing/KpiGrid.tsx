"use client";

import { AlertTriangle, FileSignature, FileStack, MessagesSquare, Scale, Wallet } from "lucide-react";
import Link from "next/link";

import { useI18n } from "@/lib/i18n";
import { formatPortfolioSar } from "@/lib/pipeline";
import { cn, formatCount, formatNum } from "@/lib/utils";

export type HomeKpiData = {
  totalContracts: number;
  portfolioValue: number;
  pendingReviews: number;
  awaitingSignature: number;
  highRisk: number;
  activeNegotiations: number;
};

/**
 * One continuous measurement band rather than six equal cards.
 *
 * Six identically-weighted tiles gave the reader no order to read in. Here the
 * portfolio figure is the anchor, risk is the only tile allowed a warning hue,
 * and hairline dividers bind the rest into a single object.
 */
export default function KpiGrid({ data }: { data: HomeKpiData }) {
  const { t, lang } = useI18n();

  const items = [
    {
      key: "total",
      href: "/contracts",
      icon: FileStack,
      label: t("home.kpi.totalContracts"),
      value: formatCount(data.totalContracts, lang),
      tone: "neutral" as const,
    },
    {
      key: "value",
      href: "/contracts",
      icon: Wallet,
      label: t("home.kpi.portfolioValue"),
      value: formatPortfolioSar(data.portfolioValue, lang),
      tone: "brand" as const,
    },
    {
      key: "reviews",
      href: "/reviews",
      icon: MessagesSquare,
      label: t("home.kpi.pendingReviews"),
      value: formatCount(data.pendingReviews, lang),
      tone: "neutral" as const,
    },
    {
      key: "signature",
      href: "/contracts?stage=awaiting_signature",
      icon: FileSignature,
      label: t("home.kpi.awaitingSignature"),
      value: formatCount(data.awaitingSignature, lang),
      tone: "neutral" as const,
    },
    {
      key: "risk",
      href: "/contracts",
      icon: AlertTriangle,
      label: t("home.kpi.highRisk"),
      value: formatCount(data.highRisk, lang),
      // Only ever loud when there is actually something to be loud about.
      tone: data.highRisk > 0 ? ("danger" as const) : ("neutral" as const),
    },
    {
      key: "negotiations",
      href: "/negotiations/monitor",
      icon: Scale,
      label: t("home.kpi.activeNegotiations"),
      value: formatCount(data.activeNegotiations, lang),
      tone: "neutral" as const,
    },
  ];

  return (
    <section className="stagger glass-card grid grid-cols-2 overflow-hidden md:grid-cols-3 xl:grid-cols-6">
      {items.map((item, i) => {
        const Icon = item.icon;
        return (
          <Link
            key={item.key}
            href={item.href}
            style={{ "--i": i } as React.CSSProperties}
            className={cn(
              "group relative flex flex-col gap-3 p-5 motion-safe:animate-riseIn",
              // Hairline grid built from logical border-inline-end, so the
              // dividers land correctly in RTL as well as LTR.
              "border-b border-white/90 border-e [&:nth-child(2n)]:border-e-0 md:[&:nth-child(2n)]:border-e md:[&:nth-child(3n)]:border-e-0",
              "xl:border-b-0 xl:[&:nth-child(3n)]:border-e xl:[&:last-child]:border-e-0",
              "transition-colors duration-300 hover:bg-emerald-50/50",
            )}
          >
            <span
              className={cn(
                "flex h-9 w-9 items-center justify-center rounded-xl motion-safe:transition-transform motion-safe:duration-300 motion-safe:ease-settle group-hover:scale-110",
                item.tone === "brand" && "bg-gradient-to-br from-emerald-50 to-teal-50 text-emerald-600 shadow-inner",
                item.tone === "danger" && "bg-gradient-to-br from-rose-50 to-amber-50 text-rose-600 shadow-inner",
                item.tone === "neutral" && "bg-slate-100 text-slate-500 shadow-inner group-hover:from-emerald-50 group-hover:to-teal-50 group-hover:bg-gradient-to-br group-hover:text-emerald-600",
              )}
            >
              <Icon className="h-[18px] w-[18px]" strokeWidth={1.9} aria-hidden />
            </span>

            <div>
              <p
                className={cn(
                  "tnum text-[1.75rem] font-extrabold leading-none tracking-tight",
                  item.tone === "danger" ? "text-rose-600" : "text-slate-900",
                )}
              >
                {item.value}
              </p>
              <p className="mt-2 text-xs font-medium leading-snug text-slate-500">{item.label}</p>
            </div>
          </Link>
        );
      })}
    </section>
  );
}
