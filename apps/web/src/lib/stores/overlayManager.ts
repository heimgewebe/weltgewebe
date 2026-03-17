import { toggleSearch, closeSearch, isSearchOpen } from './searchStore';
import { toggleFilter, closeFilter, isFilterOpen } from './filterStore';
import { get } from 'svelte/store';

export function openSearchExclusive() {
  if (get(isFilterOpen)) {
    closeFilter();
  }
  toggleSearch();
}

export function openFilterExclusive() {
  if (get(isSearchOpen)) {
    closeSearch();
  }
  toggleFilter();
}
