import type { Page } from "@playwright/test";

export type ToolFanAction = "find" | "content" | "weave";

export async function activateToolFanAction(
  page: Page,
  action: ToolFanAction,
): Promise<void> {
  await page.getByTestId("tool-fan-trigger").click();
  await page.getByTestId(`tool-fan-${action}`).click();
}
