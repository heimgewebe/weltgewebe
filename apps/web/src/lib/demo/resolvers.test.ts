import { describe, it, expect } from "vitest";
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
