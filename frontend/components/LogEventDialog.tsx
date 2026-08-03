"use client";
import { useState } from "react";

import { logContractEvent } from "@/lib/api";
import { useI18n, type TKey } from "@/lib/i18n";

const EVENT_TYPES = ["delay", "defect", "suspension", "variation", "other"] as const;

export default function LogEventDialog({
  contractId,
  demoToday,
  onLogged,
}: {
  contractId: string;
  demoToday: string;
  onLogged: () => void;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [type, setType] = useState<(typeof EVENT_TYPES)[number]>("delay");
  const [description, setDescription] = useState("");
  const [eventDate, setEventDate] = useState(demoToday);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    setError(false);
    try {
      await logContractEvent(contractId, { type, description: description || undefined, event_date: eventDate });
      setOpen(false);
      setDescription("");
      onLogged();
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => {
          setEventDate(demoToday);
          setOpen(true);
        }}
        className="mb-4 rounded-lg border border-brand-200 bg-brand-50 px-3 py-1.5 text-sm font-semibold text-brand-800 hover:bg-brand-100"
      >
        {t("event.log")}
      </button>
    );
  }

  return (
    <div className="mb-4 rounded-xl border bg-white p-4 shadow-sm">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="grid gap-1 text-sm">
          <span>{t("event.log")}</span>
          <select className="rounded-md border px-2 py-1.5" value={type} onChange={(e) => setType(e.target.value as any)}>
            {EVENT_TYPES.map((k) => (
              <option key={k} value={k}>
                {t(`event.type.${k}` as TKey)}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-sm">
          {t("event.date")}
          <input type="date" className="rounded-md border px-2 py-1.5" value={eventDate} onChange={(e) => setEventDate(e.target.value)} />
        </label>
        <label className="grid gap-1 text-sm sm:col-span-2">
          {t("event.description")}
          <input className="rounded-md border px-2 py-1.5" value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>
      </div>
      {error && <p className="mt-2 text-sm text-red-600">{t("common.error")}</p>}
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={submit}
          className="rounded-lg bg-brand-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {t("event.submit")}
        </button>
        <button type="button" onClick={() => setOpen(false)} className="rounded-lg border px-3 py-1.5 text-sm hover:bg-gray-50">
          {t("event.cancel")}
        </button>
      </div>
    </div>
  );
}
