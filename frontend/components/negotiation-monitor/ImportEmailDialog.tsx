"use client";

import { useCachedFetch } from "@/lib/cache";
import { listSimulatedInbox, importNegotiationEmail } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import Button from "@/components/ui/Button";

type Props = {
  open: boolean;
  threadId: string | null;
  onClose: () => void;
  onDone: () => void;
};

export default function ImportEmailDialog({ open, threadId, onClose, onDone }: Props) {
  const { t } = useI18n();
  const { data } = useCachedFetch("negotiation:sim-inbox", () => listSimulatedInbox().then((r) => r.messages), {
    enabled: open,
  });

  if (!open || !threadId) return null;

  async function pick(messageId: string) {
    await importNegotiationEmail(threadId!, { simulated_message_id: messageId });
    onDone();
    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="surface-card max-h-[80vh] w-full max-w-lg overflow-auto p-4">
        <h3 className="text-lg font-bold">{t("monitor.importEmail")}</h3>
        <ul className="mt-4 space-y-2">
          {(data ?? []).map((m) => (
            <li key={m.external_message_id} className="rounded-lg border border-neutral-200 p-3">
              <p className="font-semibold">{m.subject}</p>
              <p className="text-sm text-neutral-600">{m.preview}</p>
              <Button size="sm" className="mt-2" onClick={() => pick(m.external_message_id)}>
                {t("common.confirm")}
              </Button>
            </li>
          ))}
        </ul>
        <Button variant="secondary" className="mt-4" onClick={onClose}>
          {t("common.cancel")}
        </Button>
      </div>
    </div>
  );
}
