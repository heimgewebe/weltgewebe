import type { Map as MapLibreMap, Marker, MarkerOptions } from "maplibre-gl";
import { hasRenderableMapPosition } from "$lib/map/coordinates";
import type { MapEntityViewModel } from "$lib/map/types";
import type { WeaveEntity } from "$lib/map/weaveTheme";
import { getMapMarkerScale } from "$lib/map/markerScale";
import "./markers.css";
import { garnrolleIcon } from "$lib/ui/icons";
import { weaveRuntime, type WeaveRuntime } from "./weaveRuntime";

export {
  projectMapMarkerViewsForWeave,
  projectMarkersForWeave,
} from "./weaveRuntime";

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

export type MarkerConstructor = new (options?: MarkerOptions) => Marker;

/** Canonical MapLibre marker anchor for nodes, centers, and Garnrollen. */
export const MARKER_GEO_ANCHOR = "center" as const;
const WEAVE_DETAIL_ZOOM = 13.5;
const MARKER_SCALE_WRITE_EPSILON = 0.001;
const FULL_DOM_MARKER_LIMIT = 100;
/**
 * Fixed Web-Mercator bucket zoom for the DOM-marker compatibility layer.
 * The production map currently starts at city-scale zooms, so z14 keeps a
 * moveend query bounded without rebuilding the index for every camera zoom.
 */
const MARKER_SPATIAL_INDEX_ZOOM = 14;
const MARKER_SPATIAL_TILE_COUNT = 1 << MARKER_SPATIAL_INDEX_ZOOM;
const MARKER_SPATIAL_MAX_LAT = 85.05112878;
/**
 * A very wide/invalid viewport is cheaper and safer on the proven full-scan
 * path than by walking a huge number of empty spatial buckets.
 */
const MARKER_SPATIAL_QUERY_BUCKET_LIMIT = 4096;

type MarkerSpatialIndex = {
  buckets: Map<number, number[]>;
  indexById: Map<string, number>;
};

type MapObjectScaleOwnership = {
  owners: Set<symbol>;
  previousValue: string;
  previousPriority: string;
};
const MAP_OBJECT_SCALE_OWNERS = new WeakMap<
  HTMLElement,
  MapObjectScaleOwnership
>();

function markerSpatialTileX(lon: number): number {
  const raw = Math.floor(((lon + 180) / 360) * MARKER_SPATIAL_TILE_COUNT);
  return Math.max(0, Math.min(MARKER_SPATIAL_TILE_COUNT - 1, raw));
}

function markerSpatialTileY(lat: number): number {
  const clamped = Math.max(
    -MARKER_SPATIAL_MAX_LAT,
    Math.min(MARKER_SPATIAL_MAX_LAT, lat),
  );
  const radians = (clamped * Math.PI) / 180;
  const normalized = (1 - Math.asinh(Math.tan(radians)) / Math.PI) / 2;
  const raw = Math.floor(normalized * MARKER_SPATIAL_TILE_COUNT);
  return Math.max(0, Math.min(MARKER_SPATIAL_TILE_COUNT - 1, raw));
}

function markerSpatialBucketKey(lon: number, lat: number): number {
  const x = markerSpatialTileX(lon);
  const y = markerSpatialTileY(lat);
  return y * MARKER_SPATIAL_TILE_COUNT + x;
}

function buildMarkerSpatialIndex(
  points: readonly MapEntityViewModel[],
): MarkerSpatialIndex {
  const buckets = new Map<number, number[]>();
  const indexById = new Map<string, number>();

  points.forEach((item, index) => {
    if (!hasRenderableMapPosition(item)) return;
    const key = markerSpatialBucketKey(item.lon, item.lat);
    const bucket = buckets.get(key);
    if (bucket) bucket.push(index);
    else buckets.set(key, [index]);
    indexById.set(item.id, index);
  });

  return { buckets, indexById };
}

export class NodesOverlay {
  private activeMarkers = new Map<
    string,
    {
      marker: Marker;
      element: HTMLElement;
      item: MapEntityViewModel;
      weaveRoot: HTMLElement | null;
      weaveSignature: string | null;
      cleanup: () => void;
    }
  >();
  private searchMatchIds = new Set<string>();
  private selectedMarkerId: string | null = null;
  private compactWeave = false;
  private markerScale = 1;
  private markerScaleInitialized = false;
  private latestPoints: MapEntityViewModel[] = [];
  private latestShowNodes = true;
  private markerSpatialIndex: MarkerSpatialIndex | null = null;
  private mapScaleContainer: HTMLElement | null = null;
  private readonly mapScaleOwner = Symbol("nodes-overlay-map-scale");
  private readonly handleZoom = () => {
    if (this.map) this.updateZoom(this.map.getZoom());
  };
  private readonly handleMoveEnd = () => {
    this.reconcileVirtualizedMarkers();
  };

  constructor(
    private map: MapLibreMap | null,
    private MarkerClass: MarkerConstructor,
    private readonly runtime: WeaveRuntime = weaveRuntime,
  ) {
    if (this.map && typeof this.map.getContainer === "function") {
      const container = this.map.getContainer();
      this.mapScaleContainer = container;
      let ownership = MAP_OBJECT_SCALE_OWNERS.get(container);
      if (!ownership) {
        ownership = {
          owners: new Set(),
          previousValue: container.style.getPropertyValue("--map-object-scale"),
          previousPriority:
            container.style.getPropertyPriority("--map-object-scale"),
        };
        MAP_OBJECT_SCALE_OWNERS.set(container, ownership);
      }
      ownership.owners.add(this.mapScaleOwner);
    }
    if (
      this.map &&
      typeof this.map.getZoom === "function" &&
      typeof this.map.on === "function"
    ) {
      this.updateZoom(this.map.getZoom());
      this.map.on("zoom", this.handleZoom);
    }
    if (this.map && typeof this.map.on === "function") {
      this.map.on("moveend", this.handleMoveEnd);
    }
  }

  private syncWeaveDetail(root: HTMLElement) {
    root.classList.toggle("woven-node--compact", this.compactWeave);
    root.dataset.weaveDetail = this.compactWeave ? "compact" : "detail";
  }

  private syncMapObjectScale() {
    if (!this.mapScaleContainer) return;
    this.mapScaleContainer.style.setProperty(
      "--map-object-scale",
      this.markerScale.toFixed(3),
    );
  }

  public updateZoom(zoom: number) {
    const compact = zoom < WEAVE_DETAIL_ZOOM;
    const nextMarkerScale = getMapMarkerScale(zoom);
    const compactChanged = compact !== this.compactWeave;
    const markerScaleChanged =
      !this.markerScaleInitialized ||
      Math.abs(nextMarkerScale - this.markerScale) >=
        MARKER_SCALE_WRITE_EPSILON;
    if (!compactChanged && !markerScaleChanged) return;

    if (compactChanged) {
      this.compactWeave = compact;
      for (const { weaveRoot } of this.activeMarkers.values()) {
        if (weaveRoot) this.syncWeaveDetail(weaveRoot);
      }
    }
    if (markerScaleChanged) {
      this.markerScale = nextMarkerScale;
      this.syncMapObjectScale();
      this.markerScaleInitialized = true;
    }
  }

  private getMarkerCategory(
    type: MapEntityViewModel["type"],
  ): "node" | "account" | "webgemeindezentrum" {
    if (type === "garnrolle") return "account";
    if (type === "webgemeindezentrum") return "webgemeindezentrum";
    return "node";
  }

  private shouldVirtualizeMarkers(
    points: readonly MapEntityViewModel[] = this.latestPoints,
  ): boolean {
    return points.length > FULL_DOM_MARKER_LIMIT;
  }

  private rebuildMarkerSpatialIndex(points: readonly MapEntityViewModel[]) {
    this.markerSpatialIndex = this.shouldVirtualizeMarkers(points)
      ? buildMarkerSpatialIndex(points)
      : null;
  }

  private spatialCandidateIndexes(
    viewportBounds: ReturnType<MapLibreMap["getBounds"]>,
  ): number[] | null {
    const index = this.markerSpatialIndex;
    if (!index) return null;
    if (
      typeof viewportBounds.getWest !== "function" ||
      typeof viewportBounds.getEast !== "function" ||
      typeof viewportBounds.getSouth !== "function" ||
      typeof viewportBounds.getNorth !== "function"
    ) {
      return null;
    }

    const west = viewportBounds.getWest();
    const east = viewportBounds.getEast();
    const south = viewportBounds.getSouth();
    const north = viewportBounds.getNorth();
    if (
      ![west, east, south, north].every(Number.isFinite) ||
      west < -180 ||
      west > 180 ||
      east < -180 ||
      east > 180 ||
      south > north
    ) {
      return null;
    }

    const northY = markerSpatialTileY(north);
    const southY = markerSpatialTileY(south);
    const minY = Math.min(northY, southY);
    const maxY = Math.max(northY, southY);
    const xRanges: Array<readonly [number, number]> =
      west <= east
        ? [[markerSpatialTileX(west), markerSpatialTileX(east)]]
        : [
            [markerSpatialTileX(west), MARKER_SPATIAL_TILE_COUNT - 1],
            [0, markerSpatialTileX(east)],
          ];

    const ySpan = maxY - minY + 1;
    const bucketCount = xRanges.reduce(
      (count, [minX, maxX]) => count + (maxX - minX + 1) * ySpan,
      0,
    );
    if (bucketCount > MARKER_SPATIAL_QUERY_BUCKET_LIMIT) return null;

    const candidateIndexes = new Set<number>();
    for (const [minX, maxX] of xRanges) {
      for (let y = minY; y <= maxY; y += 1) {
        for (let x = minX; x <= maxX; x += 1) {
          const bucket = index.buckets.get(y * MARKER_SPATIAL_TILE_COUNT + x);
          if (!bucket) continue;
          for (const itemIndex of bucket) candidateIndexes.add(itemIndex);
        }
      }
    }

    if (this.selectedMarkerId !== null) {
      const selectedIndex = index.indexById.get(this.selectedMarkerId);
      if (selectedIndex !== undefined) candidateIndexes.add(selectedIndex);
    }
    for (const id of this.searchMatchIds) {
      const searchIndex = index.indexById.get(id);
      if (searchIndex !== undefined) candidateIndexes.add(searchIndex);
    }

    return Array.from(candidateIndexes).sort((left, right) => left - right);
  }

  private reconcileVirtualizedMarkers() {
    if (this.shouldVirtualizeMarkers()) {
      this.reconcileMarkers(this.latestPoints, this.latestShowNodes);
    }
  }

  private syncWebgemeindezentrumAppearance(
    element: HTMLElement,
    item: MapEntityViewModel,
  ) {
    if (item.type !== "webgemeindezentrum") return;
    const visual = element.children[0] as HTMLElement | undefined;
    if (!visual) return;
    const borderStyle = item.location_state === "confirmed" ? "" : "dashed";
    if (visual.style.borderStyle !== borderStyle) {
      visual.style.borderStyle = borderStyle;
    }
  }

  private reconcileMarkers(
    points: MapEntityViewModel[],
    showNodes: boolean,
  ): void {
    if (!showNodes) {
      this.activeMarkers.forEach(({ cleanup }) => cleanup());
      this.activeMarkers.clear();
      return;
    }

    const map = this.map;
    if (!map) return;

    const shouldVirtualize = this.shouldVirtualizeMarkers(points);
    const viewportBounds =
      shouldVirtualize && typeof map.getBounds === "function"
        ? map.getBounds()
        : null;
    const spatialIndexes =
      shouldVirtualize && viewportBounds
        ? this.spatialCandidateIndexes(viewportBounds)
        : null;
    const candidates =
      spatialIndexes === null
        ? points
        : spatialIndexes.flatMap((index) => {
            const item = points[index];
            return item ? [item] : [];
          });
    const currentIds = new Set<string>();

    for (const item of candidates) {
      if (!hasRenderableMapPosition(item)) {
        const existing = this.activeMarkers.get(item.id);
        if (existing) {
          existing.cleanup();
          this.activeMarkers.delete(item.id);
        }
        continue;
      }

      if (
        shouldVirtualize &&
        this.selectedMarkerId !== item.id &&
        !this.searchMatchIds.has(item.id) &&
        viewportBounds &&
        typeof viewportBounds.contains === "function" &&
        !viewportBounds.contains([item.lon, item.lat])
      ) {
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

      if (
        existing &&
        existing.element.dataset.markerCategory !== markerCategory
      ) {
        existing.cleanup();
        this.activeMarkers.delete(item.id);
        existing = undefined;
      }

      if (existing) {
        existing.item = item;
        const { marker, element } = existing;
        const lngLat = marker.getLngLat();
        if (
          Math.abs(lngLat.lng - item.lon) > 0.000001 ||
          Math.abs(lngLat.lat - item.lat) > 0.000001
        ) {
          marker.setLngLat([item.lon, item.lat]);
        }
        if (element.title !== item.title) element.title = item.title;
        const ariaLabel = this.runtime.label(item);
        if (element.getAttribute("aria-label") !== ariaLabel) {
          element.setAttribute("aria-label", ariaLabel);
        }
        if (item.type === "webgemeindezentrum") {
          if (element.dataset.locationState !== item.location_state) {
            element.dataset.locationState = item.location_state;
          }
        } else if ("locationState" in element.dataset) {
          delete element.dataset.locationState;
        }
        this.syncWebgemeindezentrumAppearance(element, item);
        if (existing.weaveRoot && item.type !== "garnrolle") {
          existing.weaveSignature = this.runtime.syncRoot(
            existing.weaveRoot,
            item,
            existing.weaveSignature,
          );
        }
      } else {
        const element = document.createElement("button");
        element.type = "button";
        element.className =
          markerCategory === "account"
            ? "map-marker marker-account"
            : markerCategory === "webgemeindezentrum"
              ? "map-marker marker-webgemeindezentrum"
              : "map-marker";

        element.dataset.id = item.id;
        element.dataset.markerCategory = markerCategory;
        if (item.type === "webgemeindezentrum") {
          element.dataset.locationState = item.location_state;
        }
        element.dataset.testid = `marker-${item.type}-${item.id}`;

        const visual = document.createElement("span");
        visual.className =
          markerCategory === "account"
            ? "map-marker__visual marker-account__visual"
            : markerCategory === "webgemeindezentrum"
              ? "map-marker__visual marker-webgemeindezentrum__visual"
              : "map-marker__visual marker-node__visual";
        visual.setAttribute("aria-hidden", "true");

        let weaveRoot: HTMLElement | null = null;
        let weaveSignature: string | null = null;
        if (item.type === "garnrolle") {
          const icon = document.createElement("img");
          icon.className = "marker-account__icon";
          icon.src = garnrolleIcon;
          icon.alt = "";
          icon.setAttribute("aria-hidden", "true");
          icon.draggable = false;
          visual.append(icon);
        } else {
          const category =
            item.type === "webgemeindezentrum" ? "webgemeindezentrum" : "node";
          const woven = this.runtime.createRoot(item as WeaveEntity, category);
          weaveRoot = woven.root;
          weaveSignature = woven.signature;
          this.syncWeaveDetail(weaveRoot);
          if (item.type === "webgemeindezentrum") {
            const icon = document.createElement("span");
            icon.className = "marker-webgemeindezentrum__icon";
            icon.setAttribute("aria-hidden", "true");
            icon.append(weaveRoot);
            visual.append(icon);
          } else {
            visual.append(weaveRoot);
          }
        }

        const halo = document.createElement("span");
        halo.className = "map-marker__halo";
        halo.setAttribute("aria-hidden", "true");

        element.append(visual, halo);
        this.syncWebgemeindezentrumAppearance(element, item);

        element.setAttribute("aria-label", this.runtime.label(item));
        element.title = item.title;

        // Center anchor: map coordinate, MapLibre pin, and visible knot/spool
        // center share one geographic point so Fäden reach the true midpoint.
        const marker = new this.MarkerClass({
          element,
          anchor: MARKER_GEO_ANCHOR,
        })
          .setLngLat([item.lon, item.lat])
          .addTo(map);
        // MapLibre assigns its generic "Map marker" label in the constructor.
        // Restore the domain-specific woven summary after that synchronous step.
        element.setAttribute("aria-label", this.runtime.label(item));

        if (this.searchMatchIds.has(item.id)) {
          element.classList.add("search-highlight");
          element.dataset.searchMatch = "true";
        }
        if (this.selectedMarkerId === item.id) {
          element.classList.add("is-selected");
          element.dataset.selected = "true";
          element.setAttribute("aria-current", "true");
        }

        this.activeMarkers.set(item.id, {
          marker,
          element,
          item,
          weaveRoot,
          weaveSignature,
          cleanup: () => {
            marker.remove();
          },
        });
      }
    }

    for (const [id, { cleanup }] of this.activeMarkers.entries()) {
      if (!currentIds.has(id)) {
        cleanup();
        this.activeMarkers.delete(id);
      }
    }
  }

  public update(points: MapEntityViewModel[], showNodes: boolean): void {
    this.latestPoints = points;
    this.latestShowNodes = showNodes;
    this.rebuildMarkerSpatialIndex(points);
    this.reconcileMarkers(points, showNodes);
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

  private setSelected(id: string, selected: boolean) {
    const entry = this.activeMarkers.get(id);
    if (!entry) return;

    entry.element.classList.toggle("is-selected", selected);
    if (selected) {
      entry.element.dataset.selected = "true";
      entry.element.setAttribute("aria-current", "true");
    } else {
      delete entry.element.dataset.selected;
      entry.element.removeAttribute("aria-current");
    }
  }

  public updateSelection(nextSelectedMarkerId: string | null) {
    if (this.selectedMarkerId === nextSelectedMarkerId) return;

    if (this.selectedMarkerId !== null) {
      this.setSelected(this.selectedMarkerId, false);
    }
    this.selectedMarkerId = nextSelectedMarkerId;
    if (nextSelectedMarkerId !== null) {
      this.setSelected(nextSelectedMarkerId, true);
    }
    this.reconcileVirtualizedMarkers();
  }

  public updateSearchMatches(nextSearchMatchIds: ReadonlySet<string>) {
    const { added, removed } = diffSearchMatchIds(
      this.searchMatchIds,
      nextSearchMatchIds,
    );

    for (const id of removed) this.setSearchMatch(id, false);
    for (const id of added) this.setSearchMatch(id, true);

    this.searchMatchIds = new Set(nextSearchMatchIds);
    this.reconcileVirtualizedMarkers();
  }

  public getActiveMarker(id: string) {
    return this.activeMarkers.get(id);
  }

  public destroy() {
    if (this.map && typeof this.map.off === "function") {
      this.map.off("zoom", this.handleZoom);
      this.map.off("moveend", this.handleMoveEnd);
    }
    if (this.mapScaleContainer) {
      const container = this.mapScaleContainer;
      const ownership = MAP_OBJECT_SCALE_OWNERS.get(container);
      if (
        ownership?.owners.delete(this.mapScaleOwner) &&
        !ownership.owners.size
      ) {
        if (ownership.previousValue) {
          container.style.setProperty(
            "--map-object-scale",
            ownership.previousValue,
            ownership.previousPriority,
          );
        } else {
          container.style.removeProperty("--map-object-scale");
        }
        MAP_OBJECT_SCALE_OWNERS.delete(container);
      }
    }
    this.mapScaleContainer = null;
    this.activeMarkers.forEach(({ cleanup }) => cleanup());
    this.activeMarkers.clear();
    this.searchMatchIds.clear();
    this.selectedMarkerId = null;
    this.latestPoints = [];
    this.latestShowNodes = false;
    this.markerSpatialIndex = null;
  }
}
