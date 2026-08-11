import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const readSource = (relativePath: string) =>
  readFileSync(new URL(relativePath, import.meta.url), "utf8");

const pageSource = readSource("./+page.svelte");
const surfaceSource = readSource(
  "../../lib/components/map/MapRouteSurface.svelte",
);
const statusSource = readSource(
  "../../lib/components/map/MapRouteStatus.svelte",
);
const overlaysSource = readSource(
  "../../lib/components/map/MapRouteOverlays.svelte",
);

describe("map route component boundaries", () => {
  it("keeps the route as orchestrator instead of owning the map presentation", () => {
    expect(pageSource).toContain("<MapRouteSurface");
    expect(pageSource).toContain("<MapRouteStatus");
    expect(pageSource).toContain("<MapRouteOverlays");
    expect(pageSource).not.toContain("<style>");
    expect(pageSource).not.toContain('class="loading-overlay"');
    expect(pageSource).not.toContain('data-testid="map-init-error"');
    expect(pageSource).not.toContain("loadContextPanelModule");
    expect(pageSource).not.toContain("loadSearchOverlayModule");
    expect(pageSource).toContain("on:retry={retryMapInitialisation}");
    expect(pageSource).toMatch(
      /function retryMapInitialisation\(\)\s*\{\s*window\.location\.reload\(\);\s*\}/,
    );
  });

  it("assigns canvas layout, recovery status and lazy overlays to one owner each", () => {
    expect(surfaceSource).toContain('id="map"');
    expect(surfaceSource).toContain("bind:this={mapElement}");
    expect(surfaceSource).toContain(".maplibregl-ctrl-bottom-right");

    expect(statusSource).toContain('data-testid="load-state-partial"');
    expect(statusSource).toContain('data-testid="load-state-failed"');
    expect(statusSource).toContain('data-testid="map-init-error-retry"');
    expect(statusSource).toContain('dispatch("retry")');

    expect(overlaysSource).toContain(
      'import("$lib/components/ContextPanel.svelte")',
    );
    expect(overlaysSource).toContain(
      'import("$lib/components/SearchOverlay.svelte")',
    );
    expect(overlaysSource).toContain("createResettableLazyImport");
  });
});
