"use client";
import Link from "next/link";
import { useState } from "react";

import Button from "@/components/ui/Button";
import Drawer from "@/components/ui/Drawer";
import { SkeletonCard } from "@/components/ui/Skeleton";
import SectionHeader from "@/components/ui/SectionHeader";
import { fetchTemplates } from "@/lib/api";
import { useCachedFetch } from "@/lib/cache";
import { useI18n } from "@/lib/i18n";
import { formatDate, formatNum } from "@/lib/utils";

// Bug fix: "Use Template" used to hard-redirect to the generic /upload page,
// silently forgetting which template (if any) was clicked. Templates are now
// real backend records (GET /api/templates) and each card links to a real
// per-template creation flow at /templates/[id]. See
// docs/signature-placement-and-template-flow-report.md.
const GRADIENTS: Record<string, [string, string]> = {
  msa: ["#0F766E", "#14b8a6"],
  nda: ["#115e59", "#5eead4"],
  sow: ["#134e4a", "#2dd4bf"],
  vendor: ["#0d9488", "#99f6e4"],
};

export default function TemplatesPage() {
  const { t, lang } = useI18n();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const { data, isLoading } = useCachedFetch("templates:list", fetchTemplates, { staleMs: 60_000 });
  const templates = data?.templates ?? [];

  return (
    <div className="space-y-6">
      <SectionHeader
        title={t("nav.templates")}
        actions={
          <Button variant="primary" onClick={() => setDrawerOpen(true)}>
            {t("templates.createNew")}
          </Button>
        }
      />
      {isLoading ? (
        <SkeletonCard rows={3} />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {templates.map((tpl) => {
            const gradient = GRADIENTS[tpl.key] ?? ["#0F766E", "#14b8a6"];
            const title = lang === "ar" ? tpl.title_ar : tpl.title_en;
            return (
              <article key={tpl.id} className="surface-card overflow-hidden">
                <div className="h-28" style={{ background: `linear-gradient(135deg, ${gradient[0]}, ${gradient[1]})` }} />
                <div className="space-y-2 p-4">
                  <h3 className="font-bold text-neutral-900">{title}</h3>
                  <p className="text-sm text-neutral-600">
                    {t("templates.category")}: {tpl.category ?? "—"}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <span className="pill">
                      {t("templates.language")}: {tpl.language}
                    </span>
                    <span className="pill">
                      {t("templates.industry")}: {tpl.industry ?? "—"}
                    </span>
                  </div>
                  <p className="text-xs text-neutral-500">
                    {t("templates.lastUpdated")}: {tpl.updated_at ? formatDate(tpl.updated_at, lang) : "—"} ·{" "}
                    {t("templates.usage")}: {formatNum(tpl.usage_count, lang)}
                  </p>
                  <Link href={`/templates/${tpl.id}`} className="block">
                    <Button variant="secondary" size="sm" className="w-full">
                      {t("templates.useTemplate")}
                    </Button>
                  </Link>
                </div>
              </article>
            );
          })}
        </div>
      )}
      <Drawer open={drawerOpen} onClose={() => setDrawerOpen(false)} title={t("templates.createNew")}>
        <p className="text-hint">{t("placeholder.comingSoonHint")}</p>
      </Drawer>
    </div>
  );
}
