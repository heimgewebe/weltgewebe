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
