import { writable } from "svelte/store";

/**
 * Cross-view invalidation signal for account-specific attention indicators.
 * Writers only announce that canonical state may have changed; consumers must
 * re-read the API instead of trusting state owned by another component.
 */
const revision = writable(0);

export const accountAttentionInvalidation = {
  subscribe: revision.subscribe,
};

export function invalidateAccountAttention(): void {
  revision.update((value) => value + 1);
}
