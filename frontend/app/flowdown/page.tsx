"use client";
import { useState } from "react";

import FlowdownFindings from "@/components/FlowdownFindings";
import FlowdownPicker, { FlowdownRunningBanner } from "@/components/FlowdownPicker";
import FlowdownSummary from "@/components/FlowdownSummary";
import SourceViewer from "@/components/SourceViewer";
import Badge from "@/components/ui/Badge";
import { Card, CardHeader } from "@/components/ui/Card";
import { useI18n } from "@/lib/i18n";
import type { FlowdownResponse, SourceTarget } from "@/lib/types";

export default function FlowdownPage() {
  const { t } = useI18n();
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<FlowdownResponse | null>(null);
  const [mainTarget, setMainTarget] = useState<SourceTarget | null>(null);
  const [subTarget, setSubTarget] = useState<SourceTarget | null>(null);

  return (
    <div className="space-y-6 motion-safe:animate-fadeIn">
      <h1 className="text-2xl font-bold text-gray-900 md:text-3xl">{t("flowdown.title")}</h1>

      <FlowdownPicker
        onRunning={setRunning}
        onResult={(r) => {
          setResult(r);
          setMainTarget(null);
          setSubTarget(null);
        }}
      />

      <FlowdownRunningBanner show={running} />

      {result && (
        <>
          <FlowdownSummary summary={result.summary} />
          <div className="grid gap-8 lg:grid-cols-2">
            <div className="min-w-0">
              <FlowdownFindings findings={result.findings} onViewMain={setMainTarget} onViewSub={setSubTarget} />
            </div>
            <div className="min-w-0 space-y-6">
              <Card className="overflow-hidden">
                <CardHeader className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-bold text-gray-900">{t("flowdown.viewer.main")}</span>
                  {result.main.title && <Badge tone="info">{result.main.title}</Badge>}
                </CardHeader>
                <div className="h-[calc(50vh-120px)] min-h-[240px]">
                  {result.main.id ? (
                    <SourceViewer contractId={result.main.id} target={mainTarget} />
                  ) : (
                    <p className="p-4 text-sm text-gray-400">—</p>
                  )}
                </div>
              </Card>
              <Card className="overflow-hidden">
                <CardHeader className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-bold text-gray-900">{t("flowdown.viewer.sub")}</span>
                  {result.sub.title && <Badge tone="neutral">{result.sub.title}</Badge>}
                </CardHeader>
                <div className="h-[calc(50vh-120px)] min-h-[240px]">
                  {result.sub.id ? (
                    <SourceViewer contractId={result.sub.id} target={subTarget} />
                  ) : (
                    <p className="p-4 text-sm text-gray-400">—</p>
                  )}
                </div>
              </Card>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
