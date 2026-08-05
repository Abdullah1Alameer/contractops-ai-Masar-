"use client";
import { useState } from "react";

import { TabList, TabPanel, Tabs, TabTrigger } from "@/components/ui/Tabs";
import { useI18n, type TKey } from "@/lib/i18n";

const TABS: { id: string; key: TKey }[] = [
  { id: "profile", key: "settings.tab.profile" },
  { id: "workspace", key: "settings.tab.workspace" },
  { id: "notifications", key: "settings.tab.notifications" },
  { id: "integrations", key: "settings.tab.integrations" },
];

export default function SettingsPage() {
  const { t } = useI18n();
  const [tab, setTab] = useState("profile");

  return (
    <div className="space-y-6">
      <h1 className="text-title">{t("nav.settings")}</h1>
      <Tabs value={tab} onValueChange={setTab}>
        <TabList>
          {TABS.map(({ id, key }) => (
            <TabTrigger key={id} value={id}>
              {t(key)}
            </TabTrigger>
          ))}
        </TabList>
        {TABS.map(({ id }) => (
          <TabPanel key={id} value={id}>
            <div className="surface-panel mt-4 space-y-4 p-6">
              <p className="text-hint">{t("placeholder.comingSoonHint")}</p>
              <input className="w-full rounded-lg border px-3 py-2 text-sm" disabled placeholder={t("settings.tab.profile")} />
            </div>
          </TabPanel>
        ))}
      </Tabs>
    </div>
  );
}
