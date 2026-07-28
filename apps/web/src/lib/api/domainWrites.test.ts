import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApiRequestError,
  deleteNode,
  replaceNode,
  updateOwnGarnrolle,
} from "./domainWrites";

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
  it("returns the structured node deletion receipt", async () => {
    const receipt = {
      node_id: "node-a",
      node_state: "removed",
      removed_edge_ids: ["edge-a"],
      conversation: {
        effect: "archived",
        archive_id: "conversation-a",
        archive_url: "/api/conversations/conversation-a",
      },
    } as const;
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(receipt), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(deleteNode("node-a", "version-a")).resolves.toEqual(receipt);
    expect(fetch).toHaveBeenCalledWith("/api/nodes/node-a", {
      method: "DELETE",
      headers: { "If-Match": '"version-a"' },
      credentials: "include",
    });
  });

  it("accepts the JSONL not-applicable deletion effect", async () => {
    const receipt = {
      node_id: "node-a",
      node_state: "removed",
      removed_edge_ids: [],
      conversation: { effect: "not_applicable" },
    } as const;
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(receipt), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(deleteNode("node-a")).resolves.toEqual(receipt);
  });

  it("rejects malformed successful deletion receipts", async () => {
    const malformed = {
      node_id: "node-a",
      node_state: "removed",
      removed_edge_ids: [],
      conversation: {
        effect: "archived",
        archive_id: "conversation-a",
        archive_url: "/api/conversations/another-conversation",
      },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(malformed), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    const error = await deleteNode("node-a").catch((reason) => reason);
    expect(error).toBeInstanceOf(ApiRequestError);
    expect(error).toMatchObject({ status: 502, body: malformed });
  });

  it("rejects non-string edge identifiers in successful deletion receipts", async () => {
    const malformed = {
      node_id: "node-a",
      node_state: "removed",
      removed_edge_ids: ["edge-a", 7],
      conversation: { effect: "deleted_empty" },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(malformed), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    const error = await deleteNode("node-a").catch((reason) => reason);
    expect(error).toBeInstanceOf(ApiRequestError);
    expect(error).toMatchObject({ status: 502, body: malformed });
  });

  it("rejects a successful empty deletion response instead of accepting a null receipt", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(null, { status: 204 })),
    );

    const error = await deleteNode("node-a").catch((reason) => reason);
    expect(error).toBeInstanceOf(ApiRequestError);
    expect(error).toMatchObject({ status: 502, body: undefined });
  });

  it("rejects invalid JSON in successful deletion responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("not-json", { status: 200 })),
    );

    const error = await deleteNode("node-a").catch((reason) => reason);
    expect(error).toBeInstanceOf(ApiRequestError);
    expect(error).toMatchObject({ status: 502, body: undefined });
  });

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
    [
      "a node-shaped response for another id",
      JSON.stringify({
        id: "node-b",
        title: "Andere Version",
        updated_at: "2026-07-26T08:00:00Z",
      }),
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

  it("keeps non-node 412 bodies on non-node write paths", async () => {
    const body = { code: "profile_version_conflict", message: "conflict" };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(body), {
          status: 412,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(
      updateOwnGarnrolle({
        title: "Garnrolle",
        tags: [],
        map_state: "not_on_map",
      }),
    ).rejects.toMatchObject({ status: 412, body });
  });
});
