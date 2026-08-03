"use client";
// Enterprise-style persistent nav rail for the dashboard route. Sits on the
// "start" edge of the flex row, which is the right side under the app's
// default RTL — and correctly moves to the left if the user switches to en/LTR.
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const links = [
  { href: "/dashboard", key: "nav.dashboard" },
  { href: "/contracts", key: "nav.contracts" },
  { href: "/upload", key: "nav.upload" },
  { href: "/flowdown", key: "nav.flowdown" },
] as const;

export default function Sidebar() {
  const { t } = useI18n();
  const pathname = usePathname();

  return (
    <aside className="w-56 shrink-0 self-start bg-oceanic py-6 pe-4 ps-6">
      <nav className="flex flex-col gap-3">
        {links.map((l) => {
          const activeLink = pathname.startsWith(l.href);
          return (
            <Link
              key={l.href}
              href={l.href}
              className={cn(
                "rounded-sm px-4 py-2.5 text-center text-sm font-semibold transition-colors",
                activeLink
                  ? "bg-nocturnal text-white shadow"
                  : "border border-white/15 text-white/80 hover:border-white/30 hover:bg-white/5 hover:text-white"
              )}
            >
              {t(l.key)}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
