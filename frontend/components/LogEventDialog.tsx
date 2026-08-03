"use client";
import { useState } from "react";

import { logContractEvent } from "@/lib/api";
import Button from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
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
      <Button variant="secondary" size="sm" className="mb-4" onClick={() => { setEventDate(demoToday); setOpen(true); }}>
        {t("event.log")}
      </Button>
    );
  }

  return (
    <Card className="mb-4">
      <CardBody>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="grid gap-1 text-sm">
          <span>{t("event.log")}</span>
          <select className="rounded-lg border-2 border-gray-200 px-2 py-2 focus-visible:focus-ring" value={type} onChange={(e) => setType(e.target.value as any)}>
            {EVENT_TYPES.map((k) => (
              <option key={k} value={k}>
                {t(`event.type.${k}` as TKey)}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-sm">
          {t("event.date")}
          <input type="date" className="rounded-lg border-2 border-gray-200 px-2 py-2 focus-visible:focus-ring" value={eventDate} onChange={(e) => setEventDate(e.target.value)} />
        </label>
        <label className="grid gap-1 text-sm sm:col-span-2">
          {t("event.description")}
          <input className="rounded-lg border-2 border-gray-200 px-2 py-2 focus-visible:focus-ring" value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>
      </div>
      {error && <p className="mt-2 text-sm text-danger-600">{t("common.error")}</p>}
      <div className="mt-3 flex gap-2">
        <Button variant="primary" size="sm" loading={busy} onClick={submit}>
          {t("event.submit")}
        </Button>
        <Button variant="secondary" size="sm" onClick={() => setOpen(false)}>
          {t("event.cancel")}
        </Button>
      </div>
      </CardBody>
    </Card>
  );
}
