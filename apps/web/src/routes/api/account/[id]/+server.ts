import { json, error } from "@sveltejs/kit";
import {
  resolveAccount,
  resolveAccountActivity,
  resolveAccountNodes,
  getAccountEntries,
} from "$lib/demo/resolvers";
import type { RequestEvent } from "@sveltejs/kit";

export const prerender = true;
export const entries = () => getAccountEntries();

export function GET({ params }: RequestEvent) {
  const { id } = params;

  if (!id || id.trim() === "") {
    throw error(400, "ID is required");
  }

  const account = resolveAccount(id);

  if (!account) {
    throw error(404, "Account not found");
  }

  const nodes = resolveAccountNodes(id);

  return json({
    ...account,
    nodes,
    activity: resolveAccountActivity(id),
  });
}
