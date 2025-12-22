import { json } from "@sveltejs/kit";
import { demoEdges } from "$lib/demo/demoData";

export const prerender = true;

export function GET() {
  return json(demoEdges);
}
