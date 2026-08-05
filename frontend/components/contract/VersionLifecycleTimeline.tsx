"use client";

import SectionHeader from "@/components/ui/SectionHeader";
import Timeline, { type TimelineItem } from "@/components/ui/Timeline";
import { useI18n, type TKey } from "@/lib/i18n";
import type { ActivityEventRow, ContractVersionRow } from "@/lib/types";

const VERSION_LIFECYCLE_EVENTS = new Set([
  "version_created",
  "version_sent_for_review",
  "version_sent_for_approval",
  "version_sent_for_signature",
  "version_approved",
  "version_signed",
  "version_restored",
  "version_compared",
  "ai_comparison_generated",
  "current_version_changed",
  "approval_workflow_started",
  "approval_workflow_completed",
  "signature_request_created",
  "signer_signed",
]);

function metaVersion(meta: Record<string, unknown> | null | undefined): number | null {
  if (!meta) return null;
  const n = meta.version_number;
  if (typeof n === "number") return n;
  if (typeof n === "string") return parseInt(n, 10) || null;
  return null;
}

function eventTitle(eventType: string, t: (k: TKey) => string): string {
  const key = `activity.${eventType}` as TKey;
  const label = t(key);
  return label === key ? eventType.replace(/_/g, " ") : label;
}

export default function VersionLifecycleTimeline({
  versions,
  activity,
}: {
  versions: ContractVersionRow[];
  activity: ActivityEventRow[];
}) {
  const { t } = useI18n();
  const sorted = [...versions].sort((a, b) => a.version_number - b.version_number);
  const items: TimelineItem[] = [];

  for (const v of sorted) {
    items.push({
      id: `v-${v.id}`,
      title: `${v.version_label} — ${t(`versions.source.${v.source}` as TKey) || v.source}`,
      subtitle: v.change_summary ?? v.ai_summary ?? undefined,
      time: v.created_at?.slice(0, 16) ?? undefined,
      tone: v.is_current ? "success" : "default",
    });

    const related = activity
      .filter((e) => {
        if (!VERSION_LIFECYCLE_EVENTS.has(e.event_type)) return false;
        const vn = metaVersion(e.metadata as Record<string, unknown> | null);
        if (vn != null) return vn === v.version_number;
        if (e.event_type === "current_version_changed") {
          const meta = e.metadata as { to?: number } | null;
          return meta?.to === v.version_number;
        }
        return false;
      })
      .sort((a, b) => (a.created_at ?? "").localeCompare(b.created_at ?? ""));

    for (const e of related) {
      items.push({
        id: e.id,
        title: eventTitle(e.event_type, t),
        subtitle: e.actor ?? e.comment ?? undefined,
        time: e.created_at?.slice(0, 16) ?? undefined,
        tone:
          e.event_type.includes("signed") || e.event_type.includes("approved") || e.event_type.includes("completed")
            ? "success"
            : e.event_type.includes("rejected") || e.event_type.includes("declined")
              ? "danger"
              : "default",
      });
    }
  }

  if (items.length === 0) return null;

  return (
    <section className="space-y-3">
      <SectionHeader title={t("versions.historyTitle")} />
      <Timeline items={items} />
    </section>
  );
}
