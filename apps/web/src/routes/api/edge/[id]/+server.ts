import { json, error } from "@sveltejs/kit";
import { demoEdges, demoAccounts, demoNodes } from "$lib/demo/demoData";
import type { RequestEvent } from "@sveltejs/kit";

export const prerender = true;
export const entries = () => demoEdges.map((e) => ({ id: e.id }));

export function GET({ params }: RequestEvent) {
  const { id } = params;

  const edge = demoEdges.find((e) => e.id === id);

  if (!edge) {
    throw error(404, "Edge not found");
  }

  type EdgeEntity = (typeof demoAccounts)[number] | (typeof demoNodes)[number];

  // Find associated source and target
  let source: EdgeEntity | undefined;
  if (edge.source_type === "account") {
    source = demoAccounts.find((a) => a.id === edge.source_id);
  } else if (edge.source_type === "node") {
    source = demoNodes.find((n) => n.id === edge.source_id);
  }

  let target: EdgeEntity | undefined;
  if (edge.target_type === "account") {
    target = demoAccounts.find((a) => a.id === edge.target_id);
  } else if (edge.target_type === "node") {
    target = demoNodes.find((n) => n.id === edge.target_id);
  }

  function toParticipantDetails(entity: EdgeEntity | undefined) {
    if (!entity) return null;
    return {
      id: entity.id,
      title: entity.title,
      type:
        "type" in entity
          ? entity.type
          : "kind" in entity
            ? entity.kind
            : undefined,
    };
  }

  // Return the complete domain object with enriched data
  return json({
    ...edge,
    source_details: toParticipantDetails(source),
    target_details: toParticipantDetails(target),
  });
}
