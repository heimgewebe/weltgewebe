import { writable } from "svelte/store";

export type ViewToggles = {
  showNodes: boolean;
  showEdges: boolean;
  showGovernance: boolean;
  showSearch: boolean;
};

export const view = writable<ViewToggles>({
  showNodes: true,
  showEdges: true,
  showGovernance: true,
  showSearch: true,
});

export type Selection = {
  type: "node" | "edge" | "account" | "garnrolle";
  id: string;
  data?: any;
} | null;

export const selection = writable<Selection>(null);

import { derived } from "svelte/store";

export type SystemState = "navigation" | "fokus" | "komposition";
export const systemState = writable<SystemState>("navigation");

export const contextPanelOpen = derived(
  systemState,
  ($state) => $state !== "navigation",
);

export type KompositionDraft = {
  mode: "new-knoten";
  lngLat?: [number, number];
  source: "map-longpress" | "action-bar";
} | null;

export const kompositionDraft = writable<KompositionDraft>(null);

export function enterFokus(newSelection: NonNullable<Selection>) {
  kompositionDraft.set(null);
  selection.set(newSelection);
  systemState.set("fokus");
}

export function enterKomposition(draft: NonNullable<KompositionDraft>) {
  selection.set(null);
  kompositionDraft.set(draft);
  systemState.set("komposition");
}

export function leaveToNavigation() {
  selection.set(null);
  kompositionDraft.set(null);
  systemState.set("navigation");
}

export function assertUiStateInvariant(
  state: SystemState,
  sel: Selection,
  draft: KompositionDraft,
) {
  if (sel !== null && draft !== null) {
    throw new Error(
      "Invariant Violation: selection and kompositionDraft cannot both be set at the same time",
    );
  }
  if (state === "fokus" && !sel) {
    throw new Error(
      "Invariant Violation: systemState is 'fokus' but selection is null",
    );
  }
  if (state === "navigation" && sel) {
    throw new Error(
      "Invariant Violation: systemState is 'navigation' but selection is not null",
    );
  }
  if (state === "komposition" && !draft) {
    throw new Error(
      "Invariant Violation: systemState is 'komposition' but kompositionDraft is null",
    );
  }
  if (state !== "komposition" && draft) {
    throw new Error(
      "Invariant Violation: systemState is not 'komposition' but kompositionDraft is not null",
    );
  }
}

// Fallback for environments where import.meta.env is not available
const isDevOrTest =
  (typeof import.meta !== "undefined" &&
    import.meta.env &&
    (import.meta.env.DEV || import.meta.env.MODE === "test")) ||
  (typeof process !== "undefined" && process.env.NODE_ENV === "test");

if (isDevOrTest) {
  let latestSnapshot: {
    $state: SystemState;
    $sel: Selection;
    $draft: KompositionDraft;
  } | null = null;
  let isValidationQueued = false;

  derived(
    [systemState, selection, kompositionDraft],
    ([$state, $sel, $draft]) => ({ $state, $sel, $draft }),
  ).subscribe((snapshot) => {
    latestSnapshot = snapshot;

    if (!isValidationQueued) {
      isValidationQueued = true;
      queueMicrotask(() => {
        isValidationQueued = false;
        if (!latestSnapshot) return;

        const { $state, $sel, $draft } = latestSnapshot;

        assertUiStateInvariant($state, $sel, $draft);
      });
    }
  });
}
