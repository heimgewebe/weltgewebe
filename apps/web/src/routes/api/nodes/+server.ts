import { json } from "@sveltejs/kit";
import { demoNodes } from "$lib/demo/demoData";

// Prerender this endpoint to a static file.
// We explicitly use `trailingSlash = "always"` on both the list and detail endpoints
// so that SvelteKit generates `api/nodes/index.html` and `api/nodes/[id]/index.html`.
// This perfectly sidesteps the `api/nodes` (file) vs `api/nodes/` (directory) conflict
// on static file systems without disabling prerendering.
// Turn off prerender to avoid static adapter directory collisions.
// SvelteKit's static adapter inherently struggles when a route `/api/nodes`
// generates a file, while another route `/api/nodes/[id]` requires an `api/nodes` directory.
// We explicitly disable prerendering for the demo endpoints to prevent `EISDIR` errors
// without resorting to `adapter-static({ strict: false })`.
export const prerender = false;

export function GET() {
  return json(demoNodes);
}
