import type {
  Map as MapLibreMap,
  MapMouseEvent,
  MapTouchEvent,
} from "maplibre-gl";
import { get } from "svelte/store";
import { enterKomposition, kompositionDraft } from "$lib/stores/uiView";
import { authStore } from "$lib/auth/store";

/**
 * Every authenticated account may create nodes. A longpress by an anonymous user
 * must not open an apparently-functional composition panel — it silently
 * does nothing, exactly like the (disabled) "Weben" tool-fan action.
 */
function canComposeOnMap(): boolean {
  return get(authStore).authenticated;
}

/**
 * The explicit Garnrolle placement mode (reached via `/map?compose=garnrolle`)
 * is a deliberate "pick a point" step, so a plain click/tap already sets the
 * point. Normal node composition stays a conscious longpress gesture and must
 * never be opened by a simple click.
 */
function isPlacingGarnrolle(): boolean {
  return get(kompositionDraft)?.mode === "place-garnrolle";
}

type ClosestTarget = EventTarget & {
  closest(selectors: string): Element | null;
};

/**
 * Marker contents can be HTML or SVG. Checking for a structural `closest`
 * capability covers both without mutating DOM globals in node-based tests.
 */
function targetIsMarker(target: EventTarget | null): boolean {
  if (
    target === null ||
    typeof (target as { closest?: unknown }).closest !== "function"
  ) {
    return false;
  }
  return (target as ClosestTarget).closest(".map-marker") !== null;
}

const LONG_PRESS_MS = 800;
// 10px squared. Below this a press counts as a stationary click/tap; above it
// the gesture is a pan/drag and never places a point.
const TAP_MOVE_TOLERANCE_SQ = 100;
// Some touch stacks emit compatibility mouse events after touchend. Ignore that
// synthetic follow-up briefly so one physical tap cannot place the point twice.
const COMPAT_MOUSE_SUPPRESSION_MS = 500;

type GestureMode = "new-knoten" | "place-garnrolle";
type ActiveGesture = {
  startX: number;
  startY: number;
  mode: GestureMode;
  longPressFired: boolean;
};

export function setupKompositionInteraction(map: MapLibreMap) {
  let longPressTimer: ReturnType<typeof setTimeout> | undefined;
  let activeGesture: ActiveGesture | null = null;
  let suppressMouseUntil = 0;

  const clearLongPressTimer = () => {
    if (longPressTimer !== undefined) {
      clearTimeout(longPressTimer);
      longPressTimer = undefined;
    }
  };

  const cancelGesture = () => {
    clearLongPressTimer();
    activeGesture = null;
  };

  const setPoint = (
    lngLat: { lng: number; lat: number },
    source: "map-longpress" | "map-tap",
    mode: GestureMode,
  ) => {
    enterKomposition({
      mode,
      lngLat: [lngLat.lng, lngLat.lat],
      source,
    });
  };

  const beginGesture = (
    point: { x: number; y: number },
    lngLat: { lng: number; lat: number },
    target: EventTarget | null,
  ) => {
    cancelGesture();
    // Markers own their own click/tap (focus). A press on a marker must never
    // arm placement, so it can never move an already-chosen Garnrolle point.
    if (targetIsMarker(target)) return;
    if (!canComposeOnMap()) return;

    activeGesture = {
      startX: point.x,
      startY: point.y,
      mode: isPlacingGarnrolle() ? "place-garnrolle" : "new-knoten",
      longPressFired: false,
    };
    longPressTimer = setTimeout(() => {
      longPressTimer = undefined;
      const gesture = activeGesture;
      if (gesture === null) return;
      // Authentication may change while the finger/button is still held.
      // Re-check before producing a UI action; the API remains the final guard.
      if (!canComposeOnMap()) {
        cancelGesture();
        return;
      }
      gesture.longPressFired = true;
      setPoint(lngLat, "map-longpress", gesture.mode);
    }, LONG_PRESS_MS);
  };

  const trackMove = (point: { x: number; y: number }) => {
    const gesture = activeGesture;
    if (gesture === null) return;
    const dx = point.x - gesture.startX;
    const dy = point.y - gesture.startY;
    if (dx * dx + dy * dy > TAP_MOVE_TOLERANCE_SQ) {
      // Movement beyond the tolerance is a pan, not a placement gesture.
      cancelGesture();
    }
  };

  const endGesture = (
    point: { x: number; y: number },
    lngLat: { lng: number; lat: number },
  ) => {
    const gesture = activeGesture;
    if (gesture === null) return;
    const dx = point.x - gesture.startX;
    const dy = point.y - gesture.startY;
    cancelGesture();
    if (gesture.longPressFired || !canComposeOnMap()) return;
    if (dx * dx + dy * dy > TAP_MOVE_TOLERANCE_SQ) return;
    // The mode is frozen at press start. A stationary release only places on
    // the explicit Garnrolle picker; normal node composition stays longpress-only.
    if (gesture.mode !== "place-garnrolle" || !isPlacingGarnrolle()) return;
    setPoint(lngLat, "map-tap", gesture.mode);
  };

  const mouseIsSuppressed = () => Date.now() < suppressMouseUntil;
  const suppressCompatibilityMouse = () => {
    suppressMouseUntil = Date.now() + COMPAT_MOUSE_SUPPRESSION_MS;
  };

  const handleMousedown = (e: MapMouseEvent) => {
    if (mouseIsSuppressed()) return;
    beginGesture(e.point, e.lngLat, e.originalEvent.target);
  };
  const handleMousemove = (e: MapMouseEvent) => {
    if (mouseIsSuppressed()) return;
    trackMove(e.point);
  };
  const handleMouseup = (e: MapMouseEvent) => {
    if (mouseIsSuppressed()) return;
    endGesture(e.point, e.lngLat);
  };

  const handleTouchstart = (e: MapTouchEvent) => {
    suppressCompatibilityMouse();
    // Pinch/zoom and other multi-touch gestures belong to the map itself and
    // must never arm composition.
    if (e.points.length !== 1) {
      cancelGesture();
      return;
    }
    beginGesture(e.point, e.lngLat, e.originalEvent.target);
  };
  const handleTouchmove = (e: MapTouchEvent) => {
    if (e.points.length !== 1) {
      cancelGesture();
      return;
    }
    trackMove(e.point);
  };
  const handleTouchend = (e: MapTouchEvent) => {
    endGesture(e.point, e.lngLat);
    suppressCompatibilityMouse();
  };
  const handleTouchcancel = () => {
    cancelGesture();
    suppressCompatibilityMouse();
  };

  map.on("mousedown", handleMousedown);
  map.on("mouseup", handleMouseup);
  map.on("mousemove", handleMousemove);
  map.on("mouseout", cancelGesture);
  map.on("dragstart", cancelGesture);
  map.on("movestart", cancelGesture);

  map.on("touchstart", handleTouchstart);
  map.on("touchend", handleTouchend);
  map.on("touchmove", handleTouchmove);
  map.on("touchcancel", handleTouchcancel);

  return () => {
    cancelGesture();
    map.off("mousedown", handleMousedown);
    map.off("mouseup", handleMouseup);
    map.off("mousemove", handleMousemove);
    map.off("mouseout", cancelGesture);
    map.off("dragstart", cancelGesture);
    map.off("movestart", cancelGesture);

    map.off("touchstart", handleTouchstart);
    map.off("touchend", handleTouchend);
    map.off("touchmove", handleTouchmove);
    map.off("touchcancel", handleTouchcancel);
  };
}
