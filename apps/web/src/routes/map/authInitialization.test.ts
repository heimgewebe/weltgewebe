import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = readFileSync(
  new URL("./+page.svelte", import.meta.url),
  "utf-8",
);

describe("map auth initialization contract", () => {
  it("does not hold public map creation behind an auth timeout", () => {
    expect(source).not.toContain("resolveInitialAuthStatus");
    expect(source).not.toContain("timeoutMs = 2500");
    expect(source).not.toMatch(
      /Promise\.all\([\s\S]*checkAuth|Promise\.all\([\s\S]*authStore/,
    );

    const mapImport = source.indexOf(
      'const maplibregl = await import("maplibre-gl")',
    );
    const authSnapshot = source.indexOf("const initialAuth = get(authStore)");
    const mapConstruction = source.indexOf("map = new maplibregl.Map");

    expect(mapImport).toBeGreaterThan(-1);
    expect(authSnapshot).toBeGreaterThan(mapImport);
    expect(mapConstruction).toBeGreaterThan(authSnapshot);
  });
});
