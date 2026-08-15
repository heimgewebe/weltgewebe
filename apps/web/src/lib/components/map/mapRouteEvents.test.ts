import { describe, expect, it } from "vitest";
import { resolveMapDomainChange } from "./mapRouteEvents";
import type { Node } from "$lib/map/types";

const node: Node = {
  id: "node-1",
  kind: "Knoten",
  title: "Aktueller Knoten",
  created_at: "2026-08-15T07:00:00.000Z",
  updated_at: "2026-08-15T07:30:00.000Z",
  tags: [],
  location: { lat: 53.5, lon: 10 },
};

describe("resolveMapDomainChange", () => {
  it("keeps a canonical successful update on the local map path", () => {
    expect(
      resolveMapDomainChange({
        kind: "node",
        id: node.id,
        action: "updated",
        node,
      }),
    ).toEqual({ kind: "local-node-update", node });
  });

  it("fails closed to a reload when the update payload identity mismatches", () => {
    expect(
      resolveMapDomainChange({
        kind: "node",
        id: "node-2",
        action: "updated",
        node,
      }),
    ).toEqual({ kind: "reload-domain-data" });
  });

  it.each(["deleted", "archived"] as const)(
    "keeps %s on the authoritative reload path",
    (action) => {
      expect(
        resolveMapDomainChange({
          kind: "node",
          id: node.id,
          action,
        }),
      ).toEqual({ kind: "reload-domain-data" });
    },
  );
});
