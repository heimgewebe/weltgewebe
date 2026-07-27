import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = readFileSync(
  new URL("./TopBar.svelte", import.meta.url),
  "utf-8",
);

describe("TopBar auth state contract", () => {
  it("distinguishes checking and degraded authentication visibly", () => {
    expect(source).toContain('$authStore.state === "authenticated"');
    expect(source).toContain('$authStore.state === "checking"');
    expect(source).toContain("Prüfe Anmeldung");
    expect(source).toContain("Verbindung gestört");
    expect(source).toContain("authStore.checkAuth({ force: true })");
  });
});
