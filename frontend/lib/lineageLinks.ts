import type { VersionLineageEvent } from "@/lib/types";

export function lineageDeepLink(contractId: string, event: VersionLineageEvent): string | null {
  const base = `/contracts/${contractId}`;
  const meta = event.metadata ?? {};
  switch (event.related_entity_type) {
    case "review_request":
      return `${base}?tab=review&review=${event.related_entity_id}`;
    case "negotiation":
      return `${base}?tab=negotiation&item=${event.related_entity_id}`;
    case "approval_workflow":
      return `${base}?tab=approvals&workflow=${event.related_entity_id}`;
    case "approval_step":
      if (meta.workflow_id) return `${base}?tab=approvals&workflow=${meta.workflow_id}`;
      return `${base}?tab=approvals`;
    case "signature_request":
      return `${base}?tab=signature&request=${event.related_entity_id}`;
    case "contract_version":
      if (event.event_type.includes("compar") || event.event_type === "versions_compared") {
        return `${base}?tab=versions`;
      }
      return `${base}?tab=versions`;
    default:
      if (event.event_category === "ai") return `${base}?tab=aiSummary`;
      if (event.event_type === "extraction_completed") return `${base}?tab=aiSummary`;
      if (event.event_category === "lifecycle") return `${base}?tab=activity`;
      return null;
  }
}

export function transitionReasonKey(reason: string): string {
  return `versions.transitionReason.${reason}`;
}
