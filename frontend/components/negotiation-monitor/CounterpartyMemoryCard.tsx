"use client";

import { useCachedFetch } from "@/lib/cache";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function CounterpartyMemoryCard({ email }: { email: string }) {
  const { t } = useI18n();
  const enc = encodeURIComponent(email);
  const { data } = useCachedFetch(`counterparty:memory:${enc}`, () =>
    api<{ insufficient_history?: boolean; summary?: string; insights?: string[] }>(
      `/api/counterparties/${enc}/negotiation-memory`
    )
  );

  if (data?.insufficient_history) return null;

  return (
    <section className="surface-card p-4">
      <h3 className="font-bold">{t("monitor.counterpartyPattern")}</h3>
      <p className="mt-2 text-sm text-neutral-700">{data?.summary}</p>
      <ul className="mt-2 list-disc ps-5 text-sm">
        {(data?.insights ?? []).map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </section>
  );
}
