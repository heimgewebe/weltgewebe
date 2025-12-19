import { writable } from 'svelte/store';

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
  showSearch: true
});

export type Selection = { type: 'node' | 'edge'; id: string; data?: any } | null;

export const selection = writable<Selection>(null);
export const viewPanelOpen = writable(false);
