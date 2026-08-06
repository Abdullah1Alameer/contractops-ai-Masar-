"use client";
import { useEffect, useState } from "react";

import { DEMO_ROLE_EVENT, DEMO_ROLE_STORAGE } from "@/lib/api";
import { useI18n, type TKey } from "@/lib/i18n";

// "sales" and "manager" were added for configurable approval routes — a
// route step can require either. See docs/configurable-approval-routes-report.md.
const ROLES = ["business_owner", "legal", "finance", "executive", "sales", "manager"] as const;

export default function DemoRoleSwitcher() {
  const { t } = useI18n();
  const [role, setRole] = useState<string>("legal");

  useEffect(() => {
    const saved = localStorage.getItem(DEMO_ROLE_STORAGE);
    if (saved && ROLES.includes(saved as (typeof ROLES)[number])) setRole(saved);
  }, []);

  const onChange = (r: string) => {
    setRole(r);
    localStorage.setItem(DEMO_ROLE_STORAGE, r);
    window.dispatchEvent(new Event(DEMO_ROLE_EVENT));
  };

  return (
    <label className="flex flex-col items-end gap-0.5 text-xs text-gray-500">
      <span className="font-semibold">{t("role.demoSwitcher")}</span>
      <select
        className="rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-sm font-medium text-gray-800"
        value={role}
        onChange={(e) => onChange(e.target.value)}
      >
        {ROLES.map((r) => (
          <option key={r} value={r}>
            {t(`role.${r}` as TKey)}
          </option>
        ))}
      </select>
    </label>
  );
}
