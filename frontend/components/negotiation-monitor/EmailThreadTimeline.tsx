"use client";

import { useI18n } from "@/lib/i18n";

type EmailRow = {
  id: string;
  direction: string;
  sender_name?: string | null;
  subject?: string | null;
  body_text?: string | null;
  classification?: string | null;
  processing_status?: string | null;
  attachments?: { filename: string }[];
};

export default function EmailThreadTimeline({ emails }: { emails: EmailRow[] }) {
  const { t } = useI18n();
  return (
    <section className="surface-card p-4">
      <h3 className="font-bold">{t("monitor.emailThread")}</h3>
      <ol className="mt-3 space-y-3">
        {emails.map((e) => (
          <li key={e.id} className="rounded-lg border border-neutral-200 p-3 text-sm">
            <div className="flex justify-between gap-2">
              <span className="font-semibold">{e.sender_name ?? e.direction}</span>
              <span className="text-xs text-neutral-500">{e.classification ?? e.processing_status}</span>
            </div>
            <p className="font-medium">{e.subject}</p>
            <p className="line-clamp-4 whitespace-pre-wrap text-neutral-700">{e.body_text}</p>
            {e.attachments?.length ? (
              <p className="mt-1 text-xs text-neutral-500">{e.attachments.map((a) => a.filename).join(", ")}</p>
            ) : null}
          </li>
        ))}
      </ol>
    </section>
  );
}
