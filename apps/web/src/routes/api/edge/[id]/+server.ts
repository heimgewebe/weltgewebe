import { json, error } from "@sveltejs/kit";
import { demoEdges } from "$lib/demo/demoData";
import { resolveEdgeParticipants } from "$lib/demo/resolvers";
import type { RequestHandler } from "./$types";

export const prerender = true;
// For static adapter + dynamic segment routes, entries must enumerate concrete ids.
export const entries = () => demoEdges.map((e) => ({ id: e.id }));

export const GET: RequestHandler = ({ params }) => {
  const { id } = params;

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
};
