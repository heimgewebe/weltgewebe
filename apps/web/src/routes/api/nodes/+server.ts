import { json } from "@sveltejs/kit";
import { demoNodes } from "$lib/demo/demoData";

// Prerender this endpoint to a static file (e.g. api/nodes.json or api/nodes/index.html containing JSON)
// to support static hosting (Path A).
export const prerender = true;

export function GET() {
  return json(demoNodes);
}
