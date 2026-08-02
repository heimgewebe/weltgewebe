import { json } from "@sveltejs/kit";
import { demoWebgemeindezentren } from "$lib/demo/demoData";

export const prerender = true;

export function GET() {
  return json(demoWebgemeindezentren);
}
