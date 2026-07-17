import { describe, expect, it } from "vitest";
import {
  edgeOpacityAt,
  FADEN_LIFETIME_MS,
  FADEN_PROJECTION_REFRESH_MS,
  nextEdgeExpiryAt,
  normalizeEdgeLifecycle,
} from "$lib/map/edgeLifecycle";
import type { Edge } from "$lib/map/types";

const createdAt = Date.parse("2026-07-17T10:00:00Z");
const rawEdge: Edge = {
  id: "edge-1",
  source_id: "source",
  target_id: "target",
  edge_kind: "reference",
  created_at: new Date(createdAt).toISOString(),
  expires_at: new Date(createdAt + FADEN_LIFETIME_MS).toISOString(),
};
const edge = normalizeEdgeLifecycle(rawEdge);

describe("edge lifecycle", () => {
  it("parses once and fades continuously across exactly 168 hours", () => {
    expect(edge.lifecycle).toEqual({
      kind: "faden",
      createdAtMs: createdAt,
      expiresAtMs: createdAt + FADEN_LIFETIME_MS,
    });
    expect(FADEN_PROJECTION_REFRESH_MS).toBe(60_000);
    expect(edgeOpacityAt(edge, createdAt)).toBe(1);
    expect(edgeOpacityAt(edge, createdAt + FADEN_LIFETIME_MS / 2)).toBe(0.5);
    expect(
      edgeOpacityAt(edge, createdAt + FADEN_LIFETIME_MS - 1),
    ).toBeGreaterThan(0);
    expect(edgeOpacityAt(edge, createdAt + FADEN_LIFETIME_MS)).toBe(0);
  });

  it("keeps legacy records visible and fails closed for invalid data", () => {
    const legacy = normalizeEdgeLifecycle({ ...rawEdge, expires_at: null });
    expect(legacy.lifecycle).toEqual({ kind: "legacy" });
    expect(edgeOpacityAt(legacy, createdAt)).toBe(1);

    for (const invalid of [
      normalizeEdgeLifecycle({ ...rawEdge, created_at: "invalid" }),
      normalizeEdgeLifecycle({ ...rawEdge, created_at: "2026-07-17" }),
      normalizeEdgeLifecycle({
        ...rawEdge,
        created_at: "2026-07-17T10:00:00+24:00",
      }),
      normalizeEdgeLifecycle({
        ...rawEdge,
        created_at: "2026-02-31T10:00:00Z",
        expires_at: "2026-03-10T10:00:00Z",
      }),
      normalizeEdgeLifecycle({ ...rawEdge, created_at: null }),
      normalizeEdgeLifecycle({
        ...rawEdge,
        expires_at: new Date(createdAt + FADEN_LIFETIME_MS + 1).toISOString(),
      }),
    ]) {
      expect(invalid.lifecycle).toEqual({ kind: "invalid" });
      expect(edgeOpacityAt(invalid, createdAt)).toBe(0);
    }
  });

  it("accepts signed offsets and rejects out-of-range offsets", () => {
    const offsetEdge = normalizeEdgeLifecycle({
      ...rawEdge,
      created_at: "2026-07-17T10:00:00-02:00",
      expires_at: "2026-07-24T10:00:00-02:00",
    });
    expect(offsetEdge.lifecycle).toEqual({
      kind: "faden",
      createdAtMs: Date.parse("2026-07-17T10:00:00-02:00"),
      expiresAtMs: Date.parse("2026-07-24T10:00:00-02:00"),
    });

    const invalidOffset = normalizeEdgeLifecycle({
      ...rawEdge,
      created_at: "2026-07-17T10:00:00+24:00",
      expires_at: "2026-07-24T10:00:00+24:00",
    });
    expect(invalidOffset.lifecycle).toEqual({ kind: "invalid" });
  });

  it("keeps exact expiry scheduling separate from the periodic fade cadence", () => {
    expect(nextEdgeExpiryAt([edge], createdAt)).toBe(
      createdAt + FADEN_LIFETIME_MS,
    );
    expect(nextEdgeExpiryAt([edge], createdAt + FADEN_LIFETIME_MS)).toBeNull();
  });
});
