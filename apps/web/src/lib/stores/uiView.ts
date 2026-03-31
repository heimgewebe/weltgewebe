import { writable } from "svelte/store";
import { setupUiInvariantWatcher } from "./uiInvariants";

export type ViewToggles = {
  showNodes: boolean;
  showEdges: boolean;
  showActivity: boolean;
  showGovernance: boolean;
  showSearch: boolean;
};

export const view = writable<ViewToggles>({
  showNodes: true,
  showEdges: true,
  showActivity: true,
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

setupUiInvariantWatcher(systemState, selection, kompositionDraft);
