"use client";
// The ميثاق / MITHAQ lockup.
//
// If a brand asset exists at /mithaq-logo.(svg|png) it is used. Otherwise the
// lockup renders as live text — the Arabic wordmark in Amiri (classical naskh)
// above the Latin name in letterspaced Cormorant caps, matching the stacked
// arrangement of the brand mark.
//
// Live text stays crisp at any size, recolors with the palette, and is
// readable by screen readers and search. The lockup is identical in RTL and
// LTR: a centered stack has no handedness.
import { useState } from "react";

import { cn } from "@/lib/utils";

/** Drop the brand file here and it replaces the text lockup automatically. */
const LOGO_SRC = "/mithaq-logo.png";

const sizes = {
  sm: { ar: "text-xl", en: "text-[0.5rem] tracking-[0.34em]", gap: "-mt-0.5", img: "h-7" },
  md: { ar: "text-2xl", en: "text-[0.6rem] tracking-[0.36em]", gap: "-mt-1", img: "h-10" },
  lg: { ar: "text-5xl", en: "text-base tracking-[0.36em]", gap: "-mt-1.5", img: "h-20" },
  xl: { ar: "text-7xl", en: "text-2xl tracking-[0.34em]", gap: "-mt-3", img: "h-28" },
  "2xl": { ar: "text-[6.5rem]", en: "text-[2rem] tracking-[0.32em]", gap: "-mt-4", img: "h-40" },
};

export default function Logo({
  size = "md",
  className,
  tone = "brand",
}: {
  size?: keyof typeof sizes;
  className?: string;
  /** `brand` on light surfaces, `onDark` over emerald/ink panels. */
  tone?: "brand" | "onDark" | "ink";
}) {
  const [assetFailed, setAssetFailed] = useState(false);
  const s = sizes[size];

  const color =
    tone === "onDark" ? "text-white" : tone === "ink" ? "text-ink-900" : "text-brand-600";
  const subColor =
    tone === "onDark" ? "text-white/70" : tone === "ink" ? "text-ink-900/60" : "text-brand-600/70";

  if (!assetFailed) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- needs an onError
      // fallback, which next/image does not surface for a missing local asset.
      <img
        src={LOGO_SRC}
        alt="ميثاق — MITHAQ"
        onError={() => setAssetFailed(true)}
        className={cn("w-auto object-contain", s.img, tone === "onDark" && "brightness-0 invert", className)}
      />
    );
  }

  return (
    <span className={cn("inline-flex flex-col items-center leading-none", className)}>
      {/* sr-only carries both halves so the lockup announces once, cleanly. */}
      <span className={cn("font-display font-bold", s.ar, color)} aria-hidden>
        ميثاق
      </span>
      <span className={cn("font-wordmark font-medium uppercase", s.en, s.gap, subColor)} aria-hidden>
        Mithaq
      </span>
      <span className="sr-only">ميثاق — MITHAQ</span>
    </span>
  );
}
