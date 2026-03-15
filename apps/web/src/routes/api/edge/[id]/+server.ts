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

  // Find associated source and target
  let source;
  if (edge.source_type === "account") {
    source = demoAccounts.find((a) => a.id === edge.source_id);
  } else if (edge.source_type === "node") {
    source = demoNodes.find((n) => n.id === edge.source_id);
  }

  let target;
  if (edge.target_type === "account") {
    target = demoAccounts.find((a) => a.id === edge.target_id);
  } else if (edge.target_type === "node") {
    target = demoNodes.find((n) => n.id === edge.target_id);
  }

  // Return the complete domain object with enriched data
  return json({
    ...edge,
    source_details: source
      ? {
          id: source.id,
          title: source.title,
          type:
            "type" in source
              ? source.type
              : "kind" in source
                ? source.kind
                : undefined,
        }
      : null,
    target_details: target
      ? {
          id: target.id,
          title: target.title,
          type:
            "type" in target
              ? target.type
              : "kind" in target
                ? target.kind
                : undefined,
        }
      : null,
  });
}
