import { afterEach, describe, expect, it, vi } from "vitest";
import { deleteNode, replaceNode } from "./domainWrites";

afterEach(() => vi.unstubAllGlobals());

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

  it("keeps structured version-conflict evidence from JSON responses", async () => {
    const current = {
      id: "node-a",
      title: "Aktuell",
      updated_at: "2026-07-26T08:00:00Z",
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            code: "node_version_conflict",
            message: "conflict",
            current,
          }),
          {
            status: 412,
            headers: { "Content-Type": "application/json" },
          },
        ),
      ),
    );

    await expect(
      replaceNode(
        "node-a",
        {
          title: "Entwurf",
          kind: "Ort",
          address: "Testweg 1",
          location: { lat: 54, lon: 8 },
          tags: [],
        },
        "stale",
      ),
    ).rejects.toMatchObject({
      status: 412,
      body: {
        code: "node_version_conflict",
        message: "conflict",
        current,
      },
    });
  });
});
