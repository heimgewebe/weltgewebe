import type { Edge, MapEdge } from "$lib/map/types";

export const FADEN_LIFETIME_MS = 168 * 60 * 60 * 1000;
export const FADEN_PROJECTION_REFRESH_MS = 24 * 60 * 60 * 1000;

const RFC3339_PATTERN =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:Z|[+-](\d{2}):(\d{2}))$/;

function parseCanonicalRfc3339Ms(value: string): number | null {
  const match = RFC3339_PATTERN.exec(value);
  if (!match) return null;

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const hour = Number(match[4]);
  const minute = Number(match[5]);
  const second = Number(match[6]);
  // The sign is intentionally left to Date.parse; these groups only enforce
  // RFC3339 offset bounds.
  const offsetHour = match[7] == null ? 0 : Number(match[7]);
  const offsetMinute = match[8] == null ? 0 : Number(match[8]);
  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate();
  if (
    year < 1 ||
    month < 1 ||
    month > 12 ||
    day < 1 ||
    day > daysInMonth ||
    hour > 23 ||
    minute > 59 ||
    second > 59 ||
    offsetHour > 23 ||
    offsetMinute > 59
  ) {
    return null;
  }

  // The regex captures only the offset magnitude for bounds checking; the
  // sign and absolute-instant calculation remain delegated to Date.parse.
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}

/** Parse lifecycle data once when an edge crosses the API/UI boundary. */
export function normalizeEdgeLifecycle(edge: Edge): MapEdge {
  if (edge.expires_at == null) {
    return { ...edge, lifecycle: { kind: "legacy" } };
  }
  if (edge.created_at == null) {
    return { ...edge, lifecycle: { kind: "invalid" } };
  }

  const createdAtMs = parseCanonicalRfc3339Ms(edge.created_at);
  const expiresAtMs = parseCanonicalRfc3339Ms(edge.expires_at);
  if (
    createdAtMs == null ||
    expiresAtMs == null ||
    expiresAtMs - createdAtMs !== FADEN_LIFETIME_MS
  ) {
    return { ...edge, lifecycle: { kind: "invalid" } };
  }

  return {
    ...edge,
    lifecycle: { kind: "faden", createdAtMs, expiresAtMs },
  };
}

/** Linear target opacity, sampled by the map at a 24-hour cadence. */
export function edgeOpacityAt(edge: MapEdge, nowMs: number): number {
  if (edge.lifecycle.kind === "legacy") return 1;
  if (edge.lifecycle.kind === "invalid" || !Number.isFinite(nowMs)) return 0;

  const { createdAtMs, expiresAtMs } = edge.lifecycle;
  if (nowMs < createdAtMs || nowMs >= expiresAtMs) return 0;

  return Math.max(0, Math.min(1, (expiresAtMs - nowMs) / FADEN_LIFETIME_MS));
}

/** Earliest active expiry; exact removal remains independent of the daily refresh. */
export function nextEdgeExpiryAt(
  edges: MapEdge[],
  nowMs: number,
): number | null {
  let next: number | null = null;
  for (const edge of edges) {
    if (edge.lifecycle.kind !== "faden") continue;
    const { expiresAtMs } = edge.lifecycle;
    if (expiresAtMs <= nowMs) continue;
    if (next == null || expiresAtMs < next) next = expiresAtMs;
  }
  return next;
}
