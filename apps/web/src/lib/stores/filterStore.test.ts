import { beforeEach, describe, expect, it } from "vitest";
import { get } from "svelte/store";
import {
  activeFilterCount,
  clearFilters,
  filterState,
  toggleContentType,
  toggleTopic,
} from "./filterStore";

describe("filterStore", () => {
  beforeEach(clearFilters);

  it("keeps independent in-memory content and topic facets", () => {
    toggleContentType("Projekt");
    toggleTopic("Natur");
    toggleTopic("Wohnen");

    expect(get(filterState)).toEqual({
      contentTypes: new Set(["Projekt"]),
      topics: new Set(["Natur", "Wohnen"]),
    });
    expect(get(activeFilterCount)).toBe(3);
  });

  it("clears every facet with the full reset", () => {
    toggleContentType("Garnrolle");
    toggleTopic("Kunst");

    clearFilters();

    expect(get(filterState)).toEqual({
      contentTypes: new Set(),
      topics: new Set(),
    });
    expect(get(activeFilterCount)).toBe(0);
  });
});
