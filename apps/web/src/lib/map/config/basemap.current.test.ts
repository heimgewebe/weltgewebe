import { describe, it, expect } from "vitest";
import {
  resolveBasemapMode,
  currentBasemap,
  REMOTE_STYLE_URL,
} from "./basemap.current";
import { resolveBasemapStyle } from "../basemap";

const CARTO_HOST = "basemaps.cartocdn.com";

describe("resolveBasemapMode", () => {
  it("honours an explicit local-sovereign value", () => {
    expect(resolveBasemapMode("local-sovereign", false)).toBe(
      "local-sovereign",
    );
    expect(resolveBasemapMode("local-sovereign", true)).toBe("local-sovereign");
  });

  it("honours an explicit remote-style value", () => {
    expect(resolveBasemapMode("remote-style", true)).toBe("remote-style");
    expect(resolveBasemapMode("remote-style", false)).toBe("remote-style");
  });

  it("defaults to local-sovereign in a local context when unset", () => {
    expect(resolveBasemapMode(undefined, true)).toBe("local-sovereign");
  });

  it("defaults to remote-style in a non-local context when unset", () => {
    // Documented default for generic/production builds without an explicit mode.
    // The Heimserver/Edge deploy sets PUBLIC_BASEMAP_MODE=local-sovereign
    // explicitly (see scripts/weltgewebe-up), so it never relies on this branch.
    expect(resolveBasemapMode(undefined, false)).toBe("remote-style");
  });

  it("falls back to the default for unknown values instead of trusting them", () => {
    expect(resolveBasemapMode("garbage", true)).toBe("local-sovereign");
    expect(resolveBasemapMode("", false)).toBe("remote-style");
  });
});

describe("local-sovereign never leaks a remote basemap", () => {
  it("resolves the style to the local route, not CARTO", () => {
    const style = resolveBasemapStyle({ mode: "local-sovereign" } as any);
    expect(style).toBe("/local-basemap/style.json");
    expect(style).not.toContain(CARTO_HOST);
    expect(style).not.toContain("voyager-gl-style");
  });

  it("keeps the CARTO url reserved for the explicit remote-style mode", () => {
    expect(REMOTE_STYLE_URL).toContain(CARTO_HOST);
    expect(REMOTE_STYLE_URL).toContain("voyager-gl-style");
  });
});

describe("currentBasemap", () => {
  it("does not carry a CARTO style url when running in local-sovereign mode", () => {
    if (currentBasemap.mode === "local-sovereign") {
      expect(currentBasemap).not.toHaveProperty("styleUrl");
      expect(resolveBasemapStyle(currentBasemap)).toBe(
        "/local-basemap/style.json",
      );
    } else {
      // remote-style: the CARTO URL is only present because it was chosen explicitly.
      expect(currentBasemap.styleUrl).toContain(CARTO_HOST);
    }
  });
});
