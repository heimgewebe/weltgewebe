import { describe, it, expect } from "vitest";
import { resolveBasemapMode, currentBasemap } from "./basemap.current";
import { resolveBasemapStyle } from "../basemap";

const CARTO_HOST = "basemaps.cartocdn.com";
const CARTO_STYLE_URL =
  "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json";

describe("resolveBasemapMode", () => {
  it("honours an explicit local-sovereign value regardless of context", () => {
    expect(resolveBasemapMode("local-sovereign", true)).toBe("local-sovereign");
    expect(resolveBasemapMode("local-sovereign", false)).toBe(
      "local-sovereign",
    );
  });

  it("honours an explicit remote-style value regardless of context", () => {
    expect(resolveBasemapMode("remote-style", true)).toBe("remote-style");
    expect(resolveBasemapMode("remote-style", false)).toBe("remote-style");
  });

  it("falls back to local-sovereign in local context when unset or invalid", () => {
    expect(resolveBasemapMode(undefined, true)).toBe("local-sovereign");
    expect(resolveBasemapMode("garbage", true)).toBe("local-sovereign");
    expect(resolveBasemapMode("", true)).toBe("local-sovereign");
  });

  it("falls back to remote-style in production context when unset or invalid", () => {
    expect(resolveBasemapMode(undefined, false)).toBe("remote-style");
    expect(resolveBasemapMode("garbage", false)).toBe("remote-style");
    expect(resolveBasemapMode("", false)).toBe("remote-style");
  });
});

describe("resolveBasemapStyle", () => {
  it("maps the default regional sovereign variant to style.json", () => {
    const style = resolveBasemapStyle({
      mode: "local-sovereign",
      variant: "regional",
    } as any);
    expect(style).toMatch(
      /^\/local-basemap\/style\.json\?v=0\.3\.1&build=[^&]+$/,
    );
    expect(style).not.toContain(CARTO_HOST);
  });

  it("maps the Germany sovereign variant to the isolated Germany style", () => {
    const style = resolveBasemapStyle({
      mode: "local-sovereign",
      variant: "germany",
    } as any);
    expect(style).toMatch(
      /^\/local-basemap\/style-germany\.json\?v=0\.3\.1&build=[^&]+$/,
    );
    expect(style).not.toContain(CARTO_HOST);
  });

  it("keeps legacy local config objects on the regional rollback path", () => {
    const style = resolveBasemapStyle({ mode: "local-sovereign" } as any);
    expect(style).toContain("/local-basemap/style.json");
  });

  it("returns the explicit CARTO url only for remote-style", () => {
    const style = resolveBasemapStyle({
      mode: "remote-style",
      styleUrl: CARTO_STYLE_URL,
    } as any);
    expect(style).toBe(CARTO_STYLE_URL);
    expect(style).toContain(CARTO_HOST);
  });
});

describe("currentBasemap (build-time generated config)", () => {
  it("never carries a CARTO style url in local-sovereign mode", () => {
    if (currentBasemap.mode === "local-sovereign") {
      expect(currentBasemap).not.toHaveProperty("styleUrl");
      expect(["regional", "germany"]).toContain(currentBasemap.variant);
      expect(resolveBasemapStyle(currentBasemap)).toMatch(
        /^\/local-basemap\/style(?:-germany)?\.json\?v=0\.3\.1&build=[^&]+$/,
      );
    } else {
      expect(currentBasemap.styleUrl).toContain(CARTO_HOST);
    }
  });
});
