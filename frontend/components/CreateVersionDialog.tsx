"use client";
import { useState } from "react";

import Button from "@/components/ui/Button";
import { useI18n, type TKey } from "@/lib/i18n";

const SOURCES = [
  "manual_upload",
  "negotiation_counter",
  "client_revision",
  "internal_revision",
  "approved",
  "signed",
] as const;

export default function CreateVersionDialog({
  open,
  onClose,
  onSubmit,
}: {
  open: boolean;
  onClose: () => void;
  onSubmit: (file: File, source: string, summary: string) => Promise<void>;
}) {
  const { t } = useI18n();
  const [file, setFile] = useState<File | null>(null);
  const [source, setSource] = useState<string>("manual_upload");
  const [summary, setSummary] = useState("");
  const [busy, setBusy] = useState(false);

  const summaryOk = summary.trim().length > 0;

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <h3 className="mb-4 text-lg font-bold">{t("versions.createNew")}</h3>
        <input type="file" accept=".pdf,.docx" className="mb-3 w-full text-sm" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        <label className="text-sm font-medium">{t("versions.changeReason")}</label>
        <select className="mb-3 w-full rounded border px-2 py-1 text-sm" value={source} onChange={(e) => setSource(e.target.value)}>
          {SOURCES.map((s) => (
            <option key={s} value={s}>
              {t(`versions.source.${s}` as TKey)}
            </option>
          ))}
        </select>
        <textarea
          className="mb-4 w-full rounded border px-2 py-1 text-sm"
          rows={2}
          placeholder={t("versions.col.summary")}
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
        />
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button
            variant="primary"
            loading={busy}
            disabled={!file || !summaryOk}
            onClick={async () => {
              if (!file) return;
              setBusy(true);
              try {
                await onSubmit(file, source, summary);
              } finally {
                setBusy(false);
              }
            }}
          >
            {t("versions.createNew")}
          </Button>
        </div>
      </div>
    </div>
  );
}
