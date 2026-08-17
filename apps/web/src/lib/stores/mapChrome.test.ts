import { beforeEach, describe, expect, it } from "vitest";
import { get } from "svelte/store";
import {
  TOOL_FAN_BRANCH,
  closeMapFans,
  mapChrome,
  setAttentionCardOpen,
  setAttentionOverflowOpen,
  showToolFanBranch,
  toggleToolFan,
} from "./mapChrome";

describe("mapChrome", () => {
  beforeEach(() => closeMapFans());

  it("toggles the tool fan without a second governance fan state", () => {
    toggleToolFan();
    expect(get(mapChrome)).toEqual({
      toolFanOpen: true,
      toolFanBranch: TOOL_FAN_BRANCH.root,
      attentionOverflowOpen: false,
      attentionCardOpen: false,
    });

    toggleToolFan();
    expect(get(mapChrome)).toEqual({
      toolFanOpen: false,
      toolFanBranch: TOOL_FAN_BRANCH.root,
      attentionOverflowOpen: false,
      attentionCardOpen: false,
    });
  });

  it("tracks attention surfaces independently from the tool fan", () => {
    setAttentionOverflowOpen(true);
    toggleToolFan();
    expect(get(mapChrome)).toEqual({
      toolFanOpen: true,
      toolFanBranch: TOOL_FAN_BRANCH.root,
      attentionOverflowOpen: true,
      attentionCardOpen: false,
    });

    setAttentionCardOpen(true);
    expect(get(mapChrome).attentionCardOpen).toBe(true);

    closeMapFans();
    expect(get(mapChrome).attentionOverflowOpen).toBe(false);
    expect(get(mapChrome).attentionCardOpen).toBe(false);
  });

  it("resets the weaving branch whenever the tool fan closes", () => {
    showToolFanBranch(TOOL_FAN_BRANCH.weave);
    expect(get(mapChrome).toolFanBranch).toBe(TOOL_FAN_BRANCH.weave);

    toggleToolFan();
    expect(get(mapChrome)).toEqual({
      toolFanOpen: false,
      toolFanBranch: TOOL_FAN_BRANCH.root,
      attentionOverflowOpen: false,
      attentionCardOpen: false,
    });
  });
});
