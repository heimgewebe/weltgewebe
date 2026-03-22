import { resolveBasemapMode } from "../src/lib/map/config/basemap.current";
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

test.describe("resolveBasemapMode", () => {
  test("returns 'local-sovereign' when envMode is explicitly 'local-sovereign'", () => {
    expect(resolveBasemapMode("local-sovereign", false)).toBe(
      "local-sovereign",
    );
    expect(resolveBasemapMode("local-sovereign", true)).toBe("local-sovereign");
  });

  test("returns 'remote-style' when envMode is explicitly 'remote-style'", () => {
    expect(resolveBasemapMode("remote-style", false)).toBe("remote-style");
    expect(resolveBasemapMode("remote-style", true)).toBe("remote-style");
  });

  test("falls back to 'local-sovereign' in local context if envMode is missing or invalid", () => {
    expect(resolveBasemapMode(undefined, true)).toBe("local-sovereign");
    expect(resolveBasemapMode("invalid-mode", true)).toBe("local-sovereign");
  });

  test("falls back to 'remote-style' in production context if envMode is missing or invalid", () => {
    expect(resolveBasemapMode(undefined, false)).toBe("remote-style");
    expect(resolveBasemapMode("invalid-mode", false)).toBe("remote-style");
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

  test("returns local dev-server style URL for local-sovereign", () => {
    const config: BasemapConfig = {
      mode: "local-sovereign",
      center: [0, 0],
      zoom: 1,
    };

    expect(resolveBasemapStyle(config)).toBe("/local-basemap/style.json");
  });
});
