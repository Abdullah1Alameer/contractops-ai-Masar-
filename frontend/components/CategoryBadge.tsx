"use client";
import Badge from "@/components/ui/Badge";
import { useI18n } from "@/lib/i18n";
import { contractCategoryLabelKey } from "@/lib/utils";

export default function CategoryBadge({ category }: { category: string | null | undefined }) {
  const { t } = useI18n();
  if (!category) return null;
  return <Badge tone="neutral">{t(contractCategoryLabelKey(category))}</Badge>;
}
