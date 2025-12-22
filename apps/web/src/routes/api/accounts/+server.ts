import { json } from "@sveltejs/kit";
import { demoAccounts } from "$lib/demo/demoData";

export const prerender = true;

export function GET() {
  return json(demoAccounts);
}
