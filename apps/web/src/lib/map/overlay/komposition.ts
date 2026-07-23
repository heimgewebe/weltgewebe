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

function targetIsMarker(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLElement && target.closest(".map-marker") !== null
  );
}

const LONG_PRESS_MS = 800;
// 10px squared. Below this a press counts as a stationary click/tap; above it
// the gesture is a pan/drag and never places a point.
const TAP_MOVE_TOLERANCE_SQ = 100;

export function setupKompositionInteraction(map: MapLibreMap) {
  let longPressTimer: ReturnType<typeof setTimeout> | undefined;
  let startX = 0;
  let startY = 0;
  // A press only counts for composition if it started on the empty map (not on
  // a marker) while authenticated. Marker presses and anonymous presses never
  // arm a gesture, so their release can never set or move a point.
  let gestureArmed = false;
  // Set once the longpress timer has fired for the current press, so the
  // trailing mouseup/touchend does not place the same point a second time.
  let longPressFired = false;

  const clearLongPressTimer = () => {
    if (longPressTimer !== undefined) {
      clearTimeout(longPressTimer);
      longPressTimer = undefined;
    }
  };

  const cancelGesture = () => {
    clearLongPressTimer();
    gestureArmed = false;
    longPressFired = false;
  };

  const setPoint = (
    lngLat: { lng: number; lat: number },
    source: "map-longpress" | "map-tap",
  ) => {
    enterKomposition({
      mode: isPlacingGarnrolle() ? "place-garnrolle" : "new-knoten",
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

    gestureArmed = true;
    startX = point.x;
    startY = point.y;
    longPressTimer = setTimeout(() => {
      longPressFired = true;
      setPoint(lngLat, "map-longpress");
    }, LONG_PRESS_MS);
  };

  const trackMove = (point: { x: number; y: number }) => {
    if (!gestureArmed) return;
    const dx = point.x - startX;
    const dy = point.y - startY;
    if (dx * dx + dy * dy > TAP_MOVE_TOLERANCE_SQ) {
      // Movement beyond the tolerance is a pan, not a placement gesture.
      cancelGesture();
    }
  };

  const endGesture = (
    point: { x: number; y: number },
    lngLat: { lng: number; lat: number },
  ) => {
    const armed = gestureArmed;
    const alreadyPlaced = longPressFired;
    cancelGesture();
    if (!armed || alreadyPlaced) return;
    const dx = point.x - startX;
    const dy = point.y - startY;
    if (dx * dx + dy * dy > TAP_MOVE_TOLERANCE_SQ) return;
    // A stationary release is a click/tap. Only the explicit Garnrolle
    // placement mode treats it as "set this point"; normal node composition
    // deliberately stays longpress-only.
    if (!isPlacingGarnrolle()) return;
    setPoint(lngLat, "map-tap");
  };

  const handleMousedown = (e: MapMouseEvent) => {
    beginGesture(e.point, e.lngLat, e.originalEvent.target);
  };
  const handleMousemove = (e: MapMouseEvent) => {
    trackMove(e.point);
  };
  const handleMouseup = (e: MapMouseEvent) => {
    endGesture(e.point, e.lngLat);
  };

  const handleTouchstart = (e: MapTouchEvent) => {
    beginGesture(e.point, e.lngLat, e.originalEvent.target);
  };
  const handleTouchmove = (e: MapTouchEvent) => {
    trackMove(e.point);
  };
  const handleTouchend = (e: MapTouchEvent) => {
    endGesture(e.point, e.lngLat);
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
  map.on("touchcancel", cancelGesture);

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
    map.off("touchcancel", cancelGesture);
  };
}
