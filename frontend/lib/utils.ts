import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

import type { TKey } from "./i18n";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatSAR(v: number | null | undefined, lang: "ar" | "en"): string {
  if (v == null) return "—";
  const n = new Intl.NumberFormat(lang === "ar" ? "ar-SA-u-nu-arab" : "en-US").format(v);
  return lang === "ar" ? `${n} ر.س` : `SAR ${n}`;
}

/** Compact SAR for KPI cards (e.g. 1.2M). */
export function formatCompactSAR(v: number | null | undefined, lang: "ar" | "en"): string {
  if (v == null) return "—";
  const abs = Math.abs(v);
  let n: string;
  if (abs >= 1_000_000) {
    const m = v / 1_000_000;
    n = m.toLocaleString(lang === "ar" ? "ar-SA-u-nu-arab" : "en-US", { maximumFractionDigits: 1 }) + "M";
  } else if (abs >= 1_000) {
    const k = v / 1_000;
    n = k.toLocaleString(lang === "ar" ? "ar-SA-u-nu-arab" : "en-US", { maximumFractionDigits: 0 }) + "K";
  } else {
    n = new Intl.NumberFormat(lang === "ar" ? "ar-SA-u-nu-arab" : "en-US").format(v);
  }
  return lang === "ar" ? `${n} ر.س` : `SAR ${n}`;
}

const CATEGORY_TO_KEY: Record<string, TKey> = {
  "Main Construction Contract": "category.main_construction",
  "Subcontract Agreement": "category.subcontract",
  "Material Supply Agreement": "category.material_supply",
  "Supplier Agreement": "category.supplier",
  "Procurement Agreement": "category.procurement",
  "Construction Service Agreement": "category.construction_service",
  "Consultant Agreement (Construction)": "category.consultant",
  "Purchase Order (Construction)": "category.purchase_order",
  "Maintenance Contract (Construction)": "category.maintenance",
  "Variation Order": "category.variation_order",
  "Work Order": "category.work_order",
  Unknown: "category.unknown",
  "Employment Contract": "category.employment",
};

export const SUPPORTED_CATEGORY_KEYS: TKey[] = [
  "category.main_construction",
  "category.subcontract",
  "category.material_supply",
  "category.supplier",
  "category.procurement",
  "category.construction_service",
  "category.consultant",
  "category.purchase_order",
  "category.maintenance",
  "category.variation_order",
  "category.work_order",
];

export function contractCategoryLabelKey(category: string | null | undefined): TKey {
  if (!category) return "category.unknown";
  return CATEGORY_TO_KEY[category] ?? "category.other_unsupported";
}
