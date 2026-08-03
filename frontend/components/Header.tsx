"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

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
    <header className="border-b bg-white">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
        <div className="flex items-center gap-8">
          <Link href="/contracts" className="text-lg font-bold text-brand-700">
            {t("appName")}
          </Link>
          <nav className="flex items-center gap-1">
            {links.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className={cn(
                  "rounded-md px-3 py-1.5 text-sm font-medium",
                  pathname.startsWith(l.href) ? "bg-brand-50 text-brand-700" : "text-gray-600 hover:bg-gray-50"
                )}
              >
                {t(l.key)}
              </Link>
            ))}
          </nav>
        </div>
        <button
          onClick={() => setLang(lang === "ar" ? "en" : "ar")}
          className="rounded-md border px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
          aria-label="toggle language"
        >
          {lang === "ar" ? "English" : "العربية"}
        </button>
      </div>
    </header>
  );
}
