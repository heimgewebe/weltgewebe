import { writable } from "svelte/store";

export const isSearchOpen = writable<boolean>(false);
export const searchQuery = writable<string>("");

export function toggleSearch() {
  isSearchOpen.update((v) => {
    if (v) {
      searchQuery.set("");
      return false;
    }
    return true;
  });
}

/**
 * Opens the search overlay unconditionally. Used by URL deep-link addressing,
 * which must never toggle (a toggle could close an already-open overlay).
 */
export function openSearch() {
  isSearchOpen.set(true);
}

export function closeSearch() {
  isSearchOpen.set(false);
  searchQuery.set("");
}
