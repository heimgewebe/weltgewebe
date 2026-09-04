import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { get } from "svelte/store";

type AuthValue = { authenticated: boolean; role: string };

// The overlay reads authentication through the auth store. A minimal writable
// stand-in (hoisted so the mock factory can reference it) lets each test decide
// whether a press is allowed to compose at all. It is implemented without
// `svelte/store` because `vi.hoisted` runs before module imports resolve.
const { authStore } = vi.hoisted(() => {
  let value: AuthValue = { authenticated: true, role: "gast" };
  const subscribers = new Set<(value: AuthValue) => void>();
  return {
    authStore: {
      subscribe(run: (value: AuthValue) => void) {
        run(value);
        subscribers.add(run);
        return () => subscribers.delete(run);
      },
      set(next: AuthValue) {
        value = next;
        for (const run of subscribers) run(value);
      },
    },
  };
});
vi.mock("$lib/auth/store", () => ({ authStore }));

import { setupKompositionInteraction } from "./komposition";
import {
  kompositionDraft,
  leaveToNavigation,
  enterKomposition,
} from "$lib/stores/uiView";

// The production guard only requires the DOM-standard `closest` capability,
// so these tests do not replace global HTMLElement/Element constructors. The
// parent chain also models nested HTML/SVG content inside a map marker.
class FakeElement {
  className: string;
  parent: FakeElement | null;

  constructor(className = "", parent: FakeElement | null = null) {
    this.className = className;
    this.parent = parent;
  }

  closest(selector: string): FakeElement | null {
    if (selector !== ".map-marker") return null;
    if (/(^|\s)map-marker(\s|$)/.test(this.className)) return this;
    return this.parent?.closest(selector) ?? null;
  }
}

type Handler = (event: unknown) => void;
type FakeDocumentTarget = EventTarget & {
  visibilityState: "visible" | "hidden";
};

class FakeMap {
  private handlers = new Map<string, Set<Handler>>();

  on(type: string, handler: Handler) {
    if (!this.handlers.has(type)) this.handlers.set(type, new Set());
    this.handlers.get(type)!.add(handler);
  }

  off(type: string, handler: Handler) {
    this.handlers.get(type)?.delete(handler);
  }

  emit(type: string, event: unknown) {
    for (const handler of this.handlers.get(type) ?? []) handler(event);
  }
}

type PointerEventOptions = {
  target?: unknown;
  touchCount?: number;
  button?: number;
  buttons?: number;
};

function pointerEvent(
  x: number,
  y: number,
  lng: number,
  lat: number,
  options: PointerEventOptions = {},
) {
  const {
    target = new FakeElement("maplibregl-canvas"),
    touchCount = 1,
    button = 0,
    buttons = 0,
  } = options;
  return {
    point: { x, y },
    points: Array.from({ length: touchCount }, (_, index) => ({
      x: x + index,
      y: y + index,
    })),
    lngLat: { lng, lat },
    originalEvent: { target, button, buttons },
  };
}

function clickAt(
  map: FakeMap,
  down: "mousedown" | "touchstart",
  up: "mouseup" | "touchend",
  event: ReturnType<typeof pointerEvent>,
) {
  map.emit(down, event);
  map.emit(up, event);
}

describe("setupKompositionInteraction", () => {
  let map: FakeMap;
  let cleanup: () => void;
  let browserWindow: EventTarget;
  let browserDocument: FakeDocumentTarget;

  beforeEach(() => {
    vi.useFakeTimers();
    browserWindow = new EventTarget();
    browserDocument = Object.assign(new EventTarget(), {
      visibilityState: "visible" as const,
    });
    vi.stubGlobal("window", browserWindow);
    vi.stubGlobal("document", browserDocument);
    authStore.set({ authenticated: true, role: "gast" });
    leaveToNavigation();
    map = new FakeMap();
    cleanup = setupKompositionInteraction(map as never);
  });

  afterEach(() => {
    cleanup();
    leaveToNavigation();
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("sets the point on a plain click in place-garnrolle mode", () => {
    enterKomposition({ mode: "place-garnrolle", source: "tool-fan" });
    clickAt(map, "mousedown", "mouseup", pointerEvent(50, 50, 10, 53.5));
    const draft = get(kompositionDraft);
    expect(draft?.mode).toBe("place-garnrolle");
    expect(draft?.lngLat).toEqual([10, 53.5]);
    expect(draft?.source).toBe("map-tap");
  });

  it("sets the point on a plain tap in place-garnrolle mode", () => {
    enterKomposition({ mode: "place-garnrolle", source: "tool-fan" });
    clickAt(map, "touchstart", "touchend", pointerEvent(50, 50, 9.9, 53.4));
    expect(get(kompositionDraft)?.lngLat).toEqual([9.9, 53.4]);
    expect(get(kompositionDraft)?.source).toBe("map-tap");
  });

  it("accepts mouse placement again after compatibility suppression expires", () => {
    enterKomposition({ mode: "place-garnrolle", source: "tool-fan" });
    clickAt(map, "touchstart", "touchend", pointerEvent(50, 50, 9.9, 53.4));
    vi.advanceTimersByTime(501);
    clickAt(map, "mousedown", "mouseup", pointerEvent(50, 50, 10.1, 53.6));
    expect(get(kompositionDraft)?.lngLat).toEqual([10.1, 53.6]);
  });

  it("suppresses compatibility mouse events after a touch tap", () => {
    enterKomposition({ mode: "place-garnrolle", source: "tool-fan" });
    const setSpy = vi.fn();
    const unsub = kompositionDraft.subscribe((value) => {
      if (value?.lngLat) setSpy(value.lngLat);
    });

    clickAt(map, "touchstart", "touchend", pointerEvent(50, 50, 9.9, 53.4));
    clickAt(map, "mousedown", "mouseup", pointerEvent(50, 50, 10.1, 53.6));

    unsub();
    expect(setSpy).toHaveBeenCalledTimes(1);
    expect(get(kompositionDraft)?.lngLat).toEqual([9.9, 53.4]);
  });

  it("ignores a plain click outside place-garnrolle mode (navigation)", () => {
    clickAt(map, "mousedown", "mouseup", pointerEvent(50, 50, 10, 53.5));
    expect(get(kompositionDraft)).toBeNull();
  });

  it("does not open node composition on a plain click in new-knoten mode", () => {
    enterKomposition({ mode: "new-knoten", source: "tool-fan" });
    clickAt(map, "mousedown", "mouseup", pointerEvent(50, 50, 10, 53.5));
    // Still node composition, but no point placed by the click.
    expect(get(kompositionDraft)?.mode).toBe("new-knoten");
    expect(get(kompositionDraft)?.lngLat).toBeUndefined();
  });

  it("still supports the longpress path for node composition", () => {
    enterKomposition({ mode: "new-knoten", source: "tool-fan" });
    map.emit("mousedown", pointerEvent(50, 50, 10, 53.5));
    vi.advanceTimersByTime(800);
    map.emit("mouseup", pointerEvent(50, 50, 10, 53.5));
    const draft = get(kompositionDraft);
    expect(draft?.mode).toBe("new-knoten");
    expect(draft?.lngLat).toEqual([10, 53.5]);
    expect(draft?.source).toBe("map-longpress");
  });

  it("places only once for a longpress in place-garnrolle mode (no double trigger)", () => {
    enterKomposition({ mode: "place-garnrolle", source: "tool-fan" });
    const setSpy = vi.fn();
    const unsub = kompositionDraft.subscribe((value) => {
      if (value?.lngLat) setSpy(value.lngLat);
    });
    map.emit("mousedown", pointerEvent(50, 50, 10, 53.5));
    vi.advanceTimersByTime(800);
    map.emit("mouseup", pointerEvent(50, 50, 10, 53.5));
    unsub();
    // The longpress fires once; the trailing mouseup must not place again.
    expect(setSpy).toHaveBeenCalledTimes(1);
    expect(get(kompositionDraft)?.source).toBe("map-longpress");
  });

  it("does not move the point when the press starts on a marker", () => {
    enterKomposition({ mode: "place-garnrolle", source: "tool-fan" });
    const marker = new FakeElement("map-marker");
    clickAt(
      map,
      "mousedown",
      "mouseup",
      pointerEvent(50, 50, 10, 53.5, { target: marker }),
    );
    expect(get(kompositionDraft)?.lngLat).toBeUndefined();
  });

  it("does not arm placement or longpress on a native domain feature", () => {
    cleanup();
    cleanup = setupKompositionInteraction(
      map as never,
      (point) => point.x === 50 && point.y === 50,
    );
    enterKomposition({ mode: "place-garnrolle", source: "tool-fan" });

    map.emit("mousedown", pointerEvent(50, 50, 10, 53.5));
    vi.advanceTimersByTime(800);
    map.emit("mouseup", pointerEvent(50, 50, 10, 53.5));

    expect(get(kompositionDraft)?.lngLat).toBeUndefined();
  });

  it("does not move the point from nested SVG-like marker content", () => {
    enterKomposition({ mode: "place-garnrolle", source: "tool-fan" });
    const marker = new FakeElement("map-marker");
    const svg = new FakeElement("marker-icon-svg", marker);
    const path = new FakeElement("marker-icon-path", svg);
    clickAt(
      map,
      "mousedown",
      "mouseup",
      pointerEvent(50, 50, 10, 53.5, { target: path }),
    );
    expect(get(kompositionDraft)?.lngLat).toBeUndefined();
  });

  it("does not resurrect Garnrolle placement when composition is cancelled mid-press", () => {
    enterKomposition({ mode: "place-garnrolle", source: "tool-fan" });
    map.emit("mousedown", pointerEvent(50, 50, 10, 53.5));
    leaveToNavigation();
    map.emit("mouseup", pointerEvent(50, 50, 10, 53.5));
    expect(get(kompositionDraft)).toBeNull();
  });

  it("does not resurrect Garnrolle placement when the longpress timer fires after cancellation", () => {
    enterKomposition({ mode: "place-garnrolle", source: "tool-fan" });
    map.emit("mousedown", pointerEvent(50, 50, 10, 53.5));
    leaveToNavigation();
    vi.advanceTimersByTime(800);
    expect(get(kompositionDraft)).toBeNull();
  });

  it("does not let a stale longpress overwrite a changed composition mode", () => {
    enterKomposition({ mode: "place-garnrolle", source: "tool-fan" });
    map.emit("mousedown", pointerEvent(50, 50, 10, 53.5));
    enterKomposition({ mode: "new-knoten", source: "tool-fan" });
    vi.advanceTimersByTime(800);
    const draft = get(kompositionDraft);
    expect(draft?.mode).toBe("new-knoten");
    expect(draft?.lngLat).toBeUndefined();
  });

  it("does not let a stale longpress affect a re-entered Garnrolle composition", () => {
    enterKomposition({ mode: "place-garnrolle", source: "tool-fan" });
    map.emit("mousedown", pointerEvent(50, 50, 10, 53.5));
    leaveToNavigation();
    enterKomposition({ mode: "place-garnrolle", source: "tool-fan" });
    vi.advanceTimersByTime(800);
    const draft = get(kompositionDraft);
    expect(draft?.mode).toBe("place-garnrolle");
    expect(draft?.lngLat).toBeUndefined();
    expect(draft?.source).toBe("tool-fan");
  });

  it("does not complete a tap after same-mode ABA re-entry", () => {
    enterKomposition({ mode: "place-garnrolle", source: "tool-fan" });
    map.emit("mousedown", pointerEvent(50, 50, 10, 53.5));
    leaveToNavigation();
    enterKomposition({ mode: "place-garnrolle", source: "tool-fan" });
    map.emit("mouseup", pointerEvent(50, 50, 10, 53.5));
    const draft = get(kompositionDraft);
    expect(draft?.mode).toBe("place-garnrolle");
    expect(draft?.lngLat).toBeUndefined();
    expect(draft?.source).toBe("tool-fan");
  });

  it("does not complete a tap after authentication changes away and back", () => {
    enterKomposition({ mode: "place-garnrolle", source: "tool-fan" });
    map.emit("mousedown", pointerEvent(50, 50, 10, 53.5));
    authStore.set({ authenticated: false, role: "gast" });
    authStore.set({ authenticated: true, role: "gast" });
    map.emit("mouseup", pointerEvent(50, 50, 10, 53.5));
    expect(get(kompositionDraft)?.lngLat).toBeUndefined();
  });

  it("does not revive a navigation longpress after an ABA state transition", () => {
    map.emit("mousedown", pointerEvent(50, 50, 10, 53.5));
    enterKomposition({ mode: "place-garnrolle", source: "tool-fan" });
    leaveToNavigation();
    vi.advanceTimersByTime(800);
    expect(get(kompositionDraft)).toBeNull();
  });

  it("does not revive a gesture after authentication changes away and back", () => {
    enterKomposition({ mode: "place-garnrolle", source: "tool-fan" });
    map.emit("mousedown", pointerEvent(50, 50, 10, 53.5));
    authStore.set({ authenticated: false, role: "gast" });
    authStore.set({ authenticated: true, role: "gast" });
    vi.advanceTimersByTime(800);
    expect(get(kompositionDraft)?.lngLat).toBeUndefined();
  });

  it("ignores right and middle mouse buttons for placement", () => {
    enterKomposition({ mode: "place-garnrolle", source: "tool-fan" });
    clickAt(
      map,
      "mousedown",
      "mouseup",
      pointerEvent(50, 50, 10, 53.5, { button: 2 }),
    );
    clickAt(
      map,
      "mousedown",
      "mouseup",
      pointerEvent(50, 50, 10, 53.5, { button: 1 }),
    );
    expect(get(kompositionDraft)?.lngLat).toBeUndefined();
  });

  it("does not arm a longpress from a non-primary mouse button", () => {
    enterKomposition({ mode: "place-garnrolle", source: "tool-fan" });
    map.emit("mousedown", pointerEvent(50, 50, 10, 53.5, { button: 2 }));
    vi.advanceTimersByTime(800);
    expect(get(kompositionDraft)?.lngLat).toBeUndefined();
  });

  it("keeps a primary gesture armed when a non-primary mouseup reports primary held", () => {
    enterKomposition({ mode: "place-garnrolle", source: "tool-fan" });
    map.emit("mousedown", pointerEvent(50, 50, 10, 53.5));
    map.emit(
      "mouseup",
      pointerEvent(50, 50, 10, 53.5, { button: 2, buttons: 1 }),
    );
    expect(get(kompositionDraft)?.lngLat).toBeUndefined();
    map.emit("mouseup", pointerEvent(50, 50, 10, 53.5));
    expect(get(kompositionDraft)?.lngLat).toEqual([10, 53.5]);
  });

  it("cancels a primary gesture when a non-primary mouseup reports primary released", () => {
    enterKomposition({ mode: "place-garnrolle", source: "tool-fan" });
    map.emit("mousedown", pointerEvent(50, 50, 10, 53.5));
    map.emit(
      "mouseup",
      pointerEvent(50, 50, 10, 53.5, { button: 2, buttons: 0 }),
    );
    vi.advanceTimersByTime(800);
    map.emit("mouseup", pointerEvent(50, 50, 10, 53.5));
    expect(get(kompositionDraft)?.lngLat).toBeUndefined();
  });

  it("cancels an armed gesture when the window loses focus", () => {
    enterKomposition({ mode: "place-garnrolle", source: "tool-fan" });
    map.emit("mousedown", pointerEvent(50, 50, 10, 53.5));
    browserWindow.dispatchEvent(new Event("blur"));
    vi.advanceTimersByTime(800);
    map.emit("mouseup", pointerEvent(50, 50, 10, 53.5));
    expect(get(kompositionDraft)?.lngLat).toBeUndefined();
  });

  it("cancels an armed gesture when the document becomes hidden", () => {
    enterKomposition({ mode: "place-garnrolle", source: "tool-fan" });
    map.emit("mousedown", pointerEvent(50, 50, 10, 53.5));
    browserDocument.visibilityState = "hidden";
    browserDocument.dispatchEvent(new Event("visibilitychange"));
    vi.advanceTimersByTime(800);
    map.emit("mouseup", pointerEvent(50, 50, 10, 53.5));
    expect(get(kompositionDraft)?.lngLat).toBeUndefined();
  });

  it("keeps an armed gesture when the document remains visible", () => {
    enterKomposition({ mode: "place-garnrolle", source: "tool-fan" });
    map.emit("mousedown", pointerEvent(50, 50, 10, 53.5));
    browserDocument.dispatchEvent(new Event("visibilitychange"));
    map.emit("mouseup", pointerEvent(50, 50, 10, 53.5));
    expect(get(kompositionDraft)?.lngLat).toEqual([10, 53.5]);
  });

  it("does not place a point for a pan (movement beyond tolerance)", () => {
    enterKomposition({ mode: "place-garnrolle", source: "tool-fan" });
    map.emit("mousedown", pointerEvent(50, 50, 10, 53.5));
    map.emit("mousemove", pointerEvent(90, 90, 10.1, 53.6));
    map.emit("mouseup", pointerEvent(90, 90, 10.1, 53.6));
    expect(get(kompositionDraft)?.lngLat).toBeUndefined();
  });

  it("does not arm placement for a multi-touch gesture", () => {
    enterKomposition({ mode: "place-garnrolle", source: "tool-fan" });
    map.emit("touchstart", pointerEvent(50, 50, 10, 53.5, { touchCount: 2 }));
    map.emit("touchend", pointerEvent(50, 50, 10, 53.5));
    expect(get(kompositionDraft)?.lngLat).toBeUndefined();
  });

  it("ignores a click by an anonymous user", () => {
    authStore.set({ authenticated: false, role: "gast" });
    enterKomposition({ mode: "place-garnrolle", source: "tool-fan" });
    clickAt(map, "mousedown", "mouseup", pointerEvent(50, 50, 10, 53.5));
    expect(get(kompositionDraft)?.lngLat).toBeUndefined();
  });

  it("cancels an armed gesture when authentication disappears before release", () => {
    enterKomposition({ mode: "place-garnrolle", source: "tool-fan" });
    map.emit("mousedown", pointerEvent(50, 50, 10, 53.5));
    authStore.set({ authenticated: false, role: "gast" });
    map.emit("mouseup", pointerEvent(50, 50, 10, 53.5));
    expect(get(kompositionDraft)?.lngLat).toBeUndefined();
  });
});
