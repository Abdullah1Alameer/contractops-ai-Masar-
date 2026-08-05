import type { TKey } from "@/lib/i18n";
import type { TimelineItem } from "@/components/ui/Timeline";
import type { ActivityEventRow } from "@/lib/types";

const TONE_MAP: Record<string, TimelineItem["tone"]> = {
  contract_created: "default",
  contract_activated: "success",
  review_sent: "default",
  review_approved: "success",
  review_rejected: "danger",
  negotiation_generated: "default",
  approval_started: "default",
  approval_step_completed: "success",
  approval_rejected: "danger",
  signature_request_created: "default",
  signature_request_sent: "default",
  signer_signed: "success",
  signer_declined: "danger",
  signature_request_completed: "success",
  signed_document_generated: "success",
};

export function activityTitleKey(eventType: string): TKey {
  const key = `activity.${eventType}` as TKey;
  return key;
}

export function mapActivityEvents(
  events: ActivityEventRow[],
  t: (k: TKey) => string
): TimelineItem[] {
  return events.map((e) => {
    const titleKey = activityTitleKey(e.event_type);
    let title: string;
    try {
      title = t(titleKey);
      if (title === titleKey) title = e.event_type.replace(/_/g, " ");
    } catch {
      title = e.event_type.replace(/_/g, " ");
    }
    return {
      id: e.id,
      title,
      subtitle: e.comment ?? e.actor ?? undefined,
      time: e.created_at?.slice(0, 16) ?? undefined,
      tone: TONE_MAP[e.event_type] ?? "default",
    };
  });
}
