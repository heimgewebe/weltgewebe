import type { MapEntityNode, Node } from "$lib/map/types";

export type NodeSearchStatus = "idle" | "loading" | "ready" | "error";

export interface NodeSearchResponse {
  items: Node[];
  mode: string;
  fallback_reason?: string;
  generation_id: string;
  offset: number;
}

export interface SearchNodesOptions {
  kinds?: string[];
  limit?: number;
  signal?: AbortSignal;
  fetcher?: typeof fetch;
  apiBase?: string;
}

export class SearchApiError extends Error {
  constructor(public readonly status: number) {
    super(`Search request failed with HTTP ${status}`);
    this.name = "SearchApiError";
  }
}

export function nodeToMapEntity(node: Node): MapEntityNode {
  return {
    type: "node",
    id: node.id,
    title: node.title,
    lat: node.location.lat,
    lon: node.location.lon,
    summary: node.summary,
    info: node.info,
    kind: node.kind,
    tags: node.tags,
    modules: node.modules,
    created_at: node.created_at,
    updated_at: node.updated_at,
  };
}

export async function searchNodes(
  query: string,
  options: SearchNodesOptions = {},
): Promise<NodeSearchResponse> {
  const normalizedQuery = query.trim();
  if (!normalizedQuery) {
    throw new Error("Search query must not be empty");
  }

  const params = new URLSearchParams({
    q: normalizedQuery,
    limit: String(options.limit ?? 10),
  });
  const kinds = Array.from(
    new Set((options.kinds ?? []).map((kind) => kind.trim()).filter(Boolean)),
  ).sort();
  if (kinds.length > 0) params.set("kinds", kinds.join(","));

  const apiBase =
    options.apiBase ?? import.meta.env.PUBLIC_GEWEBE_API_BASE ?? "";
  const fetcher = options.fetcher ?? fetch;
  const response = await fetcher(`${apiBase}/api/search?${params.toString()}`, {
    credentials: "include",
    headers: { Accept: "application/json" },
    signal: options.signal,
  });
  if (!response.ok) throw new SearchApiError(response.status);
  return (await response.json()) as NodeSearchResponse;
}

export interface SimilarNodeSource {
  title?: string | null;
  kind?: string | null;
  summary?: string | null;
  info?: string | null;
  tags?: string[] | null;
}

export function buildSimilarNodeQuery(source: SimilarNodeSource): string {
  const parts = [
    source.title,
    source.kind,
    source.summary,
    source.info,
    ...(source.tags ?? []),
  ]
    .map((part) => part?.trim())
    .filter((part): part is string => Boolean(part));
  return Array.from(parts.join(" · ")).slice(0, 512).join("");
}
