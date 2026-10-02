/** Small formatting helpers shared across the UI. */

export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

export function daysSince(iso: string, now: Date = new Date()): number {
  return Math.max(0, Math.floor((now.getTime() - new Date(iso).getTime()) / 86_400_000));
}

export function daysUntil(iso: string, now: Date = new Date()): number {
  return Math.ceil((new Date(iso).getTime() - now.getTime()) / 86_400_000);
}

/** Localised relative time ("vor 3 Tagen", "il y a 3 jours"). */
export function timeAgo(iso: string, locale = "de-CH", now: Date = new Date()): string {
  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
  const seconds = Math.round((new Date(iso).getTime() - now.getTime()) / 1000);
  const abs = Math.abs(seconds);
  if (abs < 60) return rtf.format(0, "minute");
  if (abs < 3600) return rtf.format(Math.round(seconds / 60), "minute");
  if (abs < 86_400) return rtf.format(Math.round(seconds / 3600), "hour");
  if (abs < 86_400 * 7) return rtf.format(Math.round(seconds / 86_400), "day");
  if (abs < 86_400 * 35) return rtf.format(Math.round(seconds / (86_400 * 7)), "week");
  return rtf.format(Math.round(seconds / (86_400 * 30)), "month");
}

export function shortDate(iso: string, locale = "de-CH"): string {
  return new Date(iso).toLocaleDateString(locale, { day: "numeric", month: "short" });
}

export function longDate(iso: string, locale = "de-CH"): string {
  return new Date(iso).toLocaleDateString(locale, { day: "numeric", month: "long", year: "numeric" });
}

export function dateTime(iso: string, locale = "de-CH"): string {
  return new Date(iso).toLocaleString(locale, {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Map a 1-4 rubric score to its colour token. */
export function scoreColor(score: number | null | undefined): string {
  if (score == null) return "var(--color-line)";
  if (score < 1.75) return "var(--color-score-1)";
  if (score < 2.5) return "var(--color-score-2)";
  if (score < 3.25) return "var(--color-score-3)";
  return "var(--color-score-4)";
}

export function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  return words
    .slice(0, 2)
    .map((w) => w[0]!.toUpperCase())
    .join("");
}

export function avg(values: number[]): number | null {
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
}
