"use client";
import Drawer from "@/components/ui/Drawer";
import EmptyState from "@/components/ui/EmptyState";
import Timeline from "@/components/ui/Timeline";
import { useShell } from "@/components/shell/ShellContext";
import { useI18n } from "@/lib/i18n";

const MOCK = [
  { id: "1", title: "Review sent", subtitle: "MSA — Acme Corp", time: "2026-08-04 10:00", tone: "default" as const },
  { id: "2", title: "Legal approved", subtitle: "NDA — Beta LLC", time: "2026-08-03 15:30", tone: "success" as const },
  { id: "3", title: "Signature requested", subtitle: "SOW — Gamma", time: "2026-08-02 09:15", tone: "default" as const },
];

export default function NotificationsDrawer() {
  const { notificationsOpen, setNotificationsOpen } = useShell();
  const { t } = useI18n();

  return (
    <Drawer open={notificationsOpen} onClose={() => setNotificationsOpen(false)} title={t("shell.notifications")} side="end">
      <p className="mb-4 text-hint">{t("notifications.demoHint")}</p>
      {MOCK.length === 0 ? (
        <EmptyState title={t("notifications.empty")} />
      ) : (
        <Timeline items={MOCK} />
      )}
    </Drawer>
  );
}
