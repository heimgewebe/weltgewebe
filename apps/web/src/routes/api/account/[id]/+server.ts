import { json, error } from "@sveltejs/kit";
import {
  resolveAccount,
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
    activity: [
      {
        date: account.created_at,
        event: "Account erstellt.",
      },
      ...nodes.map((n) => ({
        date: account.created_at, // Mocking date
        event: `Hat den Knoten "${n.node_title}" geknüpft.`,
      })),
    ].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()),
  });
}
