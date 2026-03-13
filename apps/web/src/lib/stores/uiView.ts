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

export function enterFokus(newSelection: Selection) {
  kompositionDraft.set(null);
  selection.set(newSelection);
  systemState.set("fokus");
}

export function enterKomposition(draft: KompositionDraft) {
  selection.set(null);
  kompositionDraft.set(draft);
  systemState.set("komposition");
}

export function leaveToNavigation() {
  selection.set(null);
  kompositionDraft.set(null);
  systemState.set("navigation");
}

if (import.meta.env.DEV || import.meta.env.MODE === "test") {
  derived(
    [systemState, selection, kompositionDraft, contextPanelOpen],
    ([$state, $sel, $draft, $open]) => ({ $state, $sel, $draft, $open }),
  ).subscribe(({ $state, $sel, $draft, $open }) => {
    queueMicrotask(() => {
      if ($state === "fokus" && !$sel) {
        console.error(
          "Invariant Violation: systemState is 'fokus' but selection is null",
        );
      }
      if ($state === "navigation" && $sel) {
        console.error(
          "Invariant Violation: systemState is 'navigation' but selection is not null",
        );
      }
      if ($state === "komposition" && !$draft) {
        console.error(
          "Invariant Violation: systemState is 'komposition' but kompositionDraft is null",
        );
      }
      if ($state !== "komposition" && $draft) {
        console.error(
          "Invariant Violation: systemState is not 'komposition' but kompositionDraft is not null",
        );
      }
      if ($state === "navigation" && $open) {
        console.error(
          "Invariant Violation: systemState is 'navigation' but contextPanelOpen is true",
        );
      }
    });
  });
}
