import { json } from "@sveltejs/kit";
import { demoNodes } from "$lib/demo/demoData";

// Disable prerender for this list endpoint to prevent conflict with /api/nodes/[id].
// In a real static build, these API routes would either hit a real backend
// or be explicitly baked into `.json` files via an external script or `entries`.
// For the scope of this PR, avoiding the build failure is sufficient.
export const prerender = false;

export function GET() {
  return json(demoNodes);
}
