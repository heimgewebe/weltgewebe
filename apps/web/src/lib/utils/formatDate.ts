const DEFAULT_FORMATTER = new Intl.DateTimeFormat("de-DE", {
  timeZone: "UTC",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

const FALLBACK = "Unbekannt";

export function formatDate(
  isoString: string | undefined | null,
  formatter: Intl.DateTimeFormat = DEFAULT_FORMATTER,
): string {
  if (!isoString) return FALLBACK;
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return FALLBACK;
  try {
    return formatter.format(date);
  } catch {
    return FALLBACK;
  }
}
