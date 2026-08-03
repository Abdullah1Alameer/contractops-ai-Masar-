"use client";
import { useEffect, useState } from "react";

import { getDemoToday, setDemoToday } from "@/lib/api";
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
    <div className="mb-4 flex flex-wrap items-center gap-3 rounded-lg border bg-gray-50 px-4 py-3">
      <label className="text-sm font-medium text-gray-700">{t("timeline.demoClock")}</label>
      <input
        type="date"
        className="rounded-md border px-2 py-1 text-sm"
        value={value}
        disabled={saving || !value}
        onChange={(e) => apply(e.target.value)}
      />
    </div>
  );
}
