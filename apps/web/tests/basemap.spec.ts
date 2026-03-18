import { test, expect } from "@playwright/test";
import { resolveBasemapStyle } from "../src/lib/map/basemap";
import type { BasemapConfig } from "../src/lib/map/config/basemap.current";

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
    const config: BasemapConfig = {
      mode: "remote-style",
      center: [0, 0],
      zoom: 1,
    };
    expect(() => resolveBasemapStyle(config)).toThrow(
      "styleUrl required for remote-style",
    );
  });

  test("returns local static path for local-sovereign mode", () => {
    const config: BasemapConfig = {
      mode: "local-sovereign",
      center: [0, 0],
      zoom: 1,
    };
    expect(resolveBasemapStyle(config)).toBe("/local-style/style.json");
  });
});
