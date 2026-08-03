"use client";
// TODO(F4): flow-down comparison screen. Call POST /api/flowdown with
// {main_contract_id, subcontract_id}, render findings (mirrored/partial/missing)
// with links to both contracts' clauses. The route + heading are wired — real
// data will light this up with zero routing work.
import { useI18n } from "@/lib/i18n";

export default function FlowdownPage() {
  const { t } = useI18n();
  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold">{t("flowdown.title")}</h1>
      <div className="rounded-xl border border-dashed bg-white p-10 text-center">
        <p className="mb-2 text-lg font-semibold text-gray-700">{t("common.wip")}</p>
        <p className="text-sm text-gray-500">{t("flowdown.wip")}</p>
      </div>
    </div>
  );
}
