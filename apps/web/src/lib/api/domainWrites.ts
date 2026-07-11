import type { Edge, GarnrolleMapState, Location, Node } from "$lib/map/types";

/**
 * Thrown when a domain write is rejected by the API. Carries the HTTP status so callers can map it to an understandable,
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

async function patchJson<T>(path: string, payload: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    credentials: "include",
  });
  if (!res.ok) {
    throw new ApiRequestError(res.status);
  }
  return res.json();
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path, { credentials: "include" });
  if (!res.ok) {
    throw new ApiRequestError(res.status);
  }
  return res.json();
}

export interface OwnGarnrolleProfile {
  id: string;
  title: string;
  summary?: string | null;
  tags: string[];
  address?: string | null;
  location?: Location | null;
  map_state: GarnrolleMapState;
  radius_m: number;
}

export interface UpdateOwnGarnrollePayload {
  title: string;
  summary?: string;
  tags: string[];
  address?: string;
  location?: Location;
  map_state: GarnrolleMapState;
  radius_m?: number;
}

/** GET /api/accounts/me/profile — private profile of the active account only. */
export function getOwnGarnrolleProfile(): Promise<OwnGarnrolleProfile> {
  return getJson<OwnGarnrolleProfile>("/api/accounts/me/profile");
}

/** PATCH /api/accounts/me/profile — update only the active account's Garnrolle. */
export function updateOwnGarnrolle(
  payload: UpdateOwnGarnrollePayload,
): Promise<OwnGarnrolleProfile> {
  return patchJson<OwnGarnrolleProfile>("/api/accounts/me/profile", payload);
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
