import type { AuthStatus } from "$lib/auth/store";
import { hasRenderableMapPosition } from "$lib/map/coordinates";
import type { MapEntityViewModel, MapLoadState } from "$lib/map/types";
import type { MapUrlFocus } from "$lib/map/urlState";

type MapAuthIdentity = Pick<AuthStatus, "authenticated" | "account_id">;

export type MapCameraTargetSource =
  | "focus"
  | "own-garnrolle"
  | "content"
  | "fallback";

export type MapCameraBounds = [
  southwest: [number, number],
  northeast: [number, number],
];

export type MapCameraTarget =
  | {
      kind: "point";
      center: [number, number];
      zoom: number;
      source: MapCameraTargetSource;
    }
  | {
      kind: "bounds";
      bounds: MapCameraBounds;
      maxZoom: number;
      source: "content";
    };

export const MAP_CONTENT_FIT_MAX_ZOOM = 13;

export interface InitialMapCameraOptions {
  loadState: MapLoadState;
  focusedZoom?: number;
  contentMaxZoom?: number;
}

export interface ViewportBounds {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

export interface ProjectedSearchMatch {
  item: MapEntityViewModel;
  point: { x: number; y: number };
}

export type IndicatorSide = "top" | "right" | "bottom" | "left";

export interface SearchDirectionIndicator {
  item: MapEntityViewModel;
  x: number;
  y: number;
  angle: number;
  side: IndicatorSide;
}

function findFocusTarget(
  markers: MapEntityViewModel[],
  focus: MapUrlFocus | null,
): MapEntityViewModel | undefined {
  if (!focus) return undefined;
  return markers.find(
    (marker) => marker.type === focus.type && marker.id === focus.id,
  );
}

function findOwnGarnrolle(
  markers: MapEntityViewModel[],
  auth: MapAuthIdentity,
): MapEntityViewModel | undefined {
  if (!auth.authenticated || !auth.account_id) return undefined;
  return markers.find(
    (marker) => marker.type === "garnrolle" && marker.id === auth.account_id,
  );
}

function resolveContentTarget(
  markers: MapEntityViewModel[],
  maxZoom: number,
): MapCameraTarget | null {
  const renderable = markers.filter(hasRenderableMapPosition);
  if (renderable.length === 0) return null;

  let west = Number.POSITIVE_INFINITY;
  let south = Number.POSITIVE_INFINITY;
  let east = Number.NEGATIVE_INFINITY;
  let north = Number.NEGATIVE_INFINITY;
  for (const marker of renderable) {
    west = Math.min(west, marker.lon);
    south = Math.min(south, marker.lat);
    east = Math.max(east, marker.lon);
    north = Math.max(north, marker.lat);
  }

  if (west === east && south === north) {
    return {
      kind: "point",
      center: [west, south],
      zoom: maxZoom,
      source: "content",
    };
  }

  return {
    kind: "bounds",
    bounds: [
      [west, south],
      [east, north],
    ],
    maxZoom,
    source: "content",
  };
}

/**
 * Resolves the first camera position before MapLibre creates its first frame.
 * Explicit focus addressing wins, followed by the signed-in person's public
 * Garnrolle position. A complete renderable scene is otherwise fitted; partial,
 * failed, or empty scenes use the configured basemap fallback.
 */
export function resolveInitialMapCamera(
  markers: MapEntityViewModel[],
  auth: MapAuthIdentity,
  focus: MapUrlFocus | null,
  fallbackCenter: [number, number],
  fallbackZoom: number,
  {
    loadState,
    focusedZoom = 14,
    contentMaxZoom = MAP_CONTENT_FIT_MAX_ZOOM,
  }: InitialMapCameraOptions,
): MapCameraTarget {
  const focusTarget = findFocusTarget(markers, focus);
  if (hasRenderableMapPosition(focusTarget)) {
    return {
      kind: "point",
      center: [focusTarget!.lon, focusTarget!.lat],
      zoom: Math.max(fallbackZoom, focusedZoom),
      source: "focus",
    };
  }

  const ownGarnrolle = findOwnGarnrolle(markers, auth);
  if (hasRenderableMapPosition(ownGarnrolle)) {
    return {
      kind: "point",
      center: [ownGarnrolle!.lon, ownGarnrolle!.lat],
      zoom: Math.max(fallbackZoom, focusedZoom),
      source: "own-garnrolle",
    };
  }

  if (loadState === "ok") {
    const contentTarget = resolveContentTarget(markers, contentMaxZoom);
    if (contentTarget) return contentTarget;
  }

  return {
    kind: "point",
    center: fallbackCenter,
    zoom: fallbackZoom,
    source: "fallback",
  };
}

function isInsideBounds(
  point: { x: number; y: number },
  bounds: ViewportBounds,
): boolean {
  return (
    point.x >= bounds.left &&
    point.x <= bounds.right &&
    point.y >= bounds.top &&
    point.y <= bounds.bottom
  );
}

function intersectRayWithBounds(
  point: { x: number; y: number },
  bounds: ViewportBounds,
): Omit<SearchDirectionIndicator, "item"> | null {
  if (isInsideBounds(point, bounds)) return null;

  const centerX = (bounds.left + bounds.right) / 2;
  const centerY = (bounds.top + bounds.bottom) / 2;
  const dx = point.x - centerX;
  const dy = point.y - centerY;

  if (!Number.isFinite(dx) || !Number.isFinite(dy) || (dx === 0 && dy === 0)) {
    return null;
  }

  const candidates: Array<{ scale: number; side: IndicatorSide }> = [];
  if (dx > 0) {
    candidates.push({ scale: (bounds.right - centerX) / dx, side: "right" });
  } else if (dx < 0) {
    candidates.push({ scale: (bounds.left - centerX) / dx, side: "left" });
  }
  if (dy > 0) {
    candidates.push({ scale: (bounds.bottom - centerY) / dy, side: "bottom" });
  } else if (dy < 0) {
    candidates.push({ scale: (bounds.top - centerY) / dy, side: "top" });
  }

  const hit = candidates
    .filter((candidate) => candidate.scale >= 0)
    .sort((a, b) => a.scale - b.scale)[0];
  if (!hit) return null;

  return {
    x: centerX + dx * hit.scale,
    y: centerY + dy * hit.scale,
    angle: (Math.atan2(dy, dx) * 180) / Math.PI,
    side: hit.side,
  };
}

function spreadSideIndicators(
  indicators: SearchDirectionIndicator[],
  bounds: ViewportBounds,
): SearchDirectionIndicator[] {
  const grouped = new Map<IndicatorSide, SearchDirectionIndicator[]>();
  for (const indicator of indicators) {
    const group = grouped.get(indicator.side) ?? [];
    group.push(indicator);
    grouped.set(indicator.side, group);
  }

  const result: SearchDirectionIndicator[] = [];
  for (const [side, group] of grouped) {
    const horizontal = side === "top" || side === "bottom";
    const minimum = horizontal ? bounds.left : bounds.top;
    const maximum = horizontal ? bounds.right : bounds.bottom;
    const axis = (indicator: SearchDirectionIndicator) =>
      horizontal ? indicator.x : indicator.y;

    group.sort((a, b) => axis(a) - axis(b));
    const available = Math.max(0, maximum - minimum);
    const spacing = Math.min(52, available / Math.max(group.length + 1, 2));
    const placed: number[] = [];

    group.forEach((indicator, index) => {
      const desired = axis(indicator);
      const lowerBound = index === 0 ? minimum : placed[index - 1] + spacing;
      placed.push(Math.max(desired, lowerBound));
    });

    if (placed.length > 0 && placed[placed.length - 1] > maximum) {
      const overflow = placed[placed.length - 1] - maximum;
      for (let index = 0; index < placed.length; index += 1) {
        placed[index] -= overflow;
      }
      if (placed[0] < minimum) {
        const step = available / Math.max(placed.length - 1, 1);
        for (let index = 0; index < placed.length; index += 1) {
          placed[index] =
            placed.length === 1
              ? (minimum + maximum) / 2
              : minimum + step * index;
        }
      }
    }

    group.forEach((indicator, index) => {
      result.push({
        ...indicator,
        x: horizontal ? placed[index] : indicator.x,
        y: horizontal ? indicator.y : placed[index],
      });
    });
  }

  return result;
}

/**
 * Converts projected offscreen search results into collision-reduced buttons on
 * the usable viewport edge. Results already visible inside the usable map area
 * are omitted because their actual marker is highlighted directly.
 */
export function deriveSearchDirectionIndicators(
  matches: ProjectedSearchMatch[],
  bounds: ViewportBounds,
): SearchDirectionIndicator[] {
  if (
    !Number.isFinite(bounds.left) ||
    !Number.isFinite(bounds.top) ||
    !Number.isFinite(bounds.right) ||
    !Number.isFinite(bounds.bottom) ||
    bounds.right <= bounds.left ||
    bounds.bottom <= bounds.top
  ) {
    return [];
  }

  const indicators = matches.flatMap(({ item, point }) => {
    const intersection = intersectRayWithBounds(point, bounds);
    return intersection ? [{ item, ...intersection }] : [];
  });

  return spreadSideIndicators(indicators, bounds);
}
