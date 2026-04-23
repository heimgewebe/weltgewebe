import { json, error } from "@sveltejs/kit";
import { demoNodes } from "$lib/demo/demoData";
import { resolveNodeParticipants } from "$lib/demo/resolvers";
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

  if (!id) {
    throw error(400, "ID is required");
  }

  const node = demoNodes.find((n) => n.id === id);

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
