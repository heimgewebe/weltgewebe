import { get } from "svelte/store";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("$app/environment", () => ({ browser: true, dev: false }));

import { updateStore } from "./updateStore";

function versionResponse(version: string): Response {
  return new Response(JSON.stringify({ version }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("updateStore", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("deduplicates concurrent checks and stops after detecting an update", async () => {
    let resolveFetch!: (response: Response) => void;
    const fetcher = vi.fn<typeof fetch>(
      () =>
        new Promise<Response>((resolve) => {
          resolveFetch = resolve;
        }),
    );
    vi.stubGlobal("fetch", fetcher);

    const first = updateStore.checkForUpdate();
    const second = updateStore.checkForUpdate();
    expect(fetcher).toHaveBeenCalledTimes(1);

    resolveFetch(versionResponse("different-version"));
    await Promise.all([first, second]);
    await updateStore.checkForUpdate();

    expect(get(updateStore)).toBe(true);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
