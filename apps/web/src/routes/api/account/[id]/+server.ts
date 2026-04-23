import { json, error } from "@sveltejs/kit";
import { demoAccounts, demoEdges, demoNodes } from "$lib/demo/demoData";
import type { RequestEvent } from "@sveltejs/kit";

export const prerender = true;
export const entries = () => demoAccounts.map((a) => ({ id: a.id }));

export function GET({ params }: RequestEvent) {
  const { id } = params;

  const account = demoAccounts.find((a) => a.id === id);

  if (!account) {
    throw error(404, "Account not found");
  }

  // Find associated nodes (where account is source)
  const relatedEdges = demoEdges.filter(
    (e) =>
      e.source_id === id &&
      e.source_type === "account" &&
      e.target_type === "node",
  );

  const nodeMap = new Map(demoNodes.map((n) => [n.id, n]));
  const nodes = relatedEdges
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

  return json({
    ...account,
    nodes,
    activity: [
      {
        date: account.created_at,
        event: "Account erstellt.",
      },
      ...nodes.map((n) => ({
        date: account.created_at, // Mocking date
        event: `Hat Knoten "${n.node_title}" verknüpft (${n.edge_kind}).`,
      })),
    ].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()),
  });
}
