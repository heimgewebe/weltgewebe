import { writable } from "svelte/store";

/**
 * Tiny in-browser invalidation signal for account attention shown in the top bar.
 * Producers bump the revision after a successful local mutation; the top bar
 * then re-reads canonical API state instead of trusting payloads from another
 * component.
 */
const revision = writable(0);

export const topBarAttentionRefresh = {
  subscribe: revision.subscribe,
};

export function requestTopBarAttentionRefresh(): void {
  revision.update((value) => value + 1);
}
