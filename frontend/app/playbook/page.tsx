"use client";

import { useCachedFetch } from "@/lib/cache";
import { getPlaybook } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import SectionHeader from "@/components/ui/SectionHeader";

const DEFAULT_PLAYBOOK = "a1000000-0000-4000-8000-000000000001";

export default function PlaybookPage() {
  const { t } = useI18n();
  const { data, isLoading } = useCachedFetch("playbook:default", () => getPlaybook(DEFAULT_PLAYBOOK));

  return (
    <div className="space-y-6">
      <SectionHeader title={t("nav.playbook")} eyebrow={t("monitor.playbookViolation")} />
      {isLoading ? <p>{t("common.loading")}</p> : null}
      <div className="grid gap-3">
        {(data?.rules ?? []).map((rule) => {
          const r = rule as Record<string, string | null>;
          return (
            <article key={String(r.id)} className="surface-card p-4">
              <h3 className="font-bold">{r.clause_category}</h3>
              <p className="text-sm text-neutral-600">{r.rule_name}</p>
              <dl className="mt-2 grid gap-1 text-sm sm:grid-cols-3">
                <div>
                  <dt className="text-neutral-500">Preferred</dt>
                  <dd>{r.preferred_position}</dd>
                </div>
                <div>
                  <dt className="text-neutral-500">Fallback</dt>
                  <dd>{r.fallback_position}</dd>
                </div>
                <div>
                  <dt className="text-neutral-500">Unacceptable</dt>
                  <dd>{r.unacceptable_position}</dd>
                </div>
              </dl>
            </article>
          );
        })}
      </div>
    </div>
  );
}
