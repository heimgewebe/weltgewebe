import { afterEach, describe, expect, it, vi } from "vitest";
import { deleteNode, replaceNode } from "./domainWrites";

afterEach(() => vi.unstubAllGlobals());

function replaceWithStaleVersion() {
  return replaceNode(
    "node-a",
    {
      title: "Entwurf",
      kind: "Ort",
      address: "Testweg 1",
      location: { lat: 54, lon: 8 },
      tags: [],
    },
    "stale",
  );
}

describe("domain writes", () => {
  it("keeps the structured delete conflict from JSON responses", async () => {
    const body = {
      code: "node_conversation_not_empty",
      message:
        "node deletion is blocked because its public conversation contains contributions",
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(body), {
          status: 409,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(deleteNode("node-a", "version-a")).rejects.toMatchObject({
      status: 409,
      body,
    });
  });

  it("keeps a plain-text conflict reason during rolling deployments", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(
            "node deletion blocked because its public conversation contains contributions",
            { status: 409 },
          ),
        ),
    );

    await expect(deleteNode("node-a", "version-a")).rejects.toMatchObject({
      status: 409,
      body: "node deletion blocked because its public conversation contains contributions",
    });
  });

  it("keeps the current node from direct 412 JSON responses", async () => {
    const current = {
      id: "node-a",
      title: "Aktuell",
      kind: "Ort",
      address: "Testweg 1",
      location: { lat: 54, lon: 8 },
      tags: [],
      updated_at: "2026-07-26T08:00:00Z",
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(current), {
          status: 412,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(replaceWithStaleVersion()).rejects.toMatchObject({
      status: 412,
      body: current,
    });
  });

  it.each([
    ["plain text", "stale precondition"],
    [
      "a non-node JSON problem",
      JSON.stringify({ code: "node_version_conflict", message: "conflict" }),
    ],
  ])("drops %s from 412 responses", async (_label, body) => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(body, { status: 412 })),
    );

    await expect(replaceWithStaleVersion()).rejects.toMatchObject({
      status: 412,
      body: undefined,
    });
  });
});
