"use client";
import { useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { listFlowdownContracts, runFlowdown } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { FlowdownResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function FlowdownPicker({
  onResult,
  onRunning,
}: {
  onResult: (r: FlowdownResponse) => void;
  onRunning: (v: boolean) => void;
}) {
  const { t } = useI18n();
  const [mains, setMains] = useState<{ id: string; title: string }[]>([]);
  const [subs, setSubs] = useState<{ id: string; title: string }[]>([]);
  const [mainId, setMainId] = useState("");
  const [subId, setSubId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [running, setRunningLocal] = useState(false);

  useEffect(() => {
    listFlowdownContracts()
      .then((r) => {
        setMains(r.main.map((c) => ({ id: c.id, title: c.title })));
        setSubs(r.sub.map((c) => ({ id: c.id, title: c.title })));
      })
      .catch(() => {});
  }, []);

  const run = async () => {
    if (!mainId || !subId) {
      setError("pair");
      return;
    }
    setError(null);
    setRunningLocal(true);
    onRunning(true);
    try {
      const r = await runFlowdown(mainId, subId);
      onResult(r);
    } catch (e: unknown) {
      const code = e && typeof e === "object" && "code" in e ? String((e as { code: string }).code) : "ai";
      setError(code === "flowdown_ineligible_category" || code === "flowdown_wrong_pair" ? "eligibility" : "ai");
    } finally {
      setRunningLocal(false);
      onRunning(false);
    }
  };

  return (
    <Card className="mb-8">
      <CardBody>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <label className="block text-sm">
            <span className="mb-2 block font-semibold text-gray-700">{t("flowdown.picker.main")}</span>
            <select
              className="w-full rounded-lg border-2 border-gray-200 px-3 py-2.5 text-sm focus-visible:focus-ring"
              value={mainId}
              onChange={(e) => setMainId(e.target.value)}
            >
              <option value="">—</option>
              {mains.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="mb-2 block font-semibold text-gray-700">{t("flowdown.picker.sub")}</span>
            <select
              className="w-full rounded-lg border-2 border-gray-200 px-3 py-2.5 text-sm focus-visible:focus-ring"
              value={subId}
              onChange={(e) => setSubId(e.target.value)}
            >
              <option value="">—</option>
              {subs.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}
                </option>
              ))}
            </select>
          </label>
          <div className="flex items-end">
            <Button variant="primary" className="w-full" loading={running} onClick={run}>
              {t("flowdown.picker.run")}
            </Button>
          </div>
        </div>
        {error === "pair" && <p className="mt-3 text-sm text-warning-700">{t("flowdown.error.pair")}</p>}
        {error === "eligibility" && <p className="mt-3 text-sm text-warning-700">{t("flowdown.error.eligibility")}</p>}
        {error === "ai" && <p className="mt-3 text-sm text-danger-600">{t("flowdown.error.ai")}</p>}
      </CardBody>
    </Card>
  );
}

export function FlowdownRunningBanner({ show }: { show: boolean }) {
  const { t } = useI18n();
  if (!show) return null;
  return (
    <p
      className={cn(
        "mb-6 rounded-lg border border-brand-200 bg-brand-50 px-4 py-3 text-sm font-medium text-brand-800 motion-safe:animate-pulse"
      )}
    >
      {t("flowdown.running")}
    </p>
  );
}
