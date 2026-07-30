import type { Edge, MapEdge } from "$lib/map/types";

export const FADEN_LIFETIME_MS = 168 * 60 * 60 * 1000;
export const FADEN_PROJECTION_REFRESH_MS = 60_000;

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
  // Offset groups only enforce RFC3339 bounds; Date.parse owns the sign.
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

  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function invalid(edge: Edge): MapEdge {
  return { ...edge, lifecycle: { kind: "invalid" } };
}

/** Parse lifecycle data once when an edge crosses the API/UI boundary. */
export function normalizeEdgeLifecycle(edge: Edge): MapEdge {
  // Public contract always includes created_at. Omitted ≠ undated legacy:
  // undated requires explicit null/null. Fail closed on non-canonical pairs.
  const created = edge.created_at;
  const expires = edge.expires_at;
  if (created === undefined) return invalid(edge);
  if (created === null) {
    return {
      ...edge,
      lifecycle: { kind: expires === null ? "legacy" : "invalid" },
    };
  }

  const createdAtMs = parseCanonicalRfc3339Ms(created);
  if (createdAtMs == null || expires === null) return invalid(edge);

  const expiresAtMs =
    expires === undefined
      ? createdAtMs + FADEN_LIFETIME_MS
      : parseCanonicalRfc3339Ms(expires);
  // Derived path is finite when createdAtMs is; parse path already rejects NaN.
  if (expiresAtMs == null || expiresAtMs - createdAtMs !== FADEN_LIFETIME_MS) {
    return invalid(edge);
  }

  return {
    ...edge,
    lifecycle: { kind: "faden", createdAtMs, expiresAtMs },
  };
}

/** Continuous linear opacity, sampled often enough to remain visually smooth. */
export function edgeOpacityAt(edge: MapEdge, nowMs: number): number {
  if (edge.lifecycle.kind === "legacy") return 1;
  if (edge.lifecycle.kind === "invalid" || !Number.isFinite(nowMs)) return 0;

  const { createdAtMs, expiresAtMs } = edge.lifecycle;
  if (nowMs < createdAtMs || nowMs >= expiresAtMs) return 0;

  return Math.max(0, Math.min(1, (expiresAtMs - nowMs) / FADEN_LIFETIME_MS));
}

/** Earliest active expiry; exact removal remains independent of periodic refreshes. */
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
