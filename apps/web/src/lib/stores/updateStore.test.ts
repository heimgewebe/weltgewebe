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
  afterEach(() => {
    updateStore.reset();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

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

  it("releases a stalled coalesced check after the timeout so later checks can retry", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn<typeof fetch>(
      (_input, init) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener(
            "abort",
            () => reject(new Error("aborted")),
            { once: true },
          );
        }),
    );
    vi.stubGlobal("fetch", fetcher);

    const first = updateStore.checkForUpdate();
    const second = updateStore.checkForUpdate();
    expect(fetcher).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(10_000);
    await Promise.all([first, second]);

    const retry = updateStore.checkForUpdate();
    expect(fetcher).toHaveBeenCalledTimes(2);

    await vi.advanceTimersByTimeAsync(10_000);
    await retry;
    expect(get(updateStore)).toBe(false);
  });
});
