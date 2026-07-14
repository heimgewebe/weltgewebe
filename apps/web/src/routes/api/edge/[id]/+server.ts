import { json, error } from "@sveltejs/kit";
import {
  resolvePublicEdge,
  resolveEdgeParticipants,
  getEdgeEntries,
} from "$lib/demo/resolvers";
import type { RequestEvent } from "@sveltejs/kit";

export const prerender = true;
export const entries = () => getEdgeEntries();

export function GET({ params }: RequestEvent) {
  const { id } = params;

  if (!id || id.trim() === "") {
    throw error(400, "ID is required");
  }

  const edge = resolvePublicEdge(id);

  if (!edge) {
    throw error(404, "Edge not found");
  }

  const participants = resolveEdgeParticipants(id);

  // Return the public edge projection with enriched participant data
  return json({
    ...edge,
    ...participants,
  });
}
