import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";
import { activateToolFanAction } from "./fixtures/toolFan";

type ManifestRecord = {
  file?: string;
  name?: string;
};

function emittedFile(
  manifest: Record<string, ManifestRecord>,
  identity: { source: string; name: string },
) {
  const direct = manifest[identity.source]?.file;
  if (direct) return direct;

  const matches = Object.values(manifest).filter(
    (record) =>
      record.name === identity.name && typeof record.file === "string",
  );
  if (matches.length !== 1) {
    throw new Error(
      `expected one manifest entry for ${identity.source} (${identity.name}), found ${matches.length}`,
    );
  }
  return matches[0].file as string;
}

test("keeps interaction-only map chunks outside the startup request path", async ({
  page,
}) => {
  await mockApiResponses(page);
  const requested = new Set<string>();
  page.on("request", (request) => {
    requested.add(new URL(request.url()).pathname.replace(/^\//, ""));
  });

  await page.goto("/map");
  await page.waitForFunction(
    () => Boolean((window as any).__TEST_MAP__),
    null,
    {
      timeout: 15_000,
    },
  );
  const marker = page
    .locator('.map-marker[data-marker-category="node"]')
    .first();
  await expect(marker).toBeVisible();

  const manifest = JSON.parse(
    readFileSync(".svelte-kit/output/client/.vite/manifest.json", "utf8"),
  ) as Record<string, ManifestRecord>;
  const searchFile = emittedFile(manifest, {
    source: "src/lib/components/SearchOverlay.svelte",
    name: "SearchOverlay",
  });
  const contextFile = emittedFile(manifest, {
    source: "src/lib/components/ContextPanel.svelte",
    name: "ContextPanel",
  });

  expect(requested.has(searchFile)).toBe(false);
  expect(requested.has(contextFile)).toBe(false);

  await activateToolFanAction(page, "find");
  await expect(page.getByTestId("search-overlay")).toBeVisible();
  await expect.poll(() => requested.has(searchFile)).toBe(true);

  await page.keyboard.press("Escape");
  await marker.click();
  await expect(page.getByTestId("context-panel")).toBeVisible();
  await expect.poll(() => requested.has(contextFile)).toBe(true);
});
