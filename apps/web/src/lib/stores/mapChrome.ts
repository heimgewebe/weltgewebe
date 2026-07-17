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
  governanceFanOpen: boolean;
}

const initialState: MapChromeState = {
  toolFanOpen: false,
  toolFanBranch: TOOL_FAN_BRANCH.root,
  governanceFanOpen: false,
};

export const mapChrome = writable<MapChromeState>(initialState);

export function toggleToolFan(): void {
  mapChrome.update((state) => ({
    toolFanOpen: !state.toolFanOpen,
    toolFanBranch: TOOL_FAN_BRANCH.root,
    governanceFanOpen: false,
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
    governanceFanOpen: false,
  }));
}

export function toggleGovernanceFan(): void {
  mapChrome.update((state) => ({
    toolFanOpen: false,
    toolFanBranch: TOOL_FAN_BRANCH.root,
    governanceFanOpen: !state.governanceFanOpen,
  }));
}

export function closeGovernanceFan(): void {
  mapChrome.update((state) => ({
    ...state,
    governanceFanOpen: false,
  }));
}

export function closeMapFans(): void {
  mapChrome.set(initialState);
}
