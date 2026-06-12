import { describe, it, expect } from "vitest";
import {
  resolveAccountNodes,
  resolveNodeParticipants,
  resolveEdgeParticipants,
  resolveNode,
  resolveAccount,
  resolveEdge,
  getNodeEntries,
  getAccountEntries,
  getEdgeEntries,
} from "./resolvers";
import { demoEdges, demoNodes, demoAccounts } from "./demoData";

describe("Demo Resolvers", () => {
  describe("Invariant Checks (Edge Index Safety)", () => {
    it("demo edge IDs are unique", () => {
      const edgeIds = demoEdges.map((e) => e.id);
      expect(new Set(edgeIds).size).toBe(edgeIds.length);

      describe("resolveNode", () => {
        it("should find an existing node", () => {
          expect(resolveNode("b52be17c-4ab7-4434-98ce-520f86290cf0")).toEqual(
            demoNodes.find(
              (n) => n.id === "b52be17c-4ab7-4434-98ce-520f86290cf0",
            ),
          );
        });
        it("should return undefined for an unknown node ID", () => {
          expect(resolveNode("unknown-node")).toBeUndefined();
        });
      });

      describe("resolveAccount", () => {
        it("should find an existing account", () => {
          expect(
            resolveAccount("7d97a42e-3704-4a33-a61f-0e0a6b4d65d8"),
          ).toEqual(
            demoAccounts.find(
              (a) => a.id === "7d97a42e-3704-4a33-a61f-0e0a6b4d65d8",
            ),
          );
        });
        it("should return undefined for an unknown account ID", () => {
          expect(resolveAccount("unknown-acc")).toBeUndefined();
        });
      });

      describe("resolveEdge", () => {
        it("should find an existing edge", () => {
          expect(resolveEdge("eb5f41ff-3e64-417e-ae7e-eecd9c886ecc")).toEqual(
            demoEdges.find(
              (e) => e.id === "eb5f41ff-3e64-417e-ae7e-eecd9c886ecc",
            ),
          );
        });
        it("should return undefined for an unknown edge ID", () => {
          expect(resolveEdge("unknown-edge")).toBeUndefined();
        });
      });

      describe("Entry functions", () => {
        it("should match getNodeEntries output", () => {
          expect(getNodeEntries()).toEqual(
            demoNodes.map((n) => ({ id: n.id })),
          );
        });

        it("should match getAccountEntries output", () => {
          expect(getAccountEntries()).toEqual(
            demoAccounts.map((a) => ({ id: a.id })),
          );
        });

        it("should match getEdgeEntries output", () => {
          expect(getEdgeEntries()).toEqual(
            demoEdges.map((e) => ({ id: e.id })),
          );
        });
      });
    });

    it("resolveAccountNodes matches the old linear account-to-node edge semantics", () => {
      const accountId = "7d97a42e-3704-4a33-a61f-0e0a6b4d65d8";

      const expectedEdgeIds = demoEdges
        .filter(
          (e) =>
            e.source_id === accountId &&
            e.source_type === "account" &&
            e.target_type === "node",
        )
        .map((e) => e.id)
        .sort();

      const actualEdgeIds = resolveAccountNodes(accountId)
        .map((r) => r.edge_id)
        .sort();

      expect(actualEdgeIds).toEqual(expectedEdgeIds);

      describe("resolveNode", () => {
        it("should find an existing node", () => {
          expect(resolveNode("b52be17c-4ab7-4434-98ce-520f86290cf0")).toEqual(
            demoNodes.find(
              (n) => n.id === "b52be17c-4ab7-4434-98ce-520f86290cf0",
            ),
          );
        });
        it("should return undefined for an unknown node ID", () => {
          expect(resolveNode("unknown-node")).toBeUndefined();
        });
      });

      describe("resolveAccount", () => {
        it("should find an existing account", () => {
          expect(
            resolveAccount("7d97a42e-3704-4a33-a61f-0e0a6b4d65d8"),
          ).toEqual(
            demoAccounts.find(
              (a) => a.id === "7d97a42e-3704-4a33-a61f-0e0a6b4d65d8",
            ),
          );
        });
        it("should return undefined for an unknown account ID", () => {
          expect(resolveAccount("unknown-acc")).toBeUndefined();
        });
      });

      describe("resolveEdge", () => {
        it("should find an existing edge", () => {
          expect(resolveEdge("eb5f41ff-3e64-417e-ae7e-eecd9c886ecc")).toEqual(
            demoEdges.find(
              (e) => e.id === "eb5f41ff-3e64-417e-ae7e-eecd9c886ecc",
            ),
          );
        });
        it("should return undefined for an unknown edge ID", () => {
          expect(resolveEdge("unknown-edge")).toBeUndefined();
        });
      });

      describe("Entry functions", () => {
        it("should match getNodeEntries output", () => {
          expect(getNodeEntries()).toEqual(
            demoNodes.map((n) => ({ id: n.id })),
          );
        });

        it("should match getAccountEntries output", () => {
          expect(getAccountEntries()).toEqual(
            demoAccounts.map((a) => ({ id: a.id })),
          );
        });

        it("should match getEdgeEntries output", () => {
          expect(getEdgeEntries()).toEqual(
            demoEdges.map((e) => ({ id: e.id })),
          );
        });
      });
    });

    it("resolveNodeParticipants matches the old linear node participant edge semantics", () => {
      const nodeId = "b52be17c-4ab7-4434-98ce-520f86290cf0";

      const expectedEdgeIds = demoEdges
        .filter(
          (e) =>
            e.target_id === nodeId &&
            e.target_type === "node" &&
            e.source_type === "account",
        )
        .map((e) => e.id)
        .sort();

      const actualEdgeIds = resolveNodeParticipants(nodeId)
        .map((r) => r.edge_id)
        .sort();

      expect(actualEdgeIds).toEqual(expectedEdgeIds);

      describe("resolveNode", () => {
        it("should find an existing node", () => {
          expect(resolveNode("b52be17c-4ab7-4434-98ce-520f86290cf0")).toEqual(
            demoNodes.find(
              (n) => n.id === "b52be17c-4ab7-4434-98ce-520f86290cf0",
            ),
          );
        });
        it("should return undefined for an unknown node ID", () => {
          expect(resolveNode("unknown-node")).toBeUndefined();
        });
      });

      describe("resolveAccount", () => {
        it("should find an existing account", () => {
          expect(
            resolveAccount("7d97a42e-3704-4a33-a61f-0e0a6b4d65d8"),
          ).toEqual(
            demoAccounts.find(
              (a) => a.id === "7d97a42e-3704-4a33-a61f-0e0a6b4d65d8",
            ),
          );
        });
        it("should return undefined for an unknown account ID", () => {
          expect(resolveAccount("unknown-acc")).toBeUndefined();
        });
      });

      describe("resolveEdge", () => {
        it("should find an existing edge", () => {
          expect(resolveEdge("eb5f41ff-3e64-417e-ae7e-eecd9c886ecc")).toEqual(
            demoEdges.find(
              (e) => e.id === "eb5f41ff-3e64-417e-ae7e-eecd9c886ecc",
            ),
          );
        });
        it("should return undefined for an unknown edge ID", () => {
          expect(resolveEdge("unknown-edge")).toBeUndefined();
        });
      });

      describe("Entry functions", () => {
        it("should match getNodeEntries output", () => {
          expect(getNodeEntries()).toEqual(
            demoNodes.map((n) => ({ id: n.id })),
          );
        });

        it("should match getAccountEntries output", () => {
          expect(getAccountEntries()).toEqual(
            demoAccounts.map((a) => ({ id: a.id })),
          );
        });

        it("should match getEdgeEntries output", () => {
          expect(getEdgeEntries()).toEqual(
            demoEdges.map((e) => ({ id: e.id })),
          );
        });
      });
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

      describe("resolveNode", () => {
        it("should find an existing node", () => {
          expect(resolveNode("b52be17c-4ab7-4434-98ce-520f86290cf0")).toEqual(
            demoNodes.find(
              (n) => n.id === "b52be17c-4ab7-4434-98ce-520f86290cf0",
            ),
          );
        });
        it("should return undefined for an unknown node ID", () => {
          expect(resolveNode("unknown-node")).toBeUndefined();
        });
      });

      describe("resolveAccount", () => {
        it("should find an existing account", () => {
          expect(
            resolveAccount("7d97a42e-3704-4a33-a61f-0e0a6b4d65d8"),
          ).toEqual(
            demoAccounts.find(
              (a) => a.id === "7d97a42e-3704-4a33-a61f-0e0a6b4d65d8",
            ),
          );
        });
        it("should return undefined for an unknown account ID", () => {
          expect(resolveAccount("unknown-acc")).toBeUndefined();
        });
      });

      describe("resolveEdge", () => {
        it("should find an existing edge", () => {
          expect(resolveEdge("eb5f41ff-3e64-417e-ae7e-eecd9c886ecc")).toEqual(
            demoEdges.find(
              (e) => e.id === "eb5f41ff-3e64-417e-ae7e-eecd9c886ecc",
            ),
          );
        });
        it("should return undefined for an unknown edge ID", () => {
          expect(resolveEdge("unknown-edge")).toBeUndefined();
        });
      });

      describe("Entry functions", () => {
        it("should match getNodeEntries output", () => {
          expect(getNodeEntries()).toEqual(
            demoNodes.map((n) => ({ id: n.id })),
          );
        });

        it("should match getAccountEntries output", () => {
          expect(getAccountEntries()).toEqual(
            demoAccounts.map((a) => ({ id: a.id })),
          );
        });

        it("should match getEdgeEntries output", () => {
          expect(getEdgeEntries()).toEqual(
            demoEdges.map((e) => ({ id: e.id })),
          );
        });
      });
    });

    describe("resolveNode", () => {
      it("should find an existing node", () => {
        expect(resolveNode("b52be17c-4ab7-4434-98ce-520f86290cf0")).toEqual(
          demoNodes.find(
            (n) => n.id === "b52be17c-4ab7-4434-98ce-520f86290cf0",
          ),
        );
      });
      it("should return undefined for an unknown node ID", () => {
        expect(resolveNode("unknown-node")).toBeUndefined();
      });
    });

    describe("resolveAccount", () => {
      it("should find an existing account", () => {
        expect(resolveAccount("7d97a42e-3704-4a33-a61f-0e0a6b4d65d8")).toEqual(
          demoAccounts.find(
            (a) => a.id === "7d97a42e-3704-4a33-a61f-0e0a6b4d65d8",
          ),
        );
      });
      it("should return undefined for an unknown account ID", () => {
        expect(resolveAccount("unknown-acc")).toBeUndefined();
      });
    });

    describe("resolveEdge", () => {
      it("should find an existing edge", () => {
        expect(resolveEdge("eb5f41ff-3e64-417e-ae7e-eecd9c886ecc")).toEqual(
          demoEdges.find(
            (e) => e.id === "eb5f41ff-3e64-417e-ae7e-eecd9c886ecc",
          ),
        );
      });
      it("should return undefined for an unknown edge ID", () => {
        expect(resolveEdge("unknown-edge")).toBeUndefined();
      });
    });

    describe("Entry functions", () => {
      it("should match getNodeEntries output", () => {
        expect(getNodeEntries()).toEqual(demoNodes.map((n) => ({ id: n.id })));
      });

      it("should match getAccountEntries output", () => {
        expect(getAccountEntries()).toEqual(
          demoAccounts.map((a) => ({ id: a.id })),
        );
      });

      it("should match getEdgeEntries output", () => {
        expect(getEdgeEntries()).toEqual(demoEdges.map((e) => ({ id: e.id })));
      });
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

      describe("resolveNode", () => {
        it("should find an existing node", () => {
          expect(resolveNode("b52be17c-4ab7-4434-98ce-520f86290cf0")).toEqual(
            demoNodes.find(
              (n) => n.id === "b52be17c-4ab7-4434-98ce-520f86290cf0",
            ),
          );
        });
        it("should return undefined for an unknown node ID", () => {
          expect(resolveNode("unknown-node")).toBeUndefined();
        });
      });

      describe("resolveAccount", () => {
        it("should find an existing account", () => {
          expect(
            resolveAccount("7d97a42e-3704-4a33-a61f-0e0a6b4d65d8"),
          ).toEqual(
            demoAccounts.find(
              (a) => a.id === "7d97a42e-3704-4a33-a61f-0e0a6b4d65d8",
            ),
          );
        });
        it("should return undefined for an unknown account ID", () => {
          expect(resolveAccount("unknown-acc")).toBeUndefined();
        });
      });

      describe("resolveEdge", () => {
        it("should find an existing edge", () => {
          expect(resolveEdge("eb5f41ff-3e64-417e-ae7e-eecd9c886ecc")).toEqual(
            demoEdges.find(
              (e) => e.id === "eb5f41ff-3e64-417e-ae7e-eecd9c886ecc",
            ),
          );
        });
        it("should return undefined for an unknown edge ID", () => {
          expect(resolveEdge("unknown-edge")).toBeUndefined();
        });
      });

      describe("Entry functions", () => {
        it("should match getNodeEntries output", () => {
          expect(getNodeEntries()).toEqual(
            demoNodes.map((n) => ({ id: n.id })),
          );
        });

        it("should match getAccountEntries output", () => {
          expect(getAccountEntries()).toEqual(
            demoAccounts.map((a) => ({ id: a.id })),
          );
        });

        it("should match getEdgeEntries output", () => {
          expect(getEdgeEntries()).toEqual(
            demoEdges.map((e) => ({ id: e.id })),
          );
        });
      });
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

      describe("resolveNode", () => {
        it("should find an existing node", () => {
          expect(resolveNode("b52be17c-4ab7-4434-98ce-520f86290cf0")).toEqual(
            demoNodes.find(
              (n) => n.id === "b52be17c-4ab7-4434-98ce-520f86290cf0",
            ),
          );
        });
        it("should return undefined for an unknown node ID", () => {
          expect(resolveNode("unknown-node")).toBeUndefined();
        });
      });

      describe("resolveAccount", () => {
        it("should find an existing account", () => {
          expect(
            resolveAccount("7d97a42e-3704-4a33-a61f-0e0a6b4d65d8"),
          ).toEqual(
            demoAccounts.find(
              (a) => a.id === "7d97a42e-3704-4a33-a61f-0e0a6b4d65d8",
            ),
          );
        });
        it("should return undefined for an unknown account ID", () => {
          expect(resolveAccount("unknown-acc")).toBeUndefined();
        });
      });

      describe("resolveEdge", () => {
        it("should find an existing edge", () => {
          expect(resolveEdge("eb5f41ff-3e64-417e-ae7e-eecd9c886ecc")).toEqual(
            demoEdges.find(
              (e) => e.id === "eb5f41ff-3e64-417e-ae7e-eecd9c886ecc",
            ),
          );
        });
        it("should return undefined for an unknown edge ID", () => {
          expect(resolveEdge("unknown-edge")).toBeUndefined();
        });
      });

      describe("Entry functions", () => {
        it("should match getNodeEntries output", () => {
          expect(getNodeEntries()).toEqual(
            demoNodes.map((n) => ({ id: n.id })),
          );
        });

        it("should match getAccountEntries output", () => {
          expect(getAccountEntries()).toEqual(
            demoAccounts.map((a) => ({ id: a.id })),
          );
        });

        it("should match getEdgeEntries output", () => {
          expect(getEdgeEntries()).toEqual(
            demoEdges.map((e) => ({ id: e.id })),
          );
        });
      });
    });

    it("resolveEdgeParticipants returns correct data", () => {
      const edgeId = "eb5f41ff-3e64-417e-ae7e-eecd9c886ecc";
      const details = resolveEdgeParticipants(edgeId);
      expect(details.source_details?.title).toBe("weltgewebeknoten1");
      expect(details.target_details?.title).toBe("fairschenkbox");

      describe("resolveNode", () => {
        it("should find an existing node", () => {
          expect(resolveNode("b52be17c-4ab7-4434-98ce-520f86290cf0")).toEqual(
            demoNodes.find(
              (n) => n.id === "b52be17c-4ab7-4434-98ce-520f86290cf0",
            ),
          );
        });
        it("should return undefined for an unknown node ID", () => {
          expect(resolveNode("unknown-node")).toBeUndefined();
        });
      });

      describe("resolveAccount", () => {
        it("should find an existing account", () => {
          expect(
            resolveAccount("7d97a42e-3704-4a33-a61f-0e0a6b4d65d8"),
          ).toEqual(
            demoAccounts.find(
              (a) => a.id === "7d97a42e-3704-4a33-a61f-0e0a6b4d65d8",
            ),
          );
        });
        it("should return undefined for an unknown account ID", () => {
          expect(resolveAccount("unknown-acc")).toBeUndefined();
        });
      });

      describe("resolveEdge", () => {
        it("should find an existing edge", () => {
          expect(resolveEdge("eb5f41ff-3e64-417e-ae7e-eecd9c886ecc")).toEqual(
            demoEdges.find(
              (e) => e.id === "eb5f41ff-3e64-417e-ae7e-eecd9c886ecc",
            ),
          );
        });
        it("should return undefined for an unknown edge ID", () => {
          expect(resolveEdge("unknown-edge")).toBeUndefined();
        });
      });

      describe("Entry functions", () => {
        it("should match getNodeEntries output", () => {
          expect(getNodeEntries()).toEqual(
            demoNodes.map((n) => ({ id: n.id })),
          );
        });

        it("should match getAccountEntries output", () => {
          expect(getAccountEntries()).toEqual(
            demoAccounts.map((a) => ({ id: a.id })),
          );
        });

        it("should match getEdgeEntries output", () => {
          expect(getEdgeEntries()).toEqual(
            demoEdges.map((e) => ({ id: e.id })),
          );
        });
      });
    });

    describe("resolveNode", () => {
      it("should find an existing node", () => {
        expect(resolveNode("b52be17c-4ab7-4434-98ce-520f86290cf0")).toEqual(
          demoNodes.find(
            (n) => n.id === "b52be17c-4ab7-4434-98ce-520f86290cf0",
          ),
        );
      });
      it("should return undefined for an unknown node ID", () => {
        expect(resolveNode("unknown-node")).toBeUndefined();
      });
    });

    describe("resolveAccount", () => {
      it("should find an existing account", () => {
        expect(resolveAccount("7d97a42e-3704-4a33-a61f-0e0a6b4d65d8")).toEqual(
          demoAccounts.find(
            (a) => a.id === "7d97a42e-3704-4a33-a61f-0e0a6b4d65d8",
          ),
        );
      });
      it("should return undefined for an unknown account ID", () => {
        expect(resolveAccount("unknown-acc")).toBeUndefined();
      });
    });

    describe("resolveEdge", () => {
      it("should find an existing edge", () => {
        expect(resolveEdge("eb5f41ff-3e64-417e-ae7e-eecd9c886ecc")).toEqual(
          demoEdges.find(
            (e) => e.id === "eb5f41ff-3e64-417e-ae7e-eecd9c886ecc",
          ),
        );
      });
      it("should return undefined for an unknown edge ID", () => {
        expect(resolveEdge("unknown-edge")).toBeUndefined();
      });
    });

    describe("Entry functions", () => {
      it("should match getNodeEntries output", () => {
        expect(getNodeEntries()).toEqual(demoNodes.map((n) => ({ id: n.id })));
      });

      it("should match getAccountEntries output", () => {
        expect(getAccountEntries()).toEqual(
          demoAccounts.map((a) => ({ id: a.id })),
        );
      });

      it("should match getEdgeEntries output", () => {
        expect(getEdgeEntries()).toEqual(demoEdges.map((e) => ({ id: e.id })));
      });
    });
  });

  describe("resolveNode", () => {
    it("should find an existing node", () => {
      expect(resolveNode("b52be17c-4ab7-4434-98ce-520f86290cf0")).toEqual(
        demoNodes.find((n) => n.id === "b52be17c-4ab7-4434-98ce-520f86290cf0"),
      );
    });
    it("should return undefined for an unknown node ID", () => {
      expect(resolveNode("unknown-node")).toBeUndefined();
    });
  });

  describe("resolveAccount", () => {
    it("should find an existing account", () => {
      expect(resolveAccount("7d97a42e-3704-4a33-a61f-0e0a6b4d65d8")).toEqual(
        demoAccounts.find(
          (a) => a.id === "7d97a42e-3704-4a33-a61f-0e0a6b4d65d8",
        ),
      );
    });
    it("should return undefined for an unknown account ID", () => {
      expect(resolveAccount("unknown-acc")).toBeUndefined();
    });
  });

  describe("resolveEdge", () => {
    it("should find an existing edge", () => {
      expect(resolveEdge("eb5f41ff-3e64-417e-ae7e-eecd9c886ecc")).toEqual(
        demoEdges.find((e) => e.id === "eb5f41ff-3e64-417e-ae7e-eecd9c886ecc"),
      );
    });
    it("should return undefined for an unknown edge ID", () => {
      expect(resolveEdge("unknown-edge")).toBeUndefined();
    });
  });

  describe("Entry functions", () => {
    it("should match getNodeEntries output", () => {
      expect(getNodeEntries()).toEqual(demoNodes.map((n) => ({ id: n.id })));
    });

    it("should match getAccountEntries output", () => {
      expect(getAccountEntries()).toEqual(
        demoAccounts.map((a) => ({ id: a.id })),
      );
    });

    it("should match getEdgeEntries output", () => {
      expect(getEdgeEntries()).toEqual(demoEdges.map((e) => ({ id: e.id })));
    });
  });
});
