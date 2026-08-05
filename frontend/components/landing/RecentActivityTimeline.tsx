"use client";

import Link from "next/link";

import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import SectionHeader from "@/components/ui/SectionHeader";
import Timeline from "@/components/ui/Timeline";
import { mapActivityEvents } from "@/lib/activity";
import { useI18n } from "@/lib/i18n";
import type { ActivityEventRow } from "@/lib/types";

type ActivityRow = ActivityEventRow & { contract_id?: string; contract_title?: string };

export default function RecentActivityTimeline({ events }: { events: ActivityRow[] }) {
  const { t } = useI18n();
  const base = mapActivityEvents(events, t);
  const items = base.map((item, i) => {
    const raw = events[i];
    const cid = raw?.contract_id;
    const title = cid ? (
      <Link href={`/contracts/${cid}`} className="link-strong">
        {item.title}
        {raw.contract_title ? ` · ${raw.contract_title}` : ""}
      </Link>
    ) : (
      item.title
    );
    return { ...item, title };
  });

  return (
    <Card className="surface-panel border-0 shadow-none">
      <CardHeader>
        <SectionHeader title={t("home.recentActivity.title")} />
      </CardHeader>
      <CardBody>
        {items.length === 0 ? (
          <EmptyState title={t("common.empty")} />
        ) : (
          <Timeline items={items} />
        )}
      </CardBody>
    </Card>
  );
}
