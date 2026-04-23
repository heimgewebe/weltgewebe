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

export function closeSearch() {
  isSearchOpen.set(false);
  searchQuery.set("");
}
