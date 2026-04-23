import { json, error } from "@sveltejs/kit";
import { demoNodes, demoEdges, demoAccounts } from "$lib/demo/demoData";
import type { RequestEvent } from "@sveltejs/kit";

// For static export (Path A), but with dynamic routes we typically prerender
// by providing a list of entries, but for demo we can just let it fall back or prerender known IDs.
// Using 'auto' or 'true' here with a dynamic route without explicitly defining entries
// breaks the static adapter.
// Prerender explicit entries for the static adapter to crawl.
export const prerender = true;
export const entries = () => demoNodes.map((n) => ({ id: n.id }));

export function GET({ params }: RequestEvent) {
  const { id } = params;

  const node = demoNodes.find((n) => n.id === id);

  if (!node) {
    throw error(404, "Node not found");
  }

  // Find associated edges and participants
  const relatedEdges = demoEdges.filter(
    (e) => e.target_id === id && e.target_type === "node",
  );

  // Optimization: Pre-compute a map of accounts for O(1) lookup
  const accountMap = new Map(demoAccounts.map((a) => [a.id, a]));

  const participants = relatedEdges
    .map((edge) => {
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

  // Return the complete domain object with enriched participant data
  return json({
    ...node,
    participants,
    history: [
      {
        date: node.created_at,
        event: "Knoten wurde im Gewebe verankert.",
      },
      // If updated_at exists and is different, add it
      ...(node.updated_at && node.updated_at !== node.created_at
        ? [
            {
              date: node.updated_at,
              event: "Knoten aktualisiert.",
            },
          ]
        : []),
    ].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()),
  });
}
