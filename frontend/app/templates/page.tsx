"use client";
import { useState } from "react";

import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Drawer from "@/components/ui/Drawer";
import SectionHeader from "@/components/ui/SectionHeader";
import { TEMPLATE_SEED } from "@/lib/templatesSeed";
import { useI18n } from "@/lib/i18n";

export default function TemplatesPage() {
  const { t } = useI18n();
  const [drawerOpen, setDrawerOpen] = useState(false);

  return (
    <div className="space-y-6">
      <SectionHeader
        title={t("nav.templates")}
        eyebrow={t("templates.sampleBadge")}
        actions={
          <Button variant="primary" onClick={() => setDrawerOpen(true)}>
            {t("templates.createNew")}
          </Button>
        }
      />
      <Badge tone="subtle">{t("templates.sampleBadge")}</Badge>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {TEMPLATE_SEED.map((tpl) => (
          <article key={tpl.id} className="surface-card overflow-hidden">
            <div
              className="h-28"
              style={{ background: `linear-gradient(135deg, ${tpl.gradient[0]}, ${tpl.gradient[1]})` }}
            />
            <div className="space-y-2 p-4">
              <h3 className="font-bold text-neutral-900">{tpl.title}</h3>
              <p className="text-sm text-neutral-600">
                {t("templates.category")}: {tpl.category}
              </p>
              <div className="flex flex-wrap gap-2">
                <span className="pill">{t("templates.language")}: {tpl.language}</span>
                <span className="pill">{t("templates.industry")}: {tpl.industry}</span>
              </div>
              <p className="text-xs text-neutral-500">
                {t("templates.lastUpdated")}: {tpl.lastUpdated} · {t("templates.usage")}: {tpl.usageCount}
              </p>
              <Button variant="secondary" size="sm" className="w-full" onClick={() => (window.location.href = "/upload")}>
                {t("templates.useTemplate")}
              </Button>
            </div>
          </article>
        ))}
      </div>
      <Drawer open={drawerOpen} onClose={() => setDrawerOpen(false)} title={t("templates.createNew")}>
        <p className="text-hint">{t("placeholder.comingSoonHint")}</p>
      </Drawer>
    </div>
  );
}
