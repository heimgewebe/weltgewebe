import { writable } from "svelte/store";

export const isFilterOpen = writable<boolean>(false);
export const activeFilters = writable<Set<string>>(new Set());

export function toggleFilter() {
  isFilterOpen.update((v) => !v);
}

export function closeFilter() {
  isFilterOpen.set(false);
}

export function toggleFilterType(type: string) {
  activeFilters.update((set) => {
    const newSet = new Set(set);
    if (newSet.has(type)) {
      newSet.delete(type);
    } else {
      newSet.add(type);
    }
    return newSet;
  });
}

export function clearFilters() {
  activeFilters.set(new Set());
}
