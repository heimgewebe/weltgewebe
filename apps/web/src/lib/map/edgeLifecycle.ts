import type { Edge } from "$lib/map/types";

export const FADEN_LIFETIME_MS = 168 * 60 * 60 * 1000;

const RFC3339_PATTERN =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:Z|[+-](\d{2}):(\d{2}))$/;

function parseRfc3339Ms(value: string): number | null {
  const match = RFC3339_PATTERN.exec(value);
  if (!match) return null;

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const hour = Number(match[4]);
  const minute = Number(match[5]);
  const second = Number(match[6]);
  const offsetHour = match[7] == null ? 0 : Number(match[7]);
  const offsetMinute = match[8] == null ? 0 : Number(match[8]);
  if (
    year < 1 ||
    month < 1 ||
    month > 12 ||
    day < 1 ||
    hour > 23 ||
    minute > 59 ||
    second > 59 ||
    offsetHour > 23 ||
    offsetMinute > 59
  ) {
    return null;
  }

  // Date.parse normalises some impossible calendar dates. Validate the local
  // calendar component independently before accepting the absolute instant.
  const calendar = new Date(0);
  calendar.setUTCFullYear(year, month - 1, day);
  calendar.setUTCHours(hour, minute, second, 0);
  if (
    calendar.getUTCFullYear() !== year ||
    calendar.getUTCMonth() !== month - 1 ||
    calendar.getUTCDate() !== day ||
    calendar.getUTCHours() !== hour ||
    calendar.getUTCMinutes() !== minute ||
    calendar.getUTCSeconds() !== second
  ) {
    return null;
  }

  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}

/** Continuous active-projection opacity for an unverzwirnter Faden. */
export function edgeOpacityAt(edge: Edge, nowMs: number): number {
  if (edge.expires_at == null) return 1;
  if (edge.created_at == null || !Number.isFinite(nowMs)) return 0;

  const createdAt = parseRfc3339Ms(edge.created_at);
  const expiresAt = parseRfc3339Ms(edge.expires_at);
  if (createdAt == null || expiresAt == null) return 0;
  if (expiresAt - createdAt !== FADEN_LIFETIME_MS) return 0;
  if (nowMs < createdAt || nowMs >= expiresAt) return 0;

  return Math.max(0, Math.min(1, (expiresAt - nowMs) / FADEN_LIFETIME_MS));
}
