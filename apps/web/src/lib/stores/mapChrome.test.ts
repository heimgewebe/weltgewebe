import { beforeEach, describe, expect, it } from "vitest";
import { get } from "svelte/store";
import {
  TOOL_FAN_BRANCH,
  closeMapFans,
  mapChrome,
  showToolFanBranch,
  toggleGovernanceFan,
  toggleToolFan,
} from "./mapChrome";

describe("mapChrome", () => {
  beforeEach(() => closeMapFans());

  it("opens only one fan at a time", () => {
    toggleToolFan();
    expect(get(mapChrome)).toEqual({
      toolFanOpen: true,
      toolFanBranch: TOOL_FAN_BRANCH.root,
      governanceFanOpen: false,
    });

    toggleGovernanceFan();
    expect(get(mapChrome)).toEqual({
      toolFanOpen: false,
      toolFanBranch: TOOL_FAN_BRANCH.root,
      governanceFanOpen: true,
    });
  });

  it("resets the weaving branch whenever the tool fan closes", () => {
    showToolFanBranch(TOOL_FAN_BRANCH.weave);
    expect(get(mapChrome).toolFanBranch).toBe(TOOL_FAN_BRANCH.weave);

    toggleToolFan();
    expect(get(mapChrome)).toEqual({
      toolFanOpen: false,
      toolFanBranch: TOOL_FAN_BRANCH.root,
      governanceFanOpen: false,
    });
  });
});
