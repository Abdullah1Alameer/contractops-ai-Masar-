import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatSAR(v: number | null | undefined, lang: "ar" | "en"): string {
  if (v == null) return "—";
  const n = new Intl.NumberFormat(lang === "ar" ? "ar-SA-u-nu-arab" : "en-US").format(v);
  return lang === "ar" ? `${n} ر.س` : `SAR ${n}`;
}
