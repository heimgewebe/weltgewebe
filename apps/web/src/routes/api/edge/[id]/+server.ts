import { json, error } from "@sveltejs/kit";
import { demoEdges } from "$lib/demo/demoData";
import { resolveEdgeParticipants } from "$lib/demo/resolvers";
import type { RequestEvent } from "@sveltejs/kit";

export const prerender = true;
export const entries = () => demoEdges.map((e) => ({ id: e.id }));

export function GET({ params }: RequestEvent) {
  const { id } = params;

  if (!id || id.trim() === "") {
    throw error(400, "ID is required");
  }

  const edge = demoEdges.find((e) => e.id === id);

  if (!edge) {
    throw error(404, "Edge not found");
  }

  const participants = resolveEdgeParticipants(id);

  // Return the complete domain object with enriched data
  return json({
    ...edge,
    ...participants,
  });
}
