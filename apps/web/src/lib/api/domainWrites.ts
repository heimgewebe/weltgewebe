import type { Edge, Location, Node } from "$lib/map/types";

/**
 * Thrown when a domain write (`POST /nodes`, `POST /edges`) is rejected by the
 * API. Carries the HTTP status so callers can map it to an understandable,
 * German, user-facing message without leaking backend/internal detail.
 */
export class ApiRequestError extends Error {
  status: number;
  constructor(status: number) {
    super(`API request failed with status ${status}`);
    this.name = "ApiRequestError";
    this.status = status;
  }
}

async function postJson<T>(path: string, payload: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    credentials: "include",
  });
  if (!res.ok) {
    throw new ApiRequestError(res.status);
  }
  return res.json();
}

export interface CreateNodePayload {
  title: string;
  kind: string;
  address: string;
  location: Location;
  summary?: string;
}

/** POST /api/nodes — create a node. Server owns `id`/`created_at`/`updated_at`. */
export function createNode(payload: CreateNodePayload): Promise<Node> {
  return postJson<Node>("/api/nodes", payload);
}

export interface CreateEdgePayload {
  source_id: string;
  source_type: string;
  target_id: string;
  target_type: string;
  edge_kind: string;
}

/** POST /api/edges — create an edge. Server owns `id`/`created_at`. */
export function createEdge(payload: CreateEdgePayload): Promise<Edge> {
  return postJson<Edge>("/api/edges", payload);
}
