import { describe, expect, it } from "vitest";
import type { MapEntityViewModel } from "$lib/map/types";
import { getMapSearchTermsNormalized } from "./searchIndex";

function makeNode(title: string): MapEntityViewModel {
  return {
    type: "node",
    id: title,
    title,
    kind: "Werkstatt",
    tags: ["Commons"],
    created_at: "2025-01-01T00:00:00Z",
    lat: 53.5,
    lon: 10,
  };
}

describe("map search index", () => {
  it("reuses terms for one entity identity and rebuilds them for new entity state", () => {
    const alpha = makeNode("Alpha");
    const first = getMapSearchTermsNormalized(alpha);
    expect(getMapSearchTermsNormalized(alpha)).toBe(first);
    expect(first).toContain("alpha");

    const beta = makeNode("Beta");
    const second = getMapSearchTermsNormalized(beta);
    expect(second).not.toBe(first);
    expect(second).toContain("beta");
    expect(second).not.toContain("alpha");
  });
});
