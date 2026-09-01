import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = readFileSync(
  new URL("./TopBar.svelte", import.meta.url),
  "utf8",
);

describe("TopBar accessibility contract", () => {
  it("exposes navigation semantics instead of an incomplete ARIA toolbar", () => {
    expect(source).toContain("<nav");
    expect(source).toContain('aria-label="Navigation"');
    expect(source).toContain("</nav>");
    expect(source).not.toContain('role="toolbar"');
  });
});
