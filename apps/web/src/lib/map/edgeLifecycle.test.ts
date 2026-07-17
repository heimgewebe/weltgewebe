import { describe, expect, it } from "vitest";
import { edgeOpacityAt, FADEN_LIFETIME_MS } from "$lib/map/edgeLifecycle";
import type { Edge } from "$lib/map/types";

const createdAt = Date.parse("2026-07-17T10:00:00Z");
const edge: Edge = {
  id: "edge-1",
  source_id: "source",
  target_id: "target",
  edge_kind: "reference",
  created_at: new Date(createdAt).toISOString(),
  expires_at: new Date(createdAt + FADEN_LIFETIME_MS).toISOString(),
};

describe("edgeOpacityAt", () => {
  it("fades linearly across exactly 168 hours", () => {
    expect(edgeOpacityAt(edge, createdAt)).toBe(1);
    expect(edgeOpacityAt(edge, createdAt + FADEN_LIFETIME_MS / 2)).toBe(0.5);
    expect(
      edgeOpacityAt(edge, createdAt + FADEN_LIFETIME_MS - 1),
    ).toBeGreaterThan(0);
    expect(edgeOpacityAt(edge, createdAt + FADEN_LIFETIME_MS)).toBe(0);
  });

  it("keeps legacy records without expires_at visible", () => {
    expect(edgeOpacityAt({ ...edge, expires_at: null }, createdAt)).toBe(1);
  });

  it("fails closed for future, malformed, missing, or non-canonical lifecycle data", () => {
    expect(edgeOpacityAt(edge, createdAt - 1)).toBe(0);
    expect(edgeOpacityAt({ ...edge, created_at: "invalid" }, createdAt)).toBe(
      0,
    );
    expect(
      edgeOpacityAt({ ...edge, created_at: "2026-07-17" }, createdAt),
    ).toBe(0);
    expect(
      edgeOpacityAt(
        {
          ...edge,
          created_at: "2026-02-31T10:00:00Z",
          expires_at: "2026-03-10T10:00:00Z",
        },
        createdAt,
      ),
    ).toBe(0);
    expect(edgeOpacityAt({ ...edge, created_at: null }, createdAt)).toBe(0);
    expect(
      edgeOpacityAt(
        {
          ...edge,
          expires_at: new Date(createdAt + FADEN_LIFETIME_MS + 1).toISOString(),
        },
        createdAt,
      ),
    ).toBe(0);
  });
});
