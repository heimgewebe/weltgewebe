import { json, error } from "@sveltejs/kit";
import { resolveNode, resolveNodeParticipants, getNodeEntries } from "$lib/demo/resolvers";
import type { RequestEvent } from "@sveltejs/kit";

export const prerender = true;
export const entries = () => getNodeEntries();

export function GET({ params }: RequestEvent) {
  const { id } = params;

  if (!id || id.trim() === "") {
    throw error(400, "ID is required");
  }

  const node = resolveNode(id);

  if (!node) {
    throw error(404, "Node not found");
  }

  const participants = resolveNodeParticipants(id);

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
