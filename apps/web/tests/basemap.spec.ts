import { test, expect } from "@playwright/test";
import { resolveBasemapStyle, rewritePmtilesUrl } from "../src/lib/map/basemap";
import type { BasemapConfig } from "../src/lib/map/config/basemap.current";

test.describe("rewritePmtilesUrl", () => {
  test("rewrites bare alias to local dev path", () => {
    const origin = "http://localhost:5173";
    const url = "pmtiles://basemap-hamburg.pmtiles";
    expect(rewritePmtilesUrl(url, origin)).toBe(
      "pmtiles://http://localhost:5173/local-basemap/basemap-hamburg.pmtiles",
    );
  });

  test("leaves qualified PMTiles URL with path unchanged", () => {
    const origin = "http://localhost:5173";
    const url = "pmtiles://http://example.com/basemap-hamburg.pmtiles";
    expect(rewritePmtilesUrl(url, origin)).toBe(url);
  });

  test("leaves non-PMTiles URLs unchanged", () => {
    const origin = "http://localhost:5173";
    const url = "https://example.com/style.json";
    expect(rewritePmtilesUrl(url, origin)).toBe(url);
  });
});

test.describe("resolveBasemapStyle", () => {
  test("returns styleUrl for remote-style when provided", () => {
    const config: BasemapConfig = {
      mode: "remote-style",
      styleUrl: "https://example.com/style.json",
      center: [0, 0],
      zoom: 1,
    };
    expect(resolveBasemapStyle(config)).toBe("https://example.com/style.json");
  });

  test("throws an error for remote-style if styleUrl is missing", () => {
    const config = {
      mode: "remote-style",
      center: [0, 0],
      zoom: 1,
    } as any; // Type casting to test runtime guard
    expect(() => resolveBasemapStyle(config)).toThrow(
      "styleUrl required for remote-style",
    );
  });

  test("returns local dev path for local-sovereign mode", () => {
    const config: BasemapConfig = {
      mode: "local-sovereign",
      center: [0, 0],
      zoom: 1,
    };

    expect(resolveBasemapStyle(config)).toBe("/local-basemap/style.json");
  });
});
