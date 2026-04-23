import { json, error } from "@sveltejs/kit";
import { demoAccounts } from "$lib/demo/demoData";
import { resolveAccountNodes } from "$lib/demo/resolvers";
import type { RequestEvent } from "@sveltejs/kit";

export const prerender = true;
export const entries = () => demoAccounts.map((a) => ({ id: a.id }));

export function GET({ params }: RequestEvent) {
  const { id } = params;

  if (!id) {
    throw error(400, "ID is required");
  }

  const account = demoAccounts.find((a) => a.id === id);

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
        event: `Hat Knoten "${n.node_title}" verknüpft (${n.edge_kind}).`,
      })),
    ].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()),
  });
}
