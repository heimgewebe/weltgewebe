import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { leaveToNavigation } = vi.hoisted(() => ({
  leaveToNavigation: vi.fn(),
}));
vi.mock("$lib/stores/uiView", () => ({ leaveToNavigation }));

import { setupFocusInteraction } from "./focus";

class FakeHTMLElement {
  constructor(public className = "") {}

  closest(selector: string) {
    if (
      selector === ".map-marker" &&
      /(^|\s)map-marker(\s|$)/.test(this.className)
    ) {
      return this;
    }
    return null;
  }
}

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

function clickEvent(target = new FakeHTMLElement("maplibregl-canvas")) {
  return {
    point: { x: 20, y: 30 },
    originalEvent: { target },
  };
}

describe("setupFocusInteraction", () => {
  beforeEach(() => {
    leaveToNavigation.mockReset();
    vi.stubGlobal("HTMLElement", FakeHTMLElement);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("does not leave focus when the click hits a native domain feature", () => {
    const map = new FakeMap();
    const hitTest = vi.fn(() => true);
    const cleanup = setupFocusInteraction(map as never, () => "fokus", hitTest);

    map.emit("click", clickEvent());

    expect(hitTest).toHaveBeenCalledWith({ x: 20, y: 30 });
    expect(leaveToNavigation).not.toHaveBeenCalled();
    cleanup();
  });

  it("still leaves focus on a genuinely empty map click", () => {
    const map = new FakeMap();
    const cleanup = setupFocusInteraction(
      map as never,
      () => "fokus",
      () => false,
    );

    map.emit("click", clickEvent());

    expect(leaveToNavigation).toHaveBeenCalledTimes(1);
    cleanup();
  });

  it("keeps the existing DOM-marker click boundary", () => {
    const map = new FakeMap();
    const cleanup = setupFocusInteraction(
      map as never,
      () => "fokus",
      () => false,
    );

    map.emit("click", clickEvent(new FakeHTMLElement("map-marker")));

    expect(leaveToNavigation).not.toHaveBeenCalled();
    cleanup();
  });

  it("does not alter navigation state on an empty click outside focus", () => {
    const map = new FakeMap();
    const cleanup = setupFocusInteraction(
      map as never,
      () => "navigation",
      () => false,
    );

    map.emit("click", clickEvent());

    expect(leaveToNavigation).not.toHaveBeenCalled();
    cleanup();
  });
});
