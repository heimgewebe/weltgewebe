import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { createAccountRequestGuard } from "./accountRequestGuard";

describe("Garnrolle account request guard", () => {
  it("rejects an older response after the active account changes", () => {
    const guard = createAccountRequestGuard();
    const accountA = guard.begin("account-a");
    const accountB = guard.begin("account-b");

    expect(guard.isCurrent(accountA, "account-b")).toBe(false);
    expect(guard.isCurrent(accountB, "account-b")).toBe(true);
  });

  it("rejects an in-flight response after logout", () => {
    const guard = createAccountRequestGuard();
    const request = guard.begin("account-a");

    guard.invalidate();

    expect(guard.isCurrent(request, null)).toBe(false);
  });

  it("invalidates account-bound operations when the component is destroyed", () => {
    const component = readFileSync(
      new URL("../components/MyGarnrolleSection.svelte", import.meta.url),
      "utf8",
    );

    expect(component).toContain('import { onDestroy, tick } from "svelte";');
    expect(component).toContain("onDestroy(invalidateAccountOperations);");
  });
});
