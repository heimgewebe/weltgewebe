import { writable, type Readable } from "svelte/store";

export type PanelResource = "node" | "account" | "edge";

export interface SelectionLike {
  id: string;
}

export interface PanelDetailsLoaderOptions {
  buildEndpoint: (id: string) => string;
  /** Called when the watched selection id changes, before any reset/fetch. */
  onSelectionChange?: (id: string | undefined) => void;
  /** Used inside the error message thrown for non-2xx responses. */
  resourceLabel?: string;
  /** Overridable fetcher; defaults to the global `fetch`. */
  fetcher?: typeof fetch;
  /** Sink for non-abort errors; defaults to `console.error`. */
  onError?: (error: unknown) => void;
}

export interface PanelDetailsLoader<T> {
  details: Readable<T | null>;
  isLoading: Readable<boolean>;
  destroy: () => void;
}

export function createPanelDetailsLoader<T>(
  selectionStore: Readable<SelectionLike | null | undefined>,
  options: PanelDetailsLoaderOptions,
): PanelDetailsLoader<T> {
  const details = writable<T | null>(null);
  const isLoading = writable<boolean>(false);
  const fetcher = options.fetcher ?? globalThis.fetch.bind(globalThis);
  const onError = options.onError ?? ((error: unknown) => console.error(error));
  const label = options.resourceLabel ?? "details";

  let abortController: AbortController | null = null;
  let lastSelectionId: string | undefined;
  let activeRequestId: string | undefined;

  const unsubscribe = selectionStore.subscribe((current) => {
    const currentId = current?.id;

    if (currentId === lastSelectionId) {
      return;
    }
    lastSelectionId = currentId;

    options.onSelectionChange?.(currentId);

    details.set(null);
    isLoading.set(false);

    if (abortController) {
      abortController.abort();
      abortController = null;
    }

    if (!currentId) {
      activeRequestId = undefined;
      return;
    }

    const requestId = currentId;
    activeRequestId = requestId;
    const controller = new AbortController();
    abortController = controller;
    isLoading.set(true);

    const endpoint = options.buildEndpoint(requestId);

    fetcher(endpoint, { signal: controller.signal })
      .then((res) => {
        if (!res.ok) {
          throw new Error(`Failed to load ${label}`);
        }
        return res.json() as Promise<T>;
      })
      .then((data) => {
        if (activeRequestId === requestId) {
          details.set(data);
        }
      })
      .catch((error: unknown) => {
        if ((error as { name?: string } | null)?.name === "AbortError") {
          return;
        }
        onError(error);
      })
      .finally(() => {
        if (activeRequestId === requestId) {
          isLoading.set(false);
          if (abortController === controller) {
            abortController = null;
          }
        }
      });
  });

  function destroy() {
    if (abortController) {
      abortController.abort();
      abortController = null;
    }
    activeRequestId = undefined;
    unsubscribe();
  }

  return { details, isLoading, destroy };
}

export function buildPanelEndpoint(
  resource: PanelResource,
  id: string,
  apiBase?: string,
): string {
  const base = apiBase ?? import.meta.env.PUBLIC_GEWEBE_API_BASE ?? "";
  if (base) {
    return `${base}/api/${resource}s/${id}`;
  }
  return `/api/${resource}/${id}`;
}
