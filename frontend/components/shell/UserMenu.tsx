"use client";
import { useEffect, useRef, useState } from "react";

import DemoRoleSwitcher from "@/components/DemoRoleSwitcher";
import SegmentedControl from "@/components/ui/SegmentedControl";
import { useI18n } from "@/lib/i18n";

export default function UserMenu() {
  const { t, lang, setLang } = useI18n();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        className="focus-ring flex h-9 w-9 items-center justify-center rounded-full bg-brand-600 text-sm font-bold text-white"
        aria-label={t("user.menu.profile")}
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        {lang === "ar" ? "م" : "U"}
      </button>
      {open && (
        <div className="absolute end-0 z-50 mt-2 w-64 rounded-card border border-neutral-200 bg-white p-4 shadow-elevation-2">
          <p className="text-eyebrow mb-3">{t("user.menu.profile")}</p>
          <DemoRoleSwitcher />
          <div className="divider my-3" />
          <p className="mb-2 text-xs font-semibold text-neutral-500">{t("user.menu.language")}</p>
          <SegmentedControl
            value={lang}
            options={[
              { value: "ar", label: t("lang.ar") },
              { value: "en", label: t("lang.en") },
            ]}
            onChange={setLang}
          />
          <button type="button" className="mt-4 w-full text-start text-sm text-neutral-400" disabled>
            {t("user.menu.signout")}
          </button>
        </div>
      )}
    </div>
  );
}
