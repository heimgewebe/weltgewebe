import { json } from "@sveltejs/kit";
import { demoOrtswebereien } from "$lib/demo/demoData";

export const prerender = true;

export function GET() {
  return json(demoOrtswebereien);
}
