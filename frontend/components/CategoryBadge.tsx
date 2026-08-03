"use client";
import { useI18n } from "@/lib/i18n";
import { contractCategoryLabelKey } from "@/lib/utils";

export default function CategoryBadge({ category }: { category: string | null | undefined }) {
  const { t } = useI18n();
  if (!category) return null;
  return (
    <span className="inline-flex items-center rounded-md bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700 ring-1 ring-inset ring-gray-300/60">
      {t(contractCategoryLabelKey(category))}
    </span>
  );
}
