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

/** DELETE /api/nodes/:id — remove a node and report its lifecycle effects. */
export async function deleteNode(
  id: string,
  etag?: string,
): Promise<NodeDeleteReceipt> {
  try {
    const response = await fetch(`/api/nodes/${encodeURIComponent(id)}`, {
      method: "DELETE",
      headers: etag ? { "If-Match": `"${etag}"` } : {},
      credentials: "include",
    });
    if (!response.ok) {
      throw new ApiRequestError(response.status, await readErrorBody(response));
    }

    const receipt = (await response.json().catch(() => null)) as
      | NodeDeleteReceipt
      | null;
    const conversation = receipt?.conversation;
    const effect = conversation?.effect;
    if (
      receipt?.node_id !== id ||
      receipt.node_state !== "removed" ||
      !Array.isArray(receipt.removed_edge_ids) ||
      receipt.removed_edge_ids.some((edgeId) => typeof edgeId !== "string") ||
      !(
        effect === "not_applicable" ||
        effect === "deleted_empty" ||
        (effect === "archived" &&
          typeof conversation?.archive_id === "string" &&
          conversation?.archive_url ===
            `/api/conversations/${conversation?.archive_id}`)
      )
    ) {
      throw new ApiRequestError(502, receipt ?? undefined);
    }
    return receipt;
  } catch (error) {
    return preserveOnlyMatchingNodeConflict(error, id);
  }
}
