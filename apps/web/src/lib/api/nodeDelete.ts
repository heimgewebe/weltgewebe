import {
  ApiRequestError,
  preserveOnlyMatchingNodeConflict,
  readErrorBody,
} from "./domainWrites";

export type NodeDeleteConversationEffect =
  | { effect: "not_applicable" }
  | { effect: "deleted_empty" }
  | { effect: "archived"; archive_id: string; archive_url: string };

export interface NodeDeleteReceipt {
  node_id: string;
  node_state: "removed";
  removed_edge_ids: string[];
  conversation: NodeDeleteConversationEffect;
}

async function deleteJson(path: string, etag?: string): Promise<unknown> {
  const headers: HeadersInit = {};
  if (etag) headers["If-Match"] = `"${etag}"`;
  const response = await fetch(path, {
    method: "DELETE",
    headers,
    credentials: "include",
  });
  if (!response.ok) {
    throw new ApiRequestError(response.status, await readErrorBody(response));
  }
  return response.json().catch(() => undefined);
}

function parseNodeDeleteReceipt(
  value: unknown,
  expectedNodeId: string,
): NodeDeleteReceipt {
  const receipt = value as NodeDeleteReceipt;
  const conversation = receipt?.conversation;
  const effect = conversation?.effect;
  if (
    receipt?.node_id !== expectedNodeId ||
    receipt.node_state !== "removed" ||
    !Array.isArray(receipt.removed_edge_ids) ||
    receipt.removed_edge_ids.some((id) => typeof id !== "string") ||
    !(
      effect === "not_applicable" ||
      effect === "deleted_empty" ||
      (effect === "archived" &&
        typeof conversation.archive_id === "string" &&
        conversation.archive_url ===
          `/api/conversations/${conversation.archive_id}`)
    )
  ) {
    throw new ApiRequestError(502, value);
  }
  return receipt;
}

/** DELETE /api/nodes/:id — remove a node and report its lifecycle effects. */
export function deleteNode(
  id: string,
  etag?: string,
): Promise<NodeDeleteReceipt> {
  return deleteJson(`/api/nodes/${encodeURIComponent(id)}`, etag)
    .then((value) => parseNodeDeleteReceipt(value, id))
    .catch((error) => preserveOnlyMatchingNodeConflict(error, id));
}
