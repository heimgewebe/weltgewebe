import { test, expect } from "@playwright/test";
import {
  systemState,
  selection,
  kompositionDraft,
  enterFokus,
  enterKomposition,
  leaveToNavigation,
  contextPanelOpen,
} from "../src/lib/stores/uiView";
import { assertUiStateInvariant } from "../src/lib/stores/uiInvariants";
import { get } from "svelte/store";

test.describe("uiView store state transitions", () => {
  test.beforeEach(() => {
    // Reset state before each test
    leaveToNavigation();
  });

  test("enterFokus sets selection !== null and kompositionDraft === null", () => {
    enterFokus({ type: "node", id: "1" });
    expect(get(systemState)).toBe("fokus");
    expect(get(selection)).not.toBeNull();
    expect(get(selection)).toEqual({ type: "node", id: "1" });
    expect(get(kompositionDraft)).toBeNull();
    expect(get(contextPanelOpen)).toBe(true);
  });

  test("enterKomposition sets selection === null and kompositionDraft !== null", () => {
    enterKomposition({ mode: "new-knoten", source: "action-bar" });
    expect(get(systemState)).toBe("komposition");
    expect(get(selection)).toBeNull();
    expect(get(kompositionDraft)).not.toBeNull();
    expect(get(kompositionDraft)).toEqual({
      mode: "new-knoten",
      source: "action-bar",
    });
    expect(get(contextPanelOpen)).toBe(true);
  });

  test("leaveToNavigation sets selection === null and kompositionDraft === null", () => {
    enterFokus({ type: "node", id: "1" });
    leaveToNavigation();
    expect(get(systemState)).toBe("navigation");
    expect(get(selection)).toBeNull();
    expect(get(kompositionDraft)).toBeNull();
    expect(get(contextPanelOpen)).toBe(false);
  });

  test("assertUiStateInvariant throws on invalid states", () => {
    // Both set
    expect(() =>
      assertUiStateInvariant(
        "navigation",
        { type: "node", id: "1" },
        { mode: "new-knoten", source: "action-bar" },
      ),
    ).toThrow(/cannot both be set at the same time/);

    // fokus but no selection
    expect(() => assertUiStateInvariant("fokus", null, null)).toThrow(
      /systemState is 'fokus' but selection is null/,
    );

    // navigation but selection set
    expect(() =>
      assertUiStateInvariant("navigation", { type: "node", id: "1" }, null),
    ).toThrow(/systemState is 'navigation' but selection is not null/);

    // komposition but no draft
    expect(() => assertUiStateInvariant("komposition", null, null)).toThrow(
      /systemState is 'komposition' but kompositionDraft is null/,
    );

    // not komposition but draft set
    expect(() =>
      assertUiStateInvariant("navigation", null, {
        mode: "new-knoten",
        source: "action-bar",
      }),
    ).toThrow(
      /systemState is not 'komposition' but kompositionDraft is not null/,
    );
  });
});
