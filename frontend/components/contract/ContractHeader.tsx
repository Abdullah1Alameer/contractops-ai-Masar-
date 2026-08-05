"use client";
import Link from "next/link";

import SendForReviewDialog from "@/components/SendForReviewDialog";
import StatusChip from "@/components/StatusChip";
import TypeBadge from "@/components/TypeBadge";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import { useI18n } from "@/lib/i18n";
import type { ContractDetail } from "@/lib/types";

export default function ContractHeader({
  detail,
  contractId,
  onStartApproval,
  onCreateSignature,
}: {
  detail: ContractDetail;
  contractId: string;
  onStartApproval?: () => void;
  onCreateSignature?: () => void;
}) {
  const { t } = useI18n();
  const stage = detail.stage ?? "negotiation";

  return (
    <div className="card-surface p-4 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-bold text-gray-900 md:text-2xl">{detail.title}</h1>
            <Badge tone="subtle">{stage}</Badge>
          </div>
          <p className="text-sm text-gray-600">
            {detail.party_b ?? "—"}
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <TypeBadge type={detail.type} />
            <StatusChip status={detail.status} />
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {["ready", "needs_review"].includes(detail.status) && <SendForReviewDialog contractId={contractId} />}
          {onStartApproval && (
            <Button variant="secondary" size="sm" onClick={onStartApproval}>
              {t("approval.start")}
            </Button>
          )}
          {onCreateSignature && (
            <Button variant="secondary" size="sm" onClick={onCreateSignature}>
              {t("signature.create")}
            </Button>
          )}
          <Link href="/contracts">
            <Button variant="ghost" size="sm">
              {t("nav.contracts")}
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
