"use client";
import { useEffect, useState } from "react";

import { useToast } from "@/components/feedback/ToastProvider";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import {
  apiErrorCode,
  configureApprovalRoute,
  DEMO_ROLE_EVENT,
  DEMO_ROLE_STORAGE,
  fetchSavedRoute,
  fetchSavedRoutes,
} from "@/lib/api";
import { useI18n, type TKey } from "@/lib/i18n";
import type { ApprovalRouteStepInput, ContractApprovalRoute, SavedApprovalRoute } from "@/lib/types";
import { cn } from "@/lib/utils";

// Route builder shown before an internal-approval workflow exists — the
// fix for "the current flow creates a fixed default sequence of
// approvers." Every step here is explicit: which role/named approver,
// what order, which steps are mandatory, an optional label, and whether
// to save it for reuse. See docs/configurable-approval-routes-report.md.
const AVAILABLE_ROLES = ["business_owner", "legal", "finance", "executive", "sales", "manager"] as const;

// Must mirror the backend's ROUTE_ADMIN_ROLES exactly
// (app/services/approval_routes.py) — configuring/saving a route is
// gated to legal/executive there. Checking it here too means an
// unauthorized attempt is prevented before the request is ever sent,
// instead of surfacing the backend's raw approval_route_role_required
// error code. See docs/approval-route-role-error-audit.md.
const ROUTE_ADMIN_ROLES = new Set(["legal", "executive"]);

// Every backend error this endpoint can actually return
// (app/services/approval_routes.py::configure_contract_route), mapped to
// a localized message — a raw backend error code must never reach the
// user untranslated. Unmapped/unexpected codes (network errors, 404s,
// etc.) fall back to the generic error message.
const ERROR_KEYS: Record<string, TKey> = {
  approval_route_role_required: "approval.routeBuilder.roleRequiredTitle",
  approval_steps_required: "approval.routeBuilder.emptyRouteError",
  invalid_approver: "approval.routeBuilder.error.invalidApprover",
  duplicate_approver: "approval.routeBuilder.duplicateError",
  invalid_stage_transition: "approval.routeBuilder.error.invalidStage",
  approval_route_locked: "approval.routeBuilder.error.routeLocked",
};

type DraftStep = { role: string; approver_name: string; required: boolean };

function roleLabel(t: (k: TKey) => string, role: string): string {
  return t(`role.${role}` as TKey);
}

export default function ApprovalRouteBuilder({
  contractId,
  initialDraft,
  onConfigured,
}: {
  contractId: string;
  initialDraft?: ContractApprovalRoute | null;
  onConfigured: () => void;
}) {
  const { t } = useI18n();
  const toast = useToast();
  const [savedRoutes, setSavedRoutes] = useState<SavedApprovalRoute[]>([]);
  const [selectedSavedId, setSelectedSavedId] = useState<string>("");
  const [steps, setSteps] = useState<DraftStep[]>(
    initialDraft
      ? initialDraft.steps.map((s) => ({ role: s.role, approver_name: s.approver_name ?? "", required: s.required }))
      : [{ role: "legal", approver_name: "", required: true }]
  );
  const [routeName, setRouteName] = useState(initialDraft?.name ?? "");
  const [saveAsRoute, setSaveAsRoute] = useState(false);
  const [saveAsRouteName, setSaveAsRouteName] = useState("");
  const [sourceRouteId, setSourceRouteId] = useState<string | null>(initialDraft?.source_route_id ?? null);
  const [busy, setBusy] = useState(false);
  const [role, setRole] = useState("legal");
  const canConfigureRoute = ROUTE_ADMIN_ROLES.has(role);

  useEffect(() => {
    fetchSavedRoutes()
      .then((r) => setSavedRoutes(r.routes))
      .catch(() => setSavedRoutes([]));
  }, []);

  useEffect(() => {
    const saved = localStorage.getItem(DEMO_ROLE_STORAGE);
    if (saved) setRole(saved);
    const onRoleChange = () => setRole(localStorage.getItem(DEMO_ROLE_STORAGE) || "legal");
    window.addEventListener(DEMO_ROLE_EVENT, onRoleChange);
    return () => window.removeEventListener(DEMO_ROLE_EVENT, onRoleChange);
  }, []);

  const addApprover = () => setSteps((s) => [...s, { role: "legal", approver_name: "", required: true }]);
  const removeApprover = (index: number) => setSteps((s) => s.filter((_, i) => i !== index));
  const moveStep = (index: number, dir: -1 | 1) => {
    setSteps((s) => {
      const next = [...s];
      const target = index + dir;
      if (target < 0 || target >= next.length) return s;
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  };
  const updateStep = (index: number, patch: Partial<DraftStep>) =>
    setSteps((s) => s.map((step, i) => (i === index ? { ...step, ...patch } : step)));

  const useSavedRoute = async (id: string) => {
    setSelectedSavedId(id);
    setSourceRouteId(id || null);
    if (!id) return;
    try {
      const detail = await fetchSavedRoute(id);
      setSteps(detail.steps.map((s) => ({ role: s.role, approver_name: s.approver_name ?? "", required: s.required })));
      setRouteName(detail.name);
    } catch (error) {
      showApiError(error);
    }
  };

  // A raw backend error code (e.g. "approval_route_role_required") must
  // never reach the user untranslated — map it through ERROR_KEYS first.
  // See docs/approval-route-role-error-audit.md.
  const showApiError = (error: unknown) => {
    const code = apiErrorCode(error, "unknown");
    toast.error(t(ERROR_KEYS[code] ?? "common.error"));
  };

  const duplicateKey = (a: DraftStep, b: DraftStep) =>
    a.role === b.role && (a.approver_name || "").trim() === (b.approver_name || "").trim();
  const hasDuplicates = steps.some((s, i) => steps.some((other, j) => j !== i && duplicateKey(s, other)));

  const start = async () => {
    // Prevent the invalid submission entirely rather than let the backend
    // reject it — this is the same ROUTE_ADMIN_ROLES check the backend
    // enforces (app/services/approval_routes.py::_require_route_admin),
    // applied client-side first.
    if (!canConfigureRoute) {
      toast.error(t("approval.routeBuilder.roleRequiredTitle"));
      return;
    }
    if (steps.length === 0) {
      toast.error(t("approval.routeBuilder.emptyRouteError"));
      return;
    }
    if (hasDuplicates) {
      toast.error(t("approval.routeBuilder.duplicateError"));
      return;
    }
    setBusy(true);
    try {
      const body: {
        name?: string | null;
        steps: ApprovalRouteStepInput[];
        source_route_id?: string | null;
        save_as_route?: boolean;
        save_as_route_name?: string | null;
      } = {
        name: routeName.trim() || null,
        steps: steps.map((s) => ({
          role: s.role,
          approver_name: s.approver_name.trim() || null,
          required: s.required,
        })),
        source_route_id: sourceRouteId,
        save_as_route: saveAsRoute,
        save_as_route_name: saveAsRoute ? saveAsRouteName.trim() || routeName.trim() || null : null,
      };
      await configureApprovalRoute(contractId, body);
      onConfigured();
    } catch (error) {
      showApiError(error);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardBody className="space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-bold">{t("approval.configureRoute")}</h3>
          <Badge tone="info">{t("approval.routeBuilder.sequentialLabel")}</Badge>
        </div>
        <p className="text-sm text-neutral-600">{t("approval.routeBuilder.hint")}</p>
        <p className="rounded-lg border border-info-200/70 bg-info-50/60 p-2 text-xs text-info-900">
          {t("approval.routeBuilder.sequentialNote")}
        </p>

        {!canConfigureRoute && (
          <div role="alert" className="rounded-lg border border-warning-300 bg-warning-50 p-3 text-sm text-warning-900">
            <p className="font-semibold">{t("approval.routeBuilder.roleRequiredTitle")}</p>
            <p className="mt-1 text-xs">
              {t("approval.routeBuilder.roleRequiredBody").replace("{role}", roleLabel(t, role))}
            </p>
          </div>
        )}

        {savedRoutes.length > 0 && (
          <div className="space-y-2 rounded-lg border p-3">
            <p className="text-sm font-semibold">{t("approval.routeBuilder.savedRoutes")}</p>
            <div className="flex flex-wrap items-center gap-2">
              <select
                className="rounded border px-2 py-1.5 text-sm"
                value={selectedSavedId}
                onChange={(e) => useSavedRoute(e.target.value)}
              >
                <option value="">{t("approval.routeBuilder.selectSaved")}</option>
                {savedRoutes.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name} ({r.step_count})
                  </option>
                ))}
              </select>
              {selectedSavedId && (
                <span className="text-xs text-neutral-500">{t("approval.routeBuilder.customize")}</span>
              )}
            </div>
          </div>
        )}

        <label className="block text-sm">
          <span className="mb-1 block font-medium text-neutral-700">{t("approval.routeBuilder.routeName")}</span>
          <input
            className="w-full rounded-lg border px-3 py-2 text-sm"
            placeholder={t("approval.routeBuilder.routeNamePlaceholder")}
            value={routeName}
            onChange={(e) => setRouteName(e.target.value)}
          />
        </label>

        <div className="space-y-2">
          {steps.map((step, index) => (
            <div key={index} className="flex flex-wrap items-center gap-2 rounded-lg border p-2">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-100 text-xs font-bold text-brand-800">
                {index + 1}
              </span>
              <select
                className="rounded border px-2 py-1 text-sm"
                aria-label={t("approval.routeBuilder.role")}
                value={step.role}
                onChange={(e) => updateStep(index, { role: e.target.value })}
              >
                {AVAILABLE_ROLES.map((role) => (
                  <option key={role} value={role}>
                    {roleLabel(t, role)}
                  </option>
                ))}
              </select>
              <input
                className="min-w-[10rem] flex-1 rounded border px-2 py-1 text-sm"
                placeholder={t("approval.routeBuilder.approverName")}
                value={step.approver_name}
                onChange={(e) => updateStep(index, { approver_name: e.target.value })}
              />
              <label className="flex items-center gap-1 text-xs text-neutral-600">
                <input
                  type="checkbox"
                  checked={step.required}
                  onChange={(e) => updateStep(index, { required: e.target.checked })}
                />
                {t("approval.routeBuilder.required")}
              </label>
              <div className="ms-auto flex items-center gap-1">
                <button
                  type="button"
                  className="rounded border px-2 py-1 text-xs disabled:opacity-30"
                  disabled={index === 0}
                  aria-label={t("approval.routeBuilder.moveUp")}
                  onClick={() => moveStep(index, -1)}
                >
                  ↑
                </button>
                <button
                  type="button"
                  className="rounded border px-2 py-1 text-xs disabled:opacity-30"
                  disabled={index === steps.length - 1}
                  aria-label={t("approval.routeBuilder.moveDown")}
                  onClick={() => moveStep(index, 1)}
                >
                  ↓
                </button>
                <button
                  type="button"
                  className="rounded border border-danger-200 px-2 py-1 text-xs text-danger-700"
                  onClick={() => removeApprover(index)}
                >
                  {t("approval.routeBuilder.remove")}
                </button>
              </div>
            </div>
          ))}
        </div>

        <Button variant="secondary" size="sm" onClick={addApprover}>
          + {t("approval.routeBuilder.addApprover")}
        </Button>

        {steps.length > 0 && (
          <div className="rounded-lg border border-brand-200/70 bg-brand-50/40 p-3">
            <p className="mb-1 text-xs font-semibold uppercase text-brand-800">{t("approval.routeBuilder.preview")}</p>
            <ol className="space-y-0.5 text-sm text-neutral-800">
              {steps.map((s, i) => (
                <li key={i} className={cn(!s.required && "text-neutral-500 italic")}>
                  {i + 1}. {roleLabel(t, s.role)}
                  {s.approver_name.trim() && ` — ${s.approver_name.trim()}`}
                  {!s.required && ` (${t("approval.routeBuilder.optionalTag")})`}
                </li>
              ))}
            </ol>
          </div>
        )}

        <div className="space-y-2 rounded-lg border p-3">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={saveAsRoute} onChange={(e) => setSaveAsRoute(e.target.checked)} />
            {t("approval.routeBuilder.saveAsRoute")}
          </label>
          {saveAsRoute && (
            <input
              className="w-full rounded-lg border px-3 py-2 text-sm"
              placeholder={t("approval.routeBuilder.saveAsRouteNamePlaceholder")}
              value={saveAsRouteName}
              onChange={(e) => setSaveAsRouteName(e.target.value)}
            />
          )}
        </div>

        <Button variant="primary" loading={busy} disabled={steps.length === 0 || !canConfigureRoute} onClick={start}>
          {t("approval.routeBuilder.confirmRoute")}
        </Button>
      </CardBody>
    </Card>
  );
}
