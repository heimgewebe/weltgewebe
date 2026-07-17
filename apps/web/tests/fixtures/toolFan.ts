import type { Page } from "@playwright/test";

export const TOOL_FAN_TEST_ID = {
  find: "tool-fan-find",
  sight: "tool-fan-map-content",
  weave: "tool-fan-weave",
  createNode: "tool-fan-create-node",
  createProposal: "tool-fan-create-proposal",
} as const;

export type ToolFanAction = "find" | "sight" | "weave";

export async function activateToolFanAction(
  page: Page,
  action: ToolFanAction,
): Promise<void> {
  await page.getByTestId("tool-fan-trigger").click();
  await page.getByTestId(TOOL_FAN_TEST_ID[action]).click();
  if (action === "weave") {
    await page.getByTestId(TOOL_FAN_TEST_ID.createNode).click();
  }
}
