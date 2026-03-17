import { test, expect } from "@playwright/test";
import { resolvePmtilesUrl } from "../src/lib/map/basemap";

test.describe("PMTiles Resolver Logic", () => {
  const mockOrigin = "http://localhost:5173";

  test("rewrites bare aliases to local basemap directory", () => {
    const inputUrl = "pmtiles://basemap-hamburg.pmtiles";
    const result = resolvePmtilesUrl(inputUrl, mockOrigin);
    expect(result).toBe(
      "pmtiles://http://localhost:5173/basemap/basemap-hamburg.pmtiles",
    );
  });

  test("does not rewrite fully qualified PMTiles URLs with remote hosts", () => {
    const inputUrl = "pmtiles://tiles.weltgewebe.org/basemap.pmtiles";
    const result = resolvePmtilesUrl(inputUrl, mockOrigin);
    expect(result).toBe("pmtiles://tiles.weltgewebe.org/basemap.pmtiles");
  });

  test("does not affect non-pmtiles URLs", () => {
    const inputUrls = [
      "https://api.maptiler.com/maps/streets/style.json",
      "mapbox://styles/mapbox/streets-v11",
      "http://localhost:8080/data.json",
    ];

    for (const url of inputUrls) {
      expect(resolvePmtilesUrl(url, mockOrigin)).toBe(url);
    }
  });
});
