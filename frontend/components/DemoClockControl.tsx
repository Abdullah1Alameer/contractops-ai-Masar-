"use client";
import { useEffect, useState } from "react";

import { getDemoToday, setDemoToday } from "@/lib/api";
import { Card, CardBody } from "@/components/ui/Card";
import { useI18n } from "@/lib/i18n";

export default function DemoClockControl({ onChange }: { onChange: (isoDate: string) => void }) {
  const { t } = useI18n();
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getDemoToday()
      .then((r) => {
        setValue(r.today);
        onChange(r.today);
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load demo date once on mount
  }, []);

  const apply = async (next: string) => {
    setValue(next);
    setSaving(true);
    try {
      const r = await setDemoToday(next);
      onChange(r.today);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="mb-4 bg-muted-50/80">
      <CardBody className="flex flex-wrap items-center gap-3 py-3">
      <label className="text-sm font-semibold text-gray-700">{t("timeline.demoClock")}</label>
      <input
        type="date"
        className="rounded-lg border-2 border-gray-200 px-2 py-2 text-sm focus-visible:focus-ring"
        value={value}
        disabled={saving || !value}
        onChange={(e) => apply(e.target.value)}
      />
      </CardBody>
    </Card>
  );
}
