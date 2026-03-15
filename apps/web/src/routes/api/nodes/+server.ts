import { json } from "@sveltejs/kit";
import { demoNodes } from "$lib/demo/demoData";

// Prerender this endpoint to a static file.
// Using trailingSlash="always" doesn't cleanly resolve the collision in SvelteKit's static adapter.
// We will instead return to `prerender = false` to avoid this purely build-time directory conflict.
// The list data is already fetched dynamically or passed differently in real scenarios anyway.
export const prerender = false;

export function GET() {
  return json(demoNodes);
}
