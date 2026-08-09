import { beforeEach, describe, expect, it } from "vitest";
import { get } from "svelte/store";
import {
  activeFilterCount,
  clearFilters,
  clearTopicFilters,
  mapContentFilters,
  toggleFilterTopic,
  toggleFilterType,
} from "./filterStore";

describe("map content filter store", () => {
  beforeEach(clearFilters);

  it("resets topics separately and all axes without hidden selections", () => {
    toggleFilterType("Event");
    toggleFilterTopic("Natur");
    expect(get(activeFilterCount)).toBe(2);

    clearTopicFilters();
    expect([...get(mapContentFilters).contentTypes]).toEqual(["Event"]);
    expect(get(mapContentFilters).topics.size).toBe(0);
    expect(get(activeFilterCount)).toBe(1);

    toggleFilterTopic("Kunst");
    clearFilters();
    expect(get(mapContentFilters).contentTypes.size).toBe(0);
    expect(get(mapContentFilters).topics.size).toBe(0);
    expect(get(activeFilterCount)).toBe(0);
  });
});
