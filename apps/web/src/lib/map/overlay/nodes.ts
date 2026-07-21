import type { Map as MapLibreMap, Marker } from "maplibre-gl";
import type { MapEntityViewModel } from "$lib/map/types";
import { ICONS } from "$lib/ui/icons";

function hasRenderablePosition(item: MapEntityViewModel): boolean {
  return (
    Number.isFinite(item.lat) &&
    Number.isFinite(item.lon) &&
    item.lat >= -90 &&
    item.lat <= 90 &&
    item.lon >= -180 &&
    item.lon <= 180
  );
}

export function diffSearchMatchIds(
  previous: ReadonlySet<string>,
  next: ReadonlySet<string>,
): { added: string[]; removed: string[] } {
  const added: string[] = [];
  const removed: string[] = [];

  for (const id of next) {
    if (!previous.has(id)) added.push(id);
  }
  for (const id of previous) {
    if (!next.has(id)) removed.push(id);
  }

  return { added, removed };
}

export class NodesOverlay {
  private activeMarkers = new Map<
    string,
    {
      marker: Marker;
      element: HTMLElement;
      item: MapEntityViewModel;
      cleanup: () => void;
    }
  >();
  private searchMatchIds = new Set<string>();

  constructor(private map: MapLibreMap) {}

  private getMarkerCategory(
    type: MapEntityViewModel["type"],
  ): "node" | "account" {
    return type === "garnrolle" ? "account" : "node";
  }

  public async update(points: MapEntityViewModel[], showNodes: boolean) {
    if (!this.map) return;
    const maplibregl = await import("maplibre-gl");

    if (!showNodes) {
      // If hidden, remove all
      this.activeMarkers.forEach(({ cleanup }) => cleanup());
      this.activeMarkers.clear();
      return;
    }

    const currentIds = new Set<string>();

    for (const item of points) {
      if (!hasRenderablePosition(item)) {
        const existing = this.activeMarkers.get(item.id);
        if (existing) {
          existing.cleanup();
          this.activeMarkers.delete(item.id);
        }
        continue;
      }

      currentIds.add(item.id);
      const markerCategory = this.getMarkerCategory(item.type);
      let existing = this.activeMarkers.get(item.id);

      // Robustness: Check if category changed (e.g. node became account, unlikely but possible)
      if (existing) {
        const isAccount = existing.element.classList.contains("marker-account");
        const shouldBeAccount = markerCategory === "account";

        if (isAccount !== shouldBeAccount) {
          // Category mismatch - force recreate
          existing.cleanup();
          this.activeMarkers.delete(item.id);
          existing = undefined;
        }
      }

      // Check if we need to update or create
      if (existing) {
        // Update item data to prevent stale data in delegated events
        existing.item = item;

        // Update position if changed
        const { marker, element } = existing;
        element.dataset.id = item.id;
        const lngLat = marker.getLngLat();
        if (
          Math.abs(lngLat.lng - item.lon) > 0.000001 ||
          Math.abs(lngLat.lat - item.lat) > 0.000001
        ) {
          marker.setLngLat([item.lon, item.lat]);
        }
        // Update attributes
        if (element.title !== item.title) {
          element.title = item.title;
          element.setAttribute("aria-label", item.title);
        }
        element.dataset.testid = `marker-${item.type}-${item.id}`;
      } else {
        // Create new
        const element = document.createElement("button");
        element.type = "button";
        element.className =
          markerCategory === "account"
            ? "map-marker marker-account"
            : "map-marker";

        // Identifying data for event delegation
        element.dataset.id = item.id;

        // Robust testing selector based on domain semantics (and unique ID for stability)
        element.dataset.testid = `marker-${item.type}-${item.id}`;

        // MapLibre owns the outer element's transform for geographic positioning.
        // All Weltgewebe styling and interaction transforms therefore live on
        // an inner visual element so map movement can never be CSS-interpolated.
        const visual = document.createElement("span");
        visual.className =
          markerCategory === "account"
            ? "map-marker__visual marker-account__visual"
            : "map-marker__visual";
        visual.setAttribute("aria-hidden", "true");

        if (markerCategory === "account") {
          const icon = document.createElement("img");
          icon.className = "marker-account__icon";
          icon.src = ICONS.garnrolle;
          icon.alt = "";
          icon.setAttribute("aria-hidden", "true");
          icon.draggable = false;
          visual.append(icon);
        }

        element.append(visual);

        element.setAttribute("aria-label", item.title);
        element.title = item.title;

        const marker = new maplibregl.Marker({ element, anchor: "bottom" })
          .setLngLat([item.lon, item.lat])
          .addTo(this.map);

        // Re-apply accessibility attributes after addTo()
        element.setAttribute("aria-label", item.title);
        element.title = item.title;

        if (this.searchMatchIds.has(item.id)) {
          element.classList.add("search-highlight");
          element.dataset.searchMatch = "true";
        }

        this.activeMarkers.set(item.id, {
          marker,
          element,
          item,
          cleanup: () => {
            marker.remove();
          },
        });
      }
    }

    // Cleanup removed markers
    for (const [id, { cleanup }] of this.activeMarkers.entries()) {
      if (!currentIds.has(id)) {
        cleanup();
        this.activeMarkers.delete(id);
      }
    }
  }

  private setSearchMatch(id: string, highlighted: boolean) {
    const entry = this.activeMarkers.get(id);
    if (!entry) return;

    if (highlighted) {
      entry.element.classList.add("search-highlight");
      entry.element.dataset.searchMatch = "true";
    } else {
      entry.element.classList.remove("search-highlight");
      delete entry.element.dataset.searchMatch;
    }
  }

  public updateSearchMatches(nextSearchMatchIds: ReadonlySet<string>) {
    const { added, removed } = diffSearchMatchIds(
      this.searchMatchIds,
      nextSearchMatchIds,
    );

    for (const id of removed) this.setSearchMatch(id, false);
    for (const id of added) this.setSearchMatch(id, true);

    this.searchMatchIds = new Set(nextSearchMatchIds);
  }

  public getActiveMarker(id: string) {
    return this.activeMarkers.get(id);
  }

  public destroy() {
    this.activeMarkers.forEach(({ cleanup }) => cleanup());
    this.activeMarkers.clear();
    this.searchMatchIds.clear();
  }
}
