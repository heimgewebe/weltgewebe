import {
  toggleSearch,
  openSearch,
  closeSearch,
  isSearchOpen,
} from "./searchStore";
import {
  toggleFilter,
  openFilter,
  closeFilter,
  isFilterOpen,
} from "./filterStore";
import { get } from "svelte/store";
import { suppressNextRestore } from "$lib/utils/focusManager";

export function toggleSearchExclusive() {
  if (get(isFilterOpen)) {
    suppressNextRestore("filter");
    closeFilter();
  }
  toggleSearch();
}

export function toggleFilterExclusive() {
  if (get(isSearchOpen)) {
    suppressNextRestore("search");
    closeSearch();
  }
  toggleFilter();
}

/**
 * Opens the search lens, closing the filter lens first if it is open.
 * Unlike {@link toggleSearchExclusive}, this never toggles — a deep link
 * to `lens=search` must always *open* search, never close an open one.
 */
export function openSearchExclusive() {
  if (get(isFilterOpen)) {
    suppressNextRestore("filter");
    closeFilter();
  }
  openSearch();
}

/**
 * Opens the filter lens, closing the search lens first if it is open.
 * Unlike {@link toggleFilterExclusive}, this never toggles — a deep link
 * to `lens=filter` must always *open* filter, never close an open one.
 */
export function openFilterExclusive() {
  if (get(isSearchOpen)) {
    suppressNextRestore("search");
    closeSearch();
  }
  openFilter();
}
