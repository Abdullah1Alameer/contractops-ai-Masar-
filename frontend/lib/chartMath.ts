/** Rounds a max value up to a clean, evenly-divisible tick ceiling — small
 * integer counts (deadlines/obligations per month) stay whole-number ticks. */
export function niceCeil(max: number, min = 4): number {
  const v = Math.max(max, min);
  const step = v <= 10 ? 2 : v <= 50 ? 10 : v <= 200 ? 50 : Math.pow(10, Math.floor(Math.log10(v)));
  return Math.ceil(v / step) * step;
}

export function monthLabel(monthKey: string, lang: "ar" | "en"): string {
  const [y, m] = monthKey.split("-").map(Number);
  const d = new Date(Date.UTC(y, m - 1, 1));
  return new Intl.DateTimeFormat(lang === "ar" ? "ar-SA" : "en-US", { month: "short", timeZone: "UTC" }).format(d);
}
