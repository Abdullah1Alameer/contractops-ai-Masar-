"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useToast } from "@/components/feedback/ToastProvider";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import { SkeletonCard } from "@/components/ui/Skeleton";
import {
  api,
  apiErrorCode,
  createContractFromTemplate,
  fetchTemplateDetail,
  previewTemplateContract,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { TemplateDetail, TemplatePreview } from "@/lib/types";
import { formatDate, formatNum } from "@/lib/utils";

// The real "Use Template" flow: detail -> variables form -> preview (exactly
// what will be created) -> create contract as draft, template_id set,
// version 1 = the generated document -> continue through the normal
// upload/extract pipeline like any other contract. See
// docs/signature-placement-and-template-flow-report.md.
type Step = "loading" | "not_found" | "detail" | "form" | "preview" | "creating";

export default function TemplateDetailPage() {
  const { t, lang } = useI18n();
  const toast = useToast();
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const templateId = params.id;

  const [step, setStep] = useState<Step>("loading");
  const [template, setTemplate] = useState<TemplateDetail | null>(null);
  const [variables, setVariables] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<TemplatePreview | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetchTemplateDetail(templateId)
      .then((tpl) => {
        setTemplate(tpl);
        setStep("detail");
      })
      .catch(() => setStep("not_found"));
  }, [templateId]);

  const title = template ? (lang === "ar" ? template.title_ar : template.title_en) : "";
  const description = template ? (lang === "ar" ? template.description_ar : template.description_en) : "";

  const startForm = () => setStep("form");

  const runPreview = async () => {
    if (!template) return;
    setBusy(true);
    try {
      const result = await previewTemplateContract(template.id, variables);
      if (result.missing_variables.length > 0) {
        toast.warning(t("templates.missingVariables"));
        return;
      }
      setPreview(result);
      setStep("preview");
    } catch (error) {
      toast.error(apiErrorCode(error, t("common.error")));
    } finally {
      setBusy(false);
    }
  };

  const confirmCreate = async () => {
    if (!template) return;
    setStep("creating");
    try {
      const created = await createContractFromTemplate(template.id, variables);
      await api(`/api/contracts/${created.id}/extract`, { method: "POST" });
      toast.success(t("templates.createSuccess"));
      router.push(`/contracts/${created.id}`);
    } catch (error) {
      toast.error(apiErrorCode(error, t("common.error")));
      setStep("preview");
    }
  };

  if (step === "loading") return <SkeletonCard rows={4} />;

  if (step === "not_found" || !template) {
    return (
      <div className="space-y-4">
        <EmptyState title={t("templates.notFound")} />
        <Link href="/templates" className="text-sm font-semibold text-brand-700 hover:underline">
          {t("templates.back")}
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Link href="/templates" className="text-sm font-semibold text-brand-700 hover:underline">
        ← {t("templates.back")}
      </Link>

      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={step === "detail" ? "info" : "subtle"}>{t("templates.step.detail")}</Badge>
        <Badge tone={step === "form" ? "info" : "subtle"}>{t("templates.step.form")}</Badge>
        <Badge tone={step === "preview" || step === "creating" ? "info" : "subtle"}>{t("templates.step.preview")}</Badge>
      </div>

      {(step === "detail" || step === "form" || step === "preview" || step === "creating") && (
        <Card>
          <CardBody className="space-y-3">
            <h1 className="text-2xl font-bold text-neutral-900">{title}</h1>
            <div className="flex flex-wrap gap-2 text-sm text-neutral-600">
              <span className="pill">
                {t("templates.category")}: {template.category ?? "—"}
              </span>
              <span className="pill">
                {t("templates.language")}: {template.language}
              </span>
              <span className="pill">
                {t("templates.industry")}: {template.industry ?? "—"}
              </span>
            </div>
            <p className="text-xs text-neutral-500">
              {t("templates.lastUpdated")}: {template.updated_at ? formatDate(template.updated_at, lang) : "—"} ·{" "}
              {t("templates.usage")}: {formatNum(template.usage_count, lang)}
            </p>
          </CardBody>
        </Card>
      )}

      {step === "detail" && (
        <Card>
          <CardBody className="space-y-4">
            <div>
              <h2 className="mb-1 text-sm font-semibold uppercase text-neutral-500">{t("templates.description")}</h2>
              <p className="text-sm text-neutral-800">{description}</p>
            </div>
            <div>
              <h2 className="mb-1 text-sm font-semibold uppercase text-neutral-500">{t("templates.clausesIncluded")}</h2>
              <ul className="list-disc space-y-1 ps-5 text-sm text-neutral-800">
                {template.clauses.map((c, i) => (
                  <li key={i}>{lang === "ar" ? c.title_ar : c.title_en}</li>
                ))}
              </ul>
            </div>
            <Button variant="primary" onClick={startForm}>
              {t("templates.createFromTemplate")}
            </Button>
          </CardBody>
        </Card>
      )}

      {step === "form" && (
        <Card>
          <CardBody className="space-y-4">
            <div>
              <h2 className="text-sm font-semibold uppercase text-neutral-500">{t("templates.variablesTitle")}</h2>
              <p className="text-xs text-neutral-500">{t("templates.variablesHint")}</p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {template.variables.map((field) => (
                <label key={field.key} className={field.type === "textarea" ? "sm:col-span-2" : undefined}>
                  <span className="mb-1 block text-sm font-medium text-neutral-700">
                    {lang === "ar" ? field.label_ar : field.label_en}
                    {field.required && <span className="text-danger-600"> *</span>}
                  </span>
                  {field.type === "textarea" ? (
                    <textarea
                      className="w-full rounded-lg border px-3 py-2 text-sm"
                      rows={3}
                      value={variables[field.key] ?? ""}
                      onChange={(e) => setVariables((v) => ({ ...v, [field.key]: e.target.value }))}
                    />
                  ) : (
                    <input
                      type={field.type === "number" ? "number" : field.type === "date" ? "date" : "text"}
                      className="w-full rounded-lg border px-3 py-2 text-sm"
                      value={variables[field.key] ?? ""}
                      onChange={(e) => setVariables((v) => ({ ...v, [field.key]: e.target.value }))}
                    />
                  )}
                </label>
              ))}
            </div>
            <Button variant="primary" loading={busy} onClick={runPreview}>
              {t("templates.previewButton")}
            </Button>
          </CardBody>
        </Card>
      )}

      {(step === "preview" || step === "creating") && preview && (
        <Card>
          <CardBody className="space-y-4">
            <div>
              <h2 className="text-sm font-semibold uppercase text-neutral-500">{t("templates.previewTitle")}</h2>
              <p className="text-xs text-neutral-500">{t("templates.previewHint")}</p>
            </div>
            <div className="space-y-3">
              {(lang === "ar" ? preview.sections_ar : preview.sections_en).map((s, i) => (
                <div key={i} className="rounded-lg border bg-muted-50/40 p-3">
                  <h3 className="mb-1 text-sm font-semibold text-neutral-900">{s.title}</h3>
                  <p dir="auto" className="bidi-plaintext whitespace-pre-wrap text-sm text-neutral-700">
                    {s.body}
                  </p>
                </div>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" disabled={step === "creating"} onClick={() => setStep("form")}>
                {t("templates.editVariables")}
              </Button>
              <Button variant="primary" loading={step === "creating"} onClick={confirmCreate}>
                {step === "creating" ? t("templates.creating") : t("templates.confirmCreate")}
              </Button>
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  );
}
