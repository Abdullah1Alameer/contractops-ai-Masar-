"use client";

import { useEffect, useMemo, useState } from "react";

import { useI18n } from "@/lib/i18n";

export default function HeroGreeting() {
  const { t, lang } = useI18n();
  const [name, setName] = useState("");

  useEffect(() => {
    setName(localStorage.getItem("demoUser") || localStorage.getItem("demoDisplayName") || "");
  }, []);

  const greetingKey = useMemo(() => {
    const h = new Date().getHours();
    if (h < 12) return "home.greeting.morning" as const;
    if (h < 17) return "home.greeting.afternoon" as const;
    return "home.greeting.evening" as const;
  }, []);

  const who = name || t("home.greeting.fallbackName");

  return (
    <div className="hero-gradient surface-glass p-6 md:p-8 motion-safe:animate-fadeIn">
      <p className="text-eyebrow text-brand-700 dark:text-brand-300">{t("appName")}</p>
      <h1 className="mt-2 text-title">
        {t(greetingKey)}
        {lang === "ar" ? "، " : ", "}
        <span className="text-brand-700 dark:text-brand-400">{who}</span>
      </h1>
      <p className="mt-3 max-w-2xl text-hint md:text-base">{t("home.subtitle")}</p>
    </div>
  );
}
