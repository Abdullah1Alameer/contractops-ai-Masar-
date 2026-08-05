"use client";

import Button from "@/components/ui/Button";
import Drawer from "@/components/ui/Drawer";
import { lineageDeepLink } from "@/lib/lineageLinks";
import { useI18n, type TKey } from "@/lib/i18n";
import type { VersionLineageEvent } from "@/lib/types";
import Link from "next/link";

export default function EventDetailDrawer({
  contractId,
  event,
  versionLabel,
  open,
  onClose,
}: {
  contractId: string;
  event: VersionLineageEvent | null;
  versionLabel?: string;
  open: boolean;
  onClose: () => void;
}) {
  const { t } = useI18n();
  if (!event) return null;
  const titleKey = event.title_key.replace("activity.", "") as TKey;
  const title = t(`activity.${titleKey}` as TKey);
  const href = lineageDeepLink(contractId, event);
  const meta = event.metadata ?? {};

  return (
    <Drawer open={open} onClose={onClose} title={title} size="md">
      <dl className="space-y-3 text-sm">
        <div>
          <dt className="text-eyebrow">{t("versions.col.version")}</dt>
          <dd className="font-medium">{versionLabel ?? event.version_number}</dd>
        </div>
        {event.actor && (
          <div>
            <dt className="text-eyebrow">{t("versions.createdBy")}</dt>
            <dd>{event.actor}</dd>
          </div>
        )}
        {event.actor_role && (
          <div>
            <dt className="text-eyebrow">{t("approval.step.legal")}</dt>
            <dd>{event.actor_role}</dd>
          </div>
        )}
        {event.timestamp && (
          <div>
            <dt className="text-eyebrow">{t("versions.col.date")}</dt>
            <dd>{event.timestamp}</dd>
          </div>
        )}
        {event.status && (
          <div>
            <dt className="text-eyebrow">{t("versions.col.status")}</dt>
            <dd>{event.status}</dd>
          </div>
        )}
        {event.description && (
          <div>
            <dt className="text-eyebrow">{t("versions.reason")}</dt>
            <dd className="whitespace-pre-wrap">{event.description}</dd>
          </div>
        )}
        {Object.keys(meta).length > 0 && (
          <div>
            <dt className="text-eyebrow">{t("activity.title")}</dt>
            <dd>
              <ul className="mt-1 space-y-1 text-xs text-neutral-600">
                {Object.entries(meta).map(([k, v]) => (
                  <li key={k}>
                    <span className="font-semibold">{k}:</span> {String(v)}
                  </li>
                ))}
              </ul>
            </dd>
          </div>
        )}
      </dl>
      {href && (
        <div className="mt-6">
          <Link href={href}>
            <Button variant="primary" size="sm">
              {t("versions.viewRelated")}
            </Button>
          </Link>
        </div>
      )}
    </Drawer>
  );
}
