import { demoAccounts, demoEdges, demoNodes } from "./demoData";

type DemoNode = (typeof demoNodes)[number];
type DemoAccount = (typeof demoAccounts)[number];
type DemoEdge = (typeof demoEdges)[number];
type DemoEntity = DemoNode | DemoAccount;

// Module-level caches for static demo data lookups
const nodeMap = new Map<string, DemoNode>(demoNodes.map((n) => [n.id, n]));
const accountMap = new Map<string, DemoAccount>(
  demoAccounts.map((a) => [a.id, a]),
);
const edgeMap = new Map<string, DemoEdge>(demoEdges.map((e) => [e.id, e]));

const edgesBySource = new Map<string, DemoEdge[]>();
const edgesByTarget = new Map<string, DemoEdge[]>();

for (const edge of demoEdges) {
  // Index by source_id
  const sourceList = edgesBySource.get(edge.source_id) || [];
  sourceList.push(edge);
  edgesBySource.set(edge.source_id, sourceList);

  // Index by target_id
  const targetList = edgesByTarget.get(edge.target_id) || [];
  targetList.push(edge);
  edgesByTarget.set(edge.target_id, targetList);
}

/**
 * Returns entries for prerendering nodes.
 */
export function getNodeEntries() {
  return demoNodes.map((n) => ({ id: n.id }));
}

/**
 * Returns entries for prerendering accounts.
 */
export function getAccountEntries() {
  return demoAccounts.map((a) => ({ id: a.id }));
}

/**
 * Returns entries for prerendering edges.
 */
export function getEdgeEntries() {
  return demoEdges.map((e) => ({ id: e.id }));
}

/**
 * Resolves a single node by ID.
 */
export function resolveNode(id: string) {
  return nodeMap.get(id);
}

/**
 * Resolves a single account by ID.
 */
export function resolveAccount(id: string) {
  return accountMap.get(id);
}

/**
 * Resolves a single edge by ID.
 */
export function resolveEdge(id: string) {
  return edgeMap.get(id);
}

/**
 * Public edge shape used by prerendered preview endpoints.
 *
 * The static demo cannot truthfully claim that its relation was created within
 * the last seven days: a build-time timestamp would eventually expire while a
 * refreshed timestamp would fabricate activity. Project it explicitly as an
 * undated, non-authoritative preview relation instead.
 */
export function toPublicEdge(edge: DemoEdge) {
  return {
    id: edge.id,
    source_id: edge.source_id,
    source_type: edge.source_type,
    target_id: edge.target_id,
    target_type: edge.target_type,
    edge_kind: edge.edge_kind,
    created_at: null,
    expires_at: null,
  };
}

/** Returns all demo edges without persisted authoring notes. */
export function listPublicEdges() {
  return demoEdges.map(toPublicEdge);
}

/** Resolves one public demo edge without persisted authoring notes. */
export function resolvePublicEdge(id: string) {
  const edge = edgeMap.get(id);
  return edge ? toPublicEdge(edge) : undefined;
}

/**
 * Resolves nodes associated with an account.
 * Replaces N+1 query pattern with a Map-based lookup.
 */
export function resolveAccountNodes(accountId: string) {
  const relatedEdges = (edgesBySource.get(accountId) || []).filter(
    (e) => e.source_type === "account" && e.target_type === "node",
  );

  return relatedEdges
    .map((edge) => {
      const node = nodeMap.get(edge.target_id);
      return {
        edge_id: edge.id,
        edge_kind: edge.edge_kind,
        node_id: node?.id,
        node_title: node?.title,
        node_kind: node?.kind,
      };
    })
    .filter((n) => n.node_id);
}

/**
 * Returns only activity backed by the static account fixture itself.
 *
 * Demo edges intentionally carry no authoritative lifecycle timestamp, so
 * neither their presence nor an account timestamp can prove when a Knoten was
 * created. Keep the relation visible in the Knoten projection without turning
 * it into invented Garnrolle activity.
 */
export function resolveAccountActivity(accountId: string) {
  const account = accountMap.get(accountId);
  return account
    ? [{ date: account.created_at, event: "Account erstellt." }]
    : [];
}

/**
 * Resolves accounts associated with a node.
 */
export function resolveNodeParticipants(nodeId: string) {
  const relatedEdges = (edgesByTarget.get(nodeId) || []).filter(
    (e) => e.target_type === "node",
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
  const edge = edgeMap.get(edgeId);
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
