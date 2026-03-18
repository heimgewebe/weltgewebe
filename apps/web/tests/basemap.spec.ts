import { test, expect } from "@playwright/test";
import { resolveBasemapStyle, rewritePmtilesUrl } from "../src/lib/map/basemap";
import type { BasemapConfig } from "../src/lib/map/config/basemap.current";

test.describe("rewritePmtilesUrl", () => {
  test("rewrites bare local alias (no path) to full dev-server URL", () => {
    const origin = "http://localhost:5173";
    const url = "pmtiles://basemap-hamburg.pmtiles";
    expect(rewritePmtilesUrl(url, origin)).toBe(
      "pmtiles://http://localhost:5173/local-basemap/basemap-hamburg.pmtiles",
    );
  });

  test("does not rewrite fully qualified PMTiles URL with path", () => {
    const origin = "http://localhost:5173";
    const url = "pmtiles://http://example.com/basemap-hamburg.pmtiles";
    expect(rewritePmtilesUrl(url, origin)).toBe(url);
  });

  test("does not rewrite non-PMTiles URL", () => {
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

  test("throws for local-sovereign until a real local asset end-to-end verification is done", () => {
    const config: BasemapConfig = {
      mode: "local-sovereign",
      center: [0, 0],
      zoom: 1,
    };

    expect(() => resolveBasemapStyle(config)).toThrow(
      "dev-infrastructure is prepared, but requires an actual local .pmtiles artifact",
    );
  });
});
