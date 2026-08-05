import type {
  GeoJSONSource,
  LineLayerSpecification,
  Map as MapLibreMap,
} from "maplibre-gl";
import { isValidMapCoordinate } from "$lib/map/coordinates";
import type { MapEdge, MapEntityViewModel } from "$lib/map/types";
import { EDGE_VISUAL_STYLE } from "./edges";
import { LAYERS } from "./layers";

export const EDGE_MOTION_SOURCE = "edge-motion-source";
export const EDGE_MOTION_LAYER = "edge-motion-layer";
export const EDGE_MOTION_HALO_LAYER = "edge-motion-halo-layer";
export const EDGE_MOTION_DURATION_MS = 720;
export const EDGE_MOTION_MAX_ACTIVE = 8;

type LngLatTuple = [number, number];
type EdgeMotionPhase = "creating" | "releasing";
type LayerFilter = Parameters<MapLibreMap["setFilter"]>[1];

export interface EdgeMotionInput {
  id: string;
  source: LngLatTuple;
  target: LngLatTuple;
  kind: string;
  opacity?: number;
}

export interface EdgeMotionScheduler {
  now: () => number;
  requestFrame: (callback: FrameRequestCallback) => number;
  cancelFrame: (handle: number) => void;
  prefersReducedMotion: () => boolean;
}

interface ActiveMotion {
  input: EdgeMotionInput;
  phase: EdgeMotionPhase;
  from: number;
  to: number;
  startedAt: number;
  durationMs: number;
  sequence: number;
}

export interface EdgeMotionSnapshot {
  activeCount: number;
  framePending: boolean;
  frameRequests: number;
  frameCallbacks: number;
  styleRefreshes: number;
  suppressedIds: string[];
  active: Array<{
    id: string;
    phase: EdgeMotionPhase;
    progress: number;
  }>;
}

function defaultScheduler(): EdgeMotionScheduler {
  return {
    now: () => performance.now(),
    requestFrame: (callback) => requestAnimationFrame(callback),
    cancelFrame: (handle) => cancelAnimationFrame(handle),
    prefersReducedMotion: () =>
      typeof matchMedia === "function" &&
      matchMedia("(prefers-reduced-motion: reduce)").matches,
  };
}

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function easeInOutCubic(value: number): number {
  const progress = clamp01(value);
  return progress < 0.5
    ? 4 * progress * progress * progress
    : 1 - Math.pow(-2 * progress + 2, 3) / 2;
}

function interpolatePoint(
  source: LngLatTuple,
  target: LngLatTuple,
  progress: number,
): LngLatTuple {
  const bounded = clamp01(progress);
  return [
    source[0] + (target[0] - source[0]) * bounded,
    source[1] + (target[1] - source[1]) * bounded,
  ];
}

function buildPointMap(points: readonly MapEntityViewModel[]) {
  const pointMap = new Map<string, MapEntityViewModel>();
  for (const point of points) {
    pointMap.set(point.id, point);
    if (point.type === "webgemeindezentrum") {
      pointMap.set(point.faden_endpoint_id, point);
    }
  }
  return pointMap;
}

/** Resolve the already-authoritative edge and map projection into motion input. */
export function resolveEdgeMotionInput(
  edge: MapEdge,
  points: readonly MapEntityViewModel[],
): EdgeMotionInput | null {
  const pointMap = buildPointMap(points);
  const source = pointMap.get(edge.source_id);
  const target = pointMap.get(edge.target_id);
  if (!source || !target) return null;
  if (
    !isValidMapCoordinate(source.lon, source.lat) ||
    !isValidMapCoordinate(target.lon, target.lat)
  ) {
    return null;
  }
  return {
    id: edge.id,
    source: [source.lon, source.lat],
    target: [target.lon, target.lat],
    kind: edge.edge_kind,
  };
}

/**
 * Short-lived visual overlay for event-bound Faden transitions.
 *
 * The canonical edge source remains untouched. While one transition is visible,
 * the same edge id is filtered from the static layers and drawn in this separate
 * source. A single RAF exists only while at least one transition is active.
 */
export class EdgeMotionController {
  private readonly active = new Map<string, ActiveMotion>();
  private readonly releaseSuppressed = new Set<string>();
  private readonly baseFilters = new Map<string, LayerFilter>();
  private readonly appliedFilterSignatures = new Map<string, string>();
  private visibleEdgeIds: Set<string> | null = null;
  private frameHandle: number | null = null;
  private sequence = 0;
  private destroyed = false;
  private rendering = false;
  private frameRequests = 0;
  private frameCallbacks = 0;
  private styleRefreshes = 0;
  private readonly scheduler: EdgeMotionScheduler;

  private readonly handleStyleData = () => {
    if (this.destroyed || this.hasMotionStyle()) return;
    this.styleRefreshes += 1;
    this.appliedFilterSignatures.clear();
    this.render();
  };

  constructor(
    private readonly map: MapLibreMap,
    scheduler: Partial<EdgeMotionScheduler> = {},
  ) {
    this.scheduler = { ...defaultScheduler(), ...scheduler };
    this.map.on("styledata", this.handleStyleData);
  }

  setVisibleEdgeIds(ids: ReadonlySet<string> | null): void {
    this.visibleEdgeIds = ids == null ? null : new Set(ids);
    this.render();
  }

  /** Release suppression only after canonical data confirms the edge is gone. */
  syncCanonicalEdges(edges: readonly MapEdge[]): void {
    const canonicalIds = new Set(edges.map((edge) => edge.id));
    let changed = false;
    for (const id of this.releaseSuppressed) {
      if (!canonicalIds.has(id)) {
        this.releaseSuppressed.delete(id);
        changed = true;
      }
    }
    if (changed) this.render();
  }

  startCreate(input: EdgeMotionInput): void {
    this.start(input, "creating", 1);
  }

  startRelease(input: EdgeMotionInput): void {
    this.start(input, "releasing", 0);
  }

  cancel(id: string): void {
    const changed = this.active.delete(id) || this.releaseSuppressed.delete(id);
    if (changed) this.render();
    if (this.active.size === 0) this.cancelScheduledFrame();
  }

  refreshStyle(): void {
    this.appliedFilterSignatures.clear();
    this.render();
  }

  inspect(): EdgeMotionSnapshot {
    const now = this.scheduler.now();
    return {
      activeCount: this.active.size,
      framePending: this.frameHandle !== null,
      frameRequests: this.frameRequests,
      frameCallbacks: this.frameCallbacks,
      styleRefreshes: this.styleRefreshes,
      suppressedIds: Array.from(this.releaseSuppressed).sort(),
      active: Array.from(this.active.values())
        .sort((left, right) => left.sequence - right.sequence)
        .map((motion) => ({
          id: motion.input.id,
          phase: motion.phase,
          progress: this.progressAt(motion, now),
        })),
    };
  }

  destroy(): void {
    if (this.destroyed) return;
    this.destroyed = true;
    this.cancelScheduledFrame();
    this.map.off("styledata", this.handleStyleData);
    this.active.clear();
    this.releaseSuppressed.clear();
    this.restoreStaticFilters();
    try {
      if (this.map.getLayer(EDGE_MOTION_LAYER)) {
        this.map.removeLayer(EDGE_MOTION_LAYER);
      }
      if (this.map.getLayer(EDGE_MOTION_HALO_LAYER)) {
        this.map.removeLayer(EDGE_MOTION_HALO_LAYER);
      }
      if (this.map.getSource(EDGE_MOTION_SOURCE)) {
        this.map.removeSource(EDGE_MOTION_SOURCE);
      }
    } catch {
      // Map destruction/style replacement may already have removed these items.
    }
  }

  private start(
    input: EdgeMotionInput,
    phase: EdgeMotionPhase,
    targetProgress: number,
  ): void {
    if (this.destroyed) return;
    const now = this.scheduler.now();
    const existing = this.active.get(input.id);
    const currentProgress = existing
      ? this.progressAt(existing, now)
      : phase === "creating"
        ? 0
        : 1;

    this.releaseSuppressed.delete(input.id);

    if (this.scheduler.prefersReducedMotion()) {
      this.active.delete(input.id);
      if (phase === "releasing") this.releaseSuppressed.add(input.id);
      this.render();
      if (this.active.size === 0) this.cancelScheduledFrame();
      return;
    }

    if (!existing) this.ensureCapacity();
    const distance = Math.abs(targetProgress - currentProgress);
    if (distance <= Number.EPSILON) {
      this.complete({
        input,
        phase,
        from: currentProgress,
        to: targetProgress,
        startedAt: now,
        durationMs: 0,
        sequence: ++this.sequence,
      });
      this.render();
      return;
    }

    this.active.set(input.id, {
      input,
      phase,
      from: currentProgress,
      to: targetProgress,
      startedAt: now,
      durationMs: Math.max(120, EDGE_MOTION_DURATION_MS * distance),
      sequence: existing?.sequence ?? ++this.sequence,
    });
    this.render();
    this.scheduleFrame();
  }

  private ensureCapacity(): void {
    if (this.active.size < EDGE_MOTION_MAX_ACTIVE) return;
    const oldest = Array.from(this.active.values()).sort(
      (left, right) => left.sequence - right.sequence,
    )[0];
    if (!oldest) return;
    this.active.delete(oldest.input.id);
    this.complete(oldest);
  }

  private complete(motion: ActiveMotion): void {
    if (motion.phase === "releasing") {
      this.releaseSuppressed.add(motion.input.id);
    } else {
      this.releaseSuppressed.delete(motion.input.id);
    }
  }

  private progressAt(motion: ActiveMotion, now: number): number {
    if (motion.durationMs <= 0) return motion.to;
    const elapsed = clamp01((now - motion.startedAt) / motion.durationMs);
    const eased = easeInOutCubic(elapsed);
    return motion.from + (motion.to - motion.from) * eased;
  }

  private scheduleFrame(): void {
    if (this.destroyed || this.frameHandle !== null || this.active.size === 0) {
      return;
    }
    this.frameRequests += 1;
    this.frameHandle = this.scheduler.requestFrame(() => {
      this.frameHandle = null;
      this.frameCallbacks += 1;
      this.tick();
    });
  }

  private cancelScheduledFrame(): void {
    if (this.frameHandle === null) return;
    this.scheduler.cancelFrame(this.frameHandle);
    this.frameHandle = null;
  }

  private tick(): void {
    if (this.destroyed) return;
    const now = this.scheduler.now();
    for (const [id, motion] of this.active) {
      const finished = now - motion.startedAt >= motion.durationMs;
      if (!finished) continue;
      this.active.delete(id);
      this.complete(motion);
    }
    this.render();
    if (this.active.size > 0) this.scheduleFrame();
  }

  private render(): void {
    if (this.destroyed || this.rendering) return;
    this.rendering = true;
    try {
      if (!this.ensureMotionStyle()) return;
      const now = this.scheduler.now();
      const features: GeoJSON.Feature<GeoJSON.LineString>[] = [];
      for (const motion of this.active.values()) {
        if (
          this.visibleEdgeIds !== null &&
          !this.visibleEdgeIds.has(motion.input.id)
        ) {
          continue;
        }
        const progress = this.progressAt(motion, now);
        if (progress <= 0) continue;
        features.push({
          type: "Feature",
          geometry: {
            type: "LineString",
            coordinates: [
              motion.input.source,
              interpolatePoint(
                motion.input.source,
                motion.input.target,
                progress,
              ),
            ],
          },
          properties: {
            id: motion.input.id,
            kind: motion.input.kind,
            opacity: clamp01(motion.input.opacity ?? 1),
            phase: motion.phase,
            progress,
          },
        });
      }
      const source = this.map.getSource(EDGE_MOTION_SOURCE) as
        | GeoJSONSource
        | undefined;
      source?.setData({ type: "FeatureCollection", features });
      this.applyStaticFilters();
    } catch {
      // A style replacement can briefly make sources/layers unavailable.
    } finally {
      this.rendering = false;
    }
  }

  private hasMotionStyle(): boolean {
    return Boolean(
      this.map.getSource(EDGE_MOTION_SOURCE) &&
      this.map.getLayer(EDGE_MOTION_HALO_LAYER) &&
      this.map.getLayer(EDGE_MOTION_LAYER),
    );
  }

  private ensureMotionStyle(): boolean {
    if (!this.map.getSource(EDGE_MOTION_SOURCE)) {
      this.map.addSource(EDGE_MOTION_SOURCE, {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
    }

    const firstSymbolId = this.map
      .getStyle()
      ?.layers?.find((layer) => layer.type === "symbol")?.id;
    const commonLayout: LineLayerSpecification["layout"] = {
      "line-join": "round",
      "line-cap": "round",
    };
    if (!this.map.getLayer(EDGE_MOTION_HALO_LAYER)) {
      this.map.addLayer(
        {
          id: EDGE_MOTION_HALO_LAYER,
          type: "line",
          source: EDGE_MOTION_SOURCE,
          layout: commonLayout,
          paint: {
            "line-color": EDGE_VISUAL_STYLE.haloColor,
            "line-width": EDGE_VISUAL_STYLE.haloWidth,
            "line-blur": EDGE_VISUAL_STYLE.haloBlur,
            "line-opacity": [
              "*",
              ["coalesce", ["to-number", ["get", "opacity"]], 0],
              EDGE_VISUAL_STYLE.haloOpacityFactor,
            ],
            "line-dasharray": EDGE_VISUAL_STYLE.dashArray,
          },
        },
        firstSymbolId,
      );
    }
    if (!this.map.getLayer(EDGE_MOTION_LAYER)) {
      this.map.addLayer(
        {
          id: EDGE_MOTION_LAYER,
          type: "line",
          source: EDGE_MOTION_SOURCE,
          layout: commonLayout,
          paint: {
            "line-color": EDGE_VISUAL_STYLE.mainColor,
            "line-width": EDGE_VISUAL_STYLE.mainWidth,
            "line-opacity": ["coalesce", ["to-number", ["get", "opacity"]], 0],
            "line-dasharray": EDGE_VISUAL_STYLE.dashArray,
          },
        },
        firstSymbolId,
      );
    }
    return true;
  }

  private hiddenIds(): string[] {
    return Array.from(
      new Set([...this.active.keys(), ...this.releaseSuppressed]),
    ).sort();
  }

  private applyStaticFilters(): void {
    const hiddenIds = this.hiddenIds();
    for (const layerId of [LAYERS.EDGES_HALO_LAYER, LAYERS.EDGES_LAYER]) {
      if (!this.map.getLayer(layerId)) continue;
      if (!this.baseFilters.has(layerId)) {
        this.baseFilters.set(layerId, this.map.getFilter(layerId) ?? null);
      }
      const baseFilter = this.baseFilters.get(layerId) ?? null;
      const hideFilter = ["!", ["in", ["get", "id"], ["literal", hiddenIds]]];
      const nextFilter =
        hiddenIds.length === 0
          ? baseFilter
          : baseFilter
            ? (["all", baseFilter, hideFilter] as unknown as LayerFilter)
            : (hideFilter as unknown as LayerFilter);
      const signature = JSON.stringify(nextFilter ?? null);
      if (this.appliedFilterSignatures.get(layerId) === signature) continue;
      this.map.setFilter(layerId, nextFilter);
      this.appliedFilterSignatures.set(layerId, signature);
    }
  }

  private restoreStaticFilters(): void {
    for (const [layerId, filter] of this.baseFilters) {
      try {
        if (this.map.getLayer(layerId)) this.map.setFilter(layerId, filter);
      } catch {
        // Map may already be tearing down.
      }
    }
    this.appliedFilterSignatures.clear();
  }
}
