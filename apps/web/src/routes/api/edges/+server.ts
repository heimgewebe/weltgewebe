import { json } from "@sveltejs/kit";
import { listPublicEdges } from "$lib/demo/resolvers";

export const prerender = true;

export function GET() {
  return json(listPublicEdges());
}
