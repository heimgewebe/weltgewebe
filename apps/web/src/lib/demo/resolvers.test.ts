import { describe, it, expect, vi, afterEach } from "vitest";
import {
  resolveAccountNodes,
  resolveNodeParticipants,
  resolveEdgeParticipants,
} from "./resolvers";

describe("Demo Resolvers", () => {
  it("resolveAccountNodes returns correct data", () => {
    const accountId = "7d97a42e-3704-4a33-a61f-0e0a6b4d65d8";
    const nodes = resolveAccountNodes(accountId);
    expect(nodes.length).toBeGreaterThan(0);
    expect(nodes).toContainEqual(
      expect.objectContaining({
        node_title: "fairschenkbox",
      }),
    );
  });

  it("resolveNodeParticipants returns correct data", () => {
    const nodeId = "b52be17c-4ab7-4434-98ce-520f86290cf0";
    const participants = resolveNodeParticipants(nodeId);
    expect(participants.length).toBeGreaterThan(0);
    expect(participants).toContainEqual(
      expect.objectContaining({
        account_title: "weltgewebeknoten1",
      }),
    );
  });

  it("resolveEdgeParticipants returns correct data", () => {
    const edgeId = "eb5f41ff-3e64-417e-ae7e-eecd9c886ecc";
    const details = resolveEdgeParticipants(edgeId);
    expect(details.source_details?.title).toBe("weltgewebeknoten1");
    expect(details.target_details?.title).toBe("fairschenkbox");
  });

  it("resolveEdgeParticipants returns null details for non-existent edge", () => {
    const details = resolveEdgeParticipants("non-existent");
    expect(details.source_details).toBeNull();
    expect(details.target_details).toBeNull();
  });
});

describe("resolveNodeParticipants — source_type contract", () => {
  afterEach(() => {
    vi.doUnmock("./demoData");
    vi.resetModules();
  });

  it("excludes edges whose source_type is not 'account'", async () => {
    vi.resetModules();
    const NODE_ID = "node-x";
    vi.doMock("./demoData", () => ({
      demoNodes: [],
      demoAccounts: [{ id: "acct-1", title: "Konto A", type: "garnrolle" }],
      demoEdges: [
        {
          id: "e-account",
          source_id: "acct-1",
          source_type: "account",
          target_id: NODE_ID,
          target_type: "node",
          edge_kind: "ref",
          note: "",
        },
        {
          id: "e-node",
          source_id: "node-y",
          source_type: "node",
          target_id: NODE_ID,
          target_type: "node",
          edge_kind: "ref",
          note: "",
        },
      ],
    }));
    const { resolveNodeParticipants: resolve } = await import("./resolvers");
    const result = resolve(NODE_ID);
    expect(result).toHaveLength(1);
    expect(result[0].account_id).toBe("acct-1");
  });
});
