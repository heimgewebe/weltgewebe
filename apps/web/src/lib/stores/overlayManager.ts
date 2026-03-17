import { toggleSearch, closeSearch, isSearchOpen } from "./searchStore";
import { toggleFilter, closeFilter, isFilterOpen } from "./filterStore";
import { get } from "svelte/store";
import { suppressNextRestore } from "$lib/utils/focusManager";

export function openSearchExclusive() {
  if (get(isFilterOpen)) {
    suppressNextRestore("filter");
    closeFilter();
  }
  toggleSearch();
}

export function openFilterExclusive() {
  if (get(isSearchOpen)) {
    suppressNextRestore("search");
    closeSearch();
  }
  toggleFilter();
}
