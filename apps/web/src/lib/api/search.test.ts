import { describe, expect, it, vi } from "vitest";
import { buildSimilarNodeQuery, nodeToMapEntity, searchNodes } from "./search";
import type { Node } from "$lib/map/types";

const NODE: Node = {
  id: "node-1",
  kind: "Werkstatt",
  title: "Radwerkstatt",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
  summary: "Gemeinsam Fahrräder reparieren",
  info: "Offene Werkstatt",
  tags: ["Fahrrad", "Hilfe"],
  location: { lat: 54.9, lon: 8.3 },
};

describe("searchNodes", () => {
  it("calls the authorized server search with credentials and stable kind filters", async () => {
    const fetcher = vi.fn<typeof fetch>(
      async () =>
        new Response(
          JSON.stringify({
            items: [NODE],
            mode: "hybrid",
            generation_id: "generation-1",
            offset: 0,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
    );

    const response = await searchNodes("  Fahrrad Hilfe  ", {
      kinds: ["Werkstatt", "Treffpunkt", "Werkstatt"],
      apiBase: "https://api.example.test",
      fetcher: fetcher as typeof fetch,
    });

    expect(response.items).toEqual([NODE]);
    expect(fetcher).toHaveBeenCalledOnce();
    const [url, init] = fetcher.mock.calls[0];
    expect(String(url)).toBe(
      "https://api.example.test/api/search?q=Fahrrad+Hilfe&limit=10&kinds=Treffpunkt%2CWerkstatt",
    );
    expect(init).toMatchObject({ credentials: "include" });
  });

  it("maps server nodes to canonical map entities", () => {
    expect(nodeToMapEntity(NODE)).toMatchObject({
      type: "node",
      id: "node-1",
      lat: 54.9,
      lon: 8.3,
      kind: "Werkstatt",
    });
  });
});

describe("buildSimilarNodeQuery", () => {
  it("uses node content as bounded machine-similarity context", () => {
    expect(buildSimilarNodeQuery(NODE)).toBe(
      "Radwerkstatt · Werkstatt · Gemeinsam Fahrräder reparieren · Offene Werkstatt · Fahrrad · Hilfe",
    );
  });

  it("never exceeds the T006 query contract", () => {
    expect(buildSimilarNodeQuery({ title: "x".repeat(600) })).toHaveLength(512);
  });
});
