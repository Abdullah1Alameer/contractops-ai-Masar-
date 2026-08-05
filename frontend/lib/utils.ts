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
