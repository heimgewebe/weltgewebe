import { describe, it, expect } from "vitest";
import {
  rewritePmtilesUrl,
  resolveBasemapStyle,
  REMOTE_VOYAGER_STYLE_URL,
  REMOTE_DARK_MATTER_STYLE_URL,
} from "./basemap";

describe("rewritePmtilesUrl", () => {
  it("rewrites bare pmtiles alias to local dev proxy", () => {
    const result = rewritePmtilesUrl(
      "pmtiles://basemap-hamburg.pmtiles",
      "http://localhost:5173",
    );
    expect(result).toBe(
      "pmtiles://http://localhost:5173/local-basemap/basemap-hamburg.pmtiles",
    );
  });

  it("leaves fully qualified pmtiles URLs unchanged", () => {
    const result = rewritePmtilesUrl(
      "pmtiles://example.com/path/tiles.pmtiles",
      "http://localhost:5173",
    );
    expect(result).toBe("pmtiles://example.com/path/tiles.pmtiles");
  });

  it("leaves non-pmtiles URLs unchanged", () => {
    const result = rewritePmtilesUrl(
      "https://example.com/style.json",
      "http://localhost:5173",
    );
    expect(result).toBe("https://example.com/style.json");
  });

  it("leaves empty string unchanged", () => {
    expect(rewritePmtilesUrl("", "http://localhost:5173")).toBe("");
  });
});

describe("resolveBasemapStyle", () => {
  it("returns styleUrl for remote-style light mode", () => {
    const result = resolveBasemapStyle(
      {
        mode: "remote-style",
        styleUrl: "https://example.com/style.json",
      } as any,
      "light",
    );
    expect(result).toBe("https://example.com/style.json");
  });

  it("returns explicit darkStyleUrl for remote-style dark mode", () => {
    const result = resolveBasemapStyle(
      {
        mode: "remote-style",
        styleUrl: REMOTE_VOYAGER_STYLE_URL,
        darkStyleUrl: "https://example.com/dark.json",
      } as any,
      "dark",
    );
    expect(result).toBe("https://example.com/dark.json");
  });

  it("maps Voyager to Dark Matter when no darkStyleUrl is set", () => {
    const result = resolveBasemapStyle(
      {
        mode: "remote-style",
        styleUrl: REMOTE_VOYAGER_STYLE_URL,
      } as any,
      "dark",
    );
    expect(result).toBe(REMOTE_DARK_MATTER_STYLE_URL);
  });

  it("keeps a custom remote light URL for dark when no darkStyleUrl is set", () => {
    const result = resolveBasemapStyle(
      {
        mode: "remote-style",
        styleUrl: "https://tiles.example.org/custom-style.json",
      } as any,
      "dark",
    );
    expect(result).toBe("https://tiles.example.org/custom-style.json");
  });

  it("throws when remote-style has no styleUrl in light mode", () => {
    expect(() =>
      resolveBasemapStyle({ mode: "remote-style" } as any, "light"),
    ).toThrow("styleUrl required");
  });

  it("throws when remote-style has no styleUrl in dark mode", () => {
    expect(() =>
      resolveBasemapStyle({ mode: "remote-style" } as any, "dark"),
    ).toThrow("styleUrl required");
  });

  it("returns the nationwide light path for legacy local-sovereign config without a variant", () => {
    const result = resolveBasemapStyle(
      { mode: "local-sovereign" } as any,
      "light",
    );
    expect(result).toMatch(
      /^\/local-basemap\/style-germany\.json\?v=0\.4\.0&build=[^&]+$/,
    );
    expect(result).not.toContain("cartocdn");
  });

  it("returns the regional light path only when rollback is explicit", () => {
    const result = resolveBasemapStyle(
      { mode: "local-sovereign", variant: "regional" } as any,
      "light",
    );
    expect(result).toMatch(
      /^\/local-basemap\/style\.json\?v=0\.4\.0&build=[^&]+$/,
    );
    expect(result).not.toContain("cartocdn");
  });

  it("returns local dark path for local-sovereign regional", () => {
    const result = resolveBasemapStyle(
      { mode: "local-sovereign", variant: "regional" } as any,
      "dark",
    );
    expect(result).toMatch(
      /^\/local-basemap\/style-dark\.json\?v=0\.4\.0&build=[^&]+$/,
    );
    expect(result).not.toContain("cartocdn");
  });

  it("returns Germany light and dark local paths without remote hosts", () => {
    const light = resolveBasemapStyle(
      { mode: "local-sovereign", variant: "germany" } as any,
      "light",
    );
    const dark = resolveBasemapStyle(
      { mode: "local-sovereign", variant: "germany" } as any,
      "dark",
    );
    expect(light).toMatch(
      /^\/local-basemap\/style-germany\.json\?v=0\.4\.0&build=[^&]+$/,
    );
    expect(dark).toMatch(
      /^\/local-basemap\/style-germany-dark\.json\?v=0\.4\.0&build=[^&]+$/,
    );
    expect(light).not.toContain("cartocdn");
    expect(dark).not.toContain("cartocdn");
  });
});
