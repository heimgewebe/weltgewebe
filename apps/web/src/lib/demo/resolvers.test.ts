import { describe, it, expect } from "vitest";
import {
  resolveAccountNodes,
  resolveNodeParticipants,
  resolveEdgeParticipants,
} from "./resolvers";
import { demoEdges } from "./demoData";

describe("Demo Resolvers", () => {
  describe("Invariant Checks (Edge Index Safety)", () => {
    it("resolveAccountNodes returns ONLY edges matching account-to-node contract", () => {
      const accountId = "7d97a42e-3704-4a33-a61f-0e0a6b4d65d8";
      const results = resolveAccountNodes(accountId);

      // Verify each result corresponds to a valid edge in demoEdges that meets the contract
      for (const res of results) {
        const originalEdge = demoEdges.find((e) => e.id === res.edge_id);
        expect(originalEdge).toBeDefined();
        expect(originalEdge?.source_id).toBe(accountId);
        expect(originalEdge?.source_type).toBe("account");
        expect(originalEdge?.target_type).toBe("node");
      }
    });

    it("resolveNodeParticipants returns ONLY source accounts matching node contract", () => {
      const nodeId = "b52be17c-4ab7-4434-98ce-520f86290cf0";
      const results = resolveNodeParticipants(nodeId);

      for (const res of results) {
        const originalEdge = demoEdges.find((e) => e.id === res.edge_id);
        expect(originalEdge).toBeDefined();
        expect(originalEdge?.target_id).toBe(nodeId);
        expect(originalEdge?.target_type).toBe("node");
        expect(originalEdge?.source_type).toBe("account");
      }
    });

    it("resolveEdgeParticipants remains consistent for existing and missing IDs", () => {
      // Existing
      const edgeId = "eb5f41ff-3e64-417e-ae7e-eecd9c886ecc";
      const details = resolveEdgeParticipants(edgeId);
      expect(details.source_details).not.toBeNull();
      expect(details.target_details).not.toBeNull();

      // Missing
      const missingDetails = resolveEdgeParticipants("non-existent-uuid");
      expect(missingDetails.source_details).toBeNull();
      expect(missingDetails.target_details).toBeNull();
    });
  });

  describe("Functional Correctness", () => {
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
  });
});
