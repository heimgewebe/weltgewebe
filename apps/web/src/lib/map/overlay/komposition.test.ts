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

// The overlay classifies event targets with `instanceof HTMLElement` +
// `closest(".map-marker")`. The suite runs under the "node" environment (no
// DOM), so a minimal element stand-in provides both.
class FakeElement {
  className: string;
  constructor(className = "") {
    this.className = className;
  }
  closest(selector: string): FakeElement | null {
    return selector === ".map-marker" &&
      /(^|\s)map-marker(\s|$)/.test(this.className)
      ? this
      : null;
  }
}
(globalThis as { HTMLElement?: unknown }).HTMLElement = FakeElement;

type Handler = (event: unknown) => void;

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

function pointerEvent(
  x: number,
  y: number,
  lng: number,
  lat: number,
  target: unknown = new FakeElement("maplibregl-canvas"),
) {
  return {
    point: { x, y },
    lngLat: { lng, lat },
    originalEvent: { target },
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

  beforeEach(() => {
    vi.useFakeTimers();
    authStore.set({ authenticated: true, role: "gast" });
    leaveToNavigation();
    map = new FakeMap();
    cleanup = setupKompositionInteraction(map as never);
  });

  afterEach(() => {
    cleanup();
    leaveToNavigation();
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
      pointerEvent(50, 50, 10, 53.5, marker),
    );
    expect(get(kompositionDraft)?.lngLat).toBeUndefined();
  });

  it("does not place a point for a pan (movement beyond tolerance)", () => {
    enterKomposition({ mode: "place-garnrolle", source: "tool-fan" });
    map.emit("mousedown", pointerEvent(50, 50, 10, 53.5));
    map.emit("mousemove", pointerEvent(90, 90, 10.1, 53.6));
    map.emit("mouseup", pointerEvent(90, 90, 10.1, 53.6));
    expect(get(kompositionDraft)?.lngLat).toBeUndefined();
  });

  it("ignores a click by an anonymous user", () => {
    authStore.set({ authenticated: false, role: "gast" });
    enterKomposition({ mode: "place-garnrolle", source: "tool-fan" });
    clickAt(map, "mousedown", "mouseup", pointerEvent(50, 50, 10, 53.5));
    expect(get(kompositionDraft)?.lngLat).toBeUndefined();
  });
});
