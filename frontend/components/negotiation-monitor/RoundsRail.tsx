"use client";

import { useI18n } from "@/lib/i18n";

type Round = { round_number: number; status: string; opened_at?: string | null };

export default function RoundsRail({ rounds }: { rounds: Round[] }) {
  const { t } = useI18n();
  return (
    <section className="surface-card p-4">
      <h3 className="font-bold">{t("monitor.round")}</h3>
      <ul className="mt-2 space-y-2">
        {rounds.map((r) => (
          <li key={r.round_number} className="flex items-center justify-between text-sm">
            <span>
              {t("monitor.round")} {r.round_number}
            </span>
            <span className="text-neutral-600">{r.status}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
