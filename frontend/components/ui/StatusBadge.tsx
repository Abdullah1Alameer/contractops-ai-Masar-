"use client";
import StatusChip from "@/components/StatusChip";

/** Contract processing status (ready, failed, etc.) */
export default function StatusBadge({ status }: { status: import("@/lib/types").ContractStatus }) {
  return <StatusChip status={status} />;
}
