import { demoAccounts, demoEdges, demoNodes } from "./demoData";

type DemoNode = (typeof demoNodes)[number];
type DemoAccount = (typeof demoAccounts)[number];
type DemoEntity = DemoNode | DemoAccount;

// Module-level caches for static demo data lookups
const nodeMap = new Map<string, DemoNode>(demoNodes.map((n) => [n.id, n]));
const accountMap = new Map<string, DemoAccount>(
  demoAccounts.map((a) => [a.id, a]),
);

/**
 * Resolves nodes associated with an account.
 * Replaces N+1 query pattern with a Map-based lookup.
 */
export function resolveAccountNodes(accountId: string) {
  const relatedEdges = demoEdges.filter(
    (e) =>
      e.source_id === accountId &&
      e.source_type === "account" &&
      e.target_type === "node",
  );

  return relatedEdges
    .map((edge) => {
      const node = nodeMap.get(edge.target_id);
      return {
        edge_id: edge.id,
        edge_kind: edge.edge_kind,
        note: edge.note,
        node_id: node?.id,
        node_title: node?.title,
        node_kind: node?.kind,
      };
    })
    .filter((n) => n.node_id);
}

/**
 * Resolves accounts associated with a node.
 */
export function resolveNodeParticipants(nodeId: string) {
  const relatedEdges = demoEdges.filter(
    (e) => e.target_id === nodeId && e.target_type === "node",
  );

  return relatedEdges
    .map((edge) => {
      // Optimization: Only lookup account if source_type is account
      const account =
        edge.source_type === "account"
          ? accountMap.get(edge.source_id)
          : undefined;
      return {
        edge_id: edge.id,
        edge_kind: edge.edge_kind,
        note: edge.note,
        account_id: account?.id,
        account_title: account?.title,
        account_type: account?.type,
      };
    })
    .filter((p) => p.account_id);
}

/**
 * Resolves source and target details for an edge.
 */
export function resolveEdgeParticipants(edgeId: string) {
  const edge = demoEdges.find((e) => e.id === edgeId);
  if (!edge) {
    return {
      source_details: null,
      target_details: null,
    };
  }

  function getEntity(id: string, type: string): DemoEntity | undefined {
    if (type === "account") return accountMap.get(id);
    if (type === "node") return nodeMap.get(id);
    return undefined;
  }

  const source = getEntity(edge.source_id, edge.source_type);
  const target = getEntity(edge.target_id, edge.target_type);

  function toDetails(entity: DemoEntity | undefined) {
    if (!entity) return null;
    return {
      id: entity.id,
      title: entity.title,
      type: "type" in entity ? entity.type : entity.kind,
    };
  }

  return {
    source_details: toDetails(source),
    target_details: toDetails(target),
  };
}
