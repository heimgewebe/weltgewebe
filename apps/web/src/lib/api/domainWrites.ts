import type { GarnrolleMapState, Location, Node } from "$lib/map/types";

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

async function requestJson<T>(
  path: string,
  method: "POST" | "PATCH" | "PUT",
  payload: unknown,
): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    credentials: "include",
  });
  if (!res.ok) {
    throw new ApiRequestError(res.status);
  }
  return res.json();
}

async function postJson<T>(path: string, payload: unknown): Promise<T> {
  return requestJson<T>(path, "POST", payload);
}

async function patchJson<T>(path: string, payload: unknown): Promise<T> {
  return requestJson<T>(path, "PATCH", payload);
}

async function putJson<T>(path: string, payload: unknown): Promise<T> {
  return requestJson<T>(path, "PUT", payload);
}

async function deleteResource(path: string): Promise<void> {
  const res = await fetch(path, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok) {
    throw new ApiRequestError(res.status);
  }
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
  /** Stable UUID for retrying one user action after an uncertain response. */
  operation_id?: string;
}

/** POST /api/nodes — create a node. Server owns `id`/`created_at`/`updated_at`. */
export function createNode(payload: CreateNodePayload): Promise<Node> {
  return postJson<Node>("/api/nodes", payload);
}

export interface ReplaceNodePayload {
  title: string;
  kind: string;
  address: string;
  location: Location;
  summary?: string;
  info?: string;
  tags: string[];
}

/** PUT /api/nodes/:id — replace the editable fields of a shared node. */
export function replaceNode(
  id: string,
  payload: ReplaceNodePayload,
): Promise<Node> {
  return putJson<Node>(`/api/nodes/${encodeURIComponent(id)}`, payload);
}

/** DELETE /api/nodes/:id — delete a node and its derived connected edges. */
export function deleteNode(id: string): Promise<void> {
  return deleteResource(`/api/nodes/${encodeURIComponent(id)}`);
}
