import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

import type { TKey } from "./i18n";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Locale numeral system.
 *
 * The Arabic UI must not mix scripts: digits render as Arabic-Indic
 * (٠١٢٣٤٥٦٧٨٩) via the `-u-nu-arab` extension, and the decimal/grouping
 * separators come from the locale too (٫ and ٬, not . and ,).
 */
export function numLocale(lang: "ar" | "en"): string {
  return lang === "ar" ? "ar-SA-u-nu-arab" : "en-US";
}

/**
 * A count for display in a large figure (KPI tiles, chart values).
 *
 * Arabic-Indic zero is U+0660 "٠" — a small centred dot. It is the correct
 * glyph, but set at 3xl/font-black beside ٣ and ٥ it reads as a stray floating
 * dot rather than a number. Dashboards already have a settled convention for
 * "nothing to report", so zero renders as an em dash and every non-zero value
 * keeps its Arabic-Indic numeral.
 *
 * Latin zero has no such ambiguity, so `en` shows 0.
 */
export function formatCount(
  v: number | null | undefined,
  lang: "ar" | "en",
): string {
  if (v == null || Number.isNaN(v)) return "—";
  if (v === 0) return lang === "ar" ? "—" : "0";
  return formatNum(v, lang);
}

/** A bare number in the reader's own numeral system. */
export function formatNum(
  v: number | null | undefined,
  lang: "ar" | "en",
  opts?: Intl.NumberFormatOptions,
): string {
  if (v == null || Number.isNaN(v)) return "—";
  return new Intl.NumberFormat(numLocale(lang), opts).format(v);
}

/** Percentage, using the Arabic percent sign (٪) under `ar`. */
export function formatPercent(
  v: number | null | undefined,
  lang: "ar" | "en",
  fractionDigits = 0,
): string {
  if (v == null || Number.isNaN(v)) return "—";
  return new Intl.NumberFormat(numLocale(lang), {
    style: "percent",
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(v / 100);
}

/**
 * A date in the reader's own numeral system.
 *
 * `calendar: "gregory"` is explicit: ar-SA defaults to the Islamic calendar,
 * which would silently re-express the stored Gregorian date as a different
 * number. Only the digits change here, never the date itself — Hijri display
 * is a separate, deliberate feature (see DualDate).
 */
export function formatDate(
  value: string | Date | null | undefined,
  lang: "ar" | "en",
): string {
  if (!value) return "—";
  const d = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat(numLocale(lang), {
    calendar: "gregory",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(d);
}

export function formatSAR(v: number | null | undefined, lang: "ar" | "en"): string {
  if (v == null) return "—";
  const n = new Intl.NumberFormat(numLocale(lang)).format(v);
  return lang === "ar" ? `${n} ر.س` : `SAR ${n}`;
}

/**
 * Compact SAR for KPI cards.
 *
 * The magnitude suffix is written in the reader's own script — مليون / ألف
 * under `ar`, M / K under `en`. Previously the Latin "M"/"K" was appended to
 * Arabic-Indic digits, producing "٩٫٦M" — mixed scripts in a single token.
 */
export function formatCompactSAR(v: number | null | undefined, lang: "ar" | "en"): string {
  if (v == null) return "—";
  const abs = Math.abs(v);
  const loc = numLocale(lang);
  let n: string;

  if (abs >= 1_000_000) {
    const m = v / 1_000_000;
    const digits = m.toLocaleString(loc, { maximumFractionDigits: 1 });
    n = lang === "ar" ? `${digits} مليون` : `${digits}M`;
  } else if (abs >= 1_000) {
    const k = v / 1_000;
    const digits = k.toLocaleString(loc, { maximumFractionDigits: 0 });
    n = lang === "ar" ? `${digits} ألف` : `${digits}K`;
  } else {
    n = new Intl.NumberFormat(loc).format(v);
  }

  return lang === "ar" ? `${n} ر.س` : `SAR ${n}`;
}

const CATEGORY_TO_KEY: Record<string, TKey> = {
  NDA: "category.nda",
  "Service Agreement": "category.service",
  "Vendor Agreement": "category.vendor",
  "Supplier Agreement": "category.supplier",
  "Procurement Agreement": "category.procurement",
  "Sales Agreement": "category.sales",
  "Partnership Agreement": "category.partnership",
  "Consulting Agreement": "category.consulting",
  "Software/SaaS Agreement": "category.saas",
  "Licensing Agreement": "category.licensing",
  "Employment Agreement": "category.employment",
  "Employment Contract": "category.employment",
  "Lease Agreement": "category.lease",
  "Distribution Agreement": "category.distribution",
  "Maintenance Agreement": "category.maintenance_general",
  "Master Service Agreement": "category.msa",
  "Statement of Work": "category.sow",
  "Construction Contract": "category.construction",
  Subcontract: "category.subcontract_general",
  "Other Commercial Contract": "category.other_commercial",
  "Main Construction Contract": "category.main_construction",
  "Subcontract Agreement": "category.subcontract",
  "Material Supply Agreement": "category.material_supply",
  "Construction Service Agreement": "category.construction_service",
  "Consultant Agreement (Construction)": "category.consultant",
  "Purchase Order (Construction)": "category.purchase_order",
  "Maintenance Contract (Construction)": "category.maintenance",
  "Variation Order": "category.variation_order",
  "Work Order": "category.work_order",
  Unknown: "category.unknown",
  "Consent Agreement": "category.consent_agreement",
  "Authorization Form": "category.authorization_form",
  "Employment Screening Consent": "category.employment_screening_consent",
  "Data Processing Consent": "category.data_processing_consent",
  "Privacy Consent": "category.privacy_consent",
  "Background Check Authorization": "category.background_check_auth",
  "Release of Information": "category.release_of_information",
  "Electronic Signature Consent": "category.electronic_signature_consent",
  "Other Legal Consent": "category.other_legal_consent",
  "Curriculum Vitae": "category.curriculum_vitae",
  "Personal Identification Document": "category.personal_id",
};

export const SUPPORTED_CATEGORY_KEYS: TKey[] = [
  "category.nda",
  "category.service",
  "category.vendor",
  "category.supplier",
  "category.procurement",
  "category.sales",
  "category.partnership",
  "category.consulting",
  "category.saas",
  "category.licensing",
  "category.employment",
  "category.lease",
  "category.distribution",
  "category.maintenance_general",
  "category.msa",
  "category.sow",
  "category.construction",
  "category.subcontract_general",
  "category.other_commercial",
  "category.main_construction",
  "category.subcontract",
  "category.material_supply",
  "category.construction_service",
  "category.consultant",
  "category.purchase_order",
  "category.maintenance",
  "category.variation_order",
  "category.work_order",
  "category.consent_agreement",
  "category.authorization_form",
  "category.employment_screening_consent",
  "category.data_processing_consent",
  "category.privacy_consent",
  "category.background_check_auth",
  "category.release_of_information",
  "category.electronic_signature_consent",
  "category.other_legal_consent",
];

export function contractCategoryLabelKey(category: string | null | undefined): TKey {
  if (!category) return "category.unknown";
  return CATEGORY_TO_KEY[category] ?? "category.other_commercial";
}
