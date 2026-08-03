"use client";
import Badge from "@/components/ui/Badge";
import { useI18n } from "@/lib/i18n";

export default function TypeBadge({ type }: { type: "main" | "subcontract" | null }) {
  const { t } = useI18n();
  if (!type) return null;
  return (
    <Badge tone={type === "main" ? "success" : "purple"} size="md">
      {t(type === "main" ? "type.main" : "type.subcontract")}
    </Badge>
  );
}
