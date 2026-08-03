"use client";
// Renders "١٢ أكتوبر ٢٠٢٦ · ٢٨ ربيع الآخر ١٤٤٨" — hijri comes from the backend
// /api/util/hijri endpoint (hijri-converter / Umm al-Qura is the single source
// of truth; we never convert client-side).
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

interface HijriResp {
  gregorian: string;
  gregorian_ar: string;
  hijri: { formatted_ar: string };
}

const cache = new Map<string, Promise<HijriResp>>();

function fetchDual(date: string): Promise<HijriResp> {
  if (!cache.has(date)) cache.set(date, api<HijriResp>(`/api/util/hijri?date=${date}`));
  return cache.get(date)!;
}

export default function DualDate({ date }: { date: string | null | undefined }) {
  const { lang } = useI18n();
  const [dual, setDual] = useState<HijriResp | null>(null);

  useEffect(() => {
    let alive = true;
    if (date) fetchDual(date).then((d) => alive && setDual(d)).catch(() => {});
    return () => {
      alive = false;
    };
  }, [date]);

  if (!date) return <span className="text-gray-400">—</span>;
  const greg =
    lang === "ar"
      ? dual?.gregorian_ar ?? date
      : new Intl.DateTimeFormat("en-GB", { dateStyle: "long" }).format(new Date(date));
  return (
    <span dir={lang === "ar" ? "rtl" : "ltr"} className="whitespace-nowrap">
      {greg}
      {dual && <span className="text-gray-500"> · {dual.hijri.formatted_ar}</span>}
    </span>
  );
}
