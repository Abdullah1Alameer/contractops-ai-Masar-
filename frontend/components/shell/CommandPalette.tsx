"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { useShell } from "@/components/shell/ShellContext";
import { useI18n, type TKey } from "@/lib/i18n";

const NAV: { href: string; key: TKey }[] = [
  { href: "/dashboard", key: "nav.dashboard" },
  { href: "/contracts", key: "nav.contracts" },
  { href: "/upload", key: "nav.upload" },
  { href: "/reviews", key: "nav.reviews" },
  { href: "/negotiations", key: "nav.negotiations" },
  { href: "/approvals", key: "nav.approvals" },
  { href: "/signatures", key: "nav.signatures" },
  { href: "/versions", key: "nav.versions" },
  { href: "/flowdown", key: "nav.flowdown" },
  { href: "/settings", key: "nav.settings" },
  { href: "/help", key: "nav.help" },
];

export default function CommandPalette() {
  const { paletteOpen, setPaletteOpen } = useShell();
  const { t } = useI18n();
  const router = useRouter();
  const [q, setQ] = useState("");

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setPaletteOpen(true);
      }
      if (e.key === "Escape") setPaletteOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setPaletteOpen]);

  const items = useMemo(() => {
    const query = q.trim().toLowerCase();
    return NAV.filter((n) => !query || t(n.key).toLowerCase().includes(query) || n.href.includes(query));
  }, [q, t]);

  if (!paletteOpen) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center bg-black/40 p-4 pt-[15vh]"
      role="dialog"
      aria-modal
      onClick={() => setPaletteOpen(false)}
    >
      <div
        className="w-full max-w-lg rounded-xl border border-gray-200 bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <input
          autoFocus
          className="w-full border-b border-gray-100 px-4 py-3 text-sm outline-none"
          placeholder={t("shell.commandPalette")}
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <ul className="max-h-72 overflow-auto py-2">
          {items.map((item) => (
            <li key={item.href}>
              <button
                type="button"
                className="flex w-full px-4 py-2 text-start text-sm hover:bg-muted-50"
                onClick={() => {
                  setPaletteOpen(false);
                  router.push(item.href);
                }}
              >
                {t(item.key)}
                <span className="ms-auto text-xs text-gray-400">{item.href}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
