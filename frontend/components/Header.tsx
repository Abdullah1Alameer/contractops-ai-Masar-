"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

import SegmentedControl from "@/components/ui/SegmentedControl";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const links = [
  { href: "/contracts", key: "nav.contracts" },
  { href: "/upload", key: "nav.upload" },
  { href: "/dashboard", key: "nav.dashboard" },
  { href: "/flowdown", key: "nav.flowdown" },
] as const;

export default function Header() {
  const { t, lang, setLang } = useI18n();
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-50 border-b border-gray-200 bg-white/95 backdrop-blur-sm">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-4">
        <div className="flex flex-wrap items-center gap-6 lg:gap-10">
          <Link href="/contracts" className="flex items-center gap-2">
            <span className="rounded-md bg-brand-50 px-2 py-0.5 text-xs font-bold uppercase tracking-wide text-brand-700">
              AI
            </span>
            <span className="text-lg font-bold text-brand-800">{t("appName")}</span>
          </Link>
          <nav className="flex flex-wrap items-center gap-1">
            {links.map((l) => {
              const active = pathname === l.href || pathname.startsWith(`${l.href}/`);
              return (
                <Link
                  key={l.href}
                  href={l.href}
                  className={cn(
                    "relative rounded-lg px-3 py-2 text-sm font-semibold motion-safe:transition-colors",
                    active ? "text-brand-700" : "text-gray-600 hover:bg-muted-50 hover:text-gray-900"
                  )}
                >
                  {t(l.key)}
                  {active && (
                    <span className="absolute inset-x-2 -bottom-0.5 h-0.5 rounded-full bg-brand-600" aria-hidden />
                  )}
                </Link>
              );
            })}
          </nav>
        </div>
        <SegmentedControl
          value={lang}
          options={[
            { value: "ar", label: t("lang.ar") },
            { value: "en", label: t("lang.en") },
          ]}
          onChange={setLang}
        />
      </div>
    </header>
  );
}
