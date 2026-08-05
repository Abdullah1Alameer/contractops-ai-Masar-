"use client";

import { useCachedFetch } from "@/lib/cache";
import { getNegotiationPackage } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function ThreeWayComparisonPanel({ packageId }: { packageId: string | null }) {
  const { t } = useI18n();
  const { data } = useCachedFetch(
    packageId ? `negotiation:pkg:${packageId}` : "negotiation:pkg:none",
    () => (packageId ? getNegotiationPackage(packageId) : Promise.resolve(null)),
    { enabled: Boolean(packageId) }
  );

  const body = (data?.package_json ?? {}) as Record<string, unknown>;
  const changes = (body.changes ?? []) as Record<string, unknown>[];

  if (!packageId) {
    return (
      <section className="surface-card p-4">
        <p className="text-hint">{t("monitor.awaitingLawyer")}</p>
      </section>
    );
  }

  return (
    <section className="surface-card space-y-3 p-4">
      <h3 className="font-bold">{t("monitor.templateDeviation")}</h3>
      {changes.map((ch, i) => (
        <article key={i} className="rounded-lg border border-neutral-200 p-3 text-sm">
          <p className="font-semibold">{String(ch.clause_category ?? "")}</p>
          <p className="text-neutral-600">{String(ch.revised_text ?? "").slice(0, 200)}</p>
          <span className="mt-1 inline-block rounded bg-neutral-100 px-2 py-0.5 text-xs">
            {String(ch.playbook_position ?? "—")}
          </span>
        </article>
      ))}
    </section>
  );
}
