import { json, error } from "@sveltejs/kit";
import { demoNodes } from "$lib/demo/demoData";
import { resolveNodeParticipants } from "$lib/demo/resolvers";
import type { RequestHandler } from "./$types";

export const prerender = true;
export const entries = () => demoNodes.map((n) => ({ id: n.id }));

export const GET: RequestHandler = ({ params }) => {
  const { id } = params;

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
};
