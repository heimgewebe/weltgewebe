import { writable } from "svelte/store";

export const TOOL_FAN_BRANCH = {
  root: "root",
  weave: "weave",
} as const;

export type ToolFanBranch =
  (typeof TOOL_FAN_BRANCH)[keyof typeof TOOL_FAN_BRANCH];

export interface MapChromeState {
  toolFanOpen: boolean;
  toolFanBranch: ToolFanBranch;
  attentionOverflowOpen: boolean;
  attentionCardOpen: boolean;
}

const initialState: MapChromeState = {
  toolFanOpen: false,
  toolFanBranch: TOOL_FAN_BRANCH.root,
  attentionOverflowOpen: false,
  attentionCardOpen: false,
};

export const mapChrome = writable<MapChromeState>(initialState);

export function toggleToolFan(): void {
  mapChrome.update((state) => ({
    ...state,
    toolFanOpen: !state.toolFanOpen,
    toolFanBranch: TOOL_FAN_BRANCH.root,
  }));
}

export function closeToolFan(): void {
  mapChrome.update((state) => ({
    ...state,
    toolFanOpen: false,
    toolFanBranch: TOOL_FAN_BRANCH.root,
  }));
}

export function showToolFanBranch(branch: ToolFanBranch): void {
  mapChrome.update((state) => ({
    ...state,
    toolFanOpen: true,
    toolFanBranch: branch,
  }));
}

export function setAttentionOverflowOpen(open: boolean): void {
  mapChrome.update((state) =>
    state.attentionOverflowOpen === open
      ? state
      : { ...state, attentionOverflowOpen: open },
  );
}

export function setAttentionCardOpen(open: boolean): void {
  mapChrome.update((state) =>
    state.attentionCardOpen === open
      ? state
      : { ...state, attentionCardOpen: open },
  );
}

export function closeMapFans(): void {
  mapChrome.set(initialState);
}
