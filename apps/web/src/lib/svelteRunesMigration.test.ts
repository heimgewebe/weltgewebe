import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const srcRoot = fileURLToPath(new URL("../", import.meta.url));

function collectSvelteFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return collectSvelteFiles(path);
    return entry.isFile() && entry.name.endsWith(".svelte") ? [path] : [];
  });
}

function readSource(relativePath: string): string {
  return readFileSync(new URL(relativePath, import.meta.url), "utf8");
}

describe("Svelte 5 runes migration contract", () => {
  it("keeps migrated Svelte components off legacy prop and reactive declarations", () => {
    const offenders = collectSvelteFiles(srcRoot).flatMap((path) => {
      const source = readFileSync(path, "utf8");
      const reasons = [
        /(^|\n)\s*export\s+let\s/.test(source) ? "export let" : null,
        /(^|\n)\s*\$:\s*/.test(source) ? "$:" : null,
        /from\s+["']svelte\/legacy["']/.test(source) ? "svelte/legacy" : null,
      ].filter(Boolean);
      return reasons.length > 0
        ? [`${path.slice(srcRoot.length)}: ${reasons.join(", ")}`]
        : [];
    });

    expect(offenders).toEqual([]);
  });

  it("keeps the map core on explicit state, derivation and effect runes", () => {
    const page = readSource("../routes/map/+page.svelte");
    const marker = readSource("./maplibre/Marker.svelte");
    const mapLibre = readSource("./maplibre/MapLibre.svelte");

    expect(page).toContain("$state(");
    expect(page).toContain("$derived");

    for (const source of [marker, mapLibre]) {
      expect(source).toContain("$state(");
      expect(source).toContain("$derived");
      expect(source).toContain("$effect(");
      expect(source).not.toContain('from "svelte/legacy"');
      expect(source).not.toContain("from 'svelte/legacy'");
    }
  });
});
