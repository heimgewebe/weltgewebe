import { get } from "svelte/store";
import { describe, expect, it, vi } from "vitest";

vi.mock("$app/environment", () => ({ browser: false }));

import { createAuthStore } from "./store";

function authResponse(accountId = "account-a"): Response {
  return new Response(
    JSON.stringify({
      authenticated: true,
      account_id: accountId,
      role: "weber",
    }),
    { status: 200, headers: { "Content-Type": "application/json" } },
  );
}

describe("authStore", () => {
  it("deduplicates parallel auth checks", async () => {
    let resolveFetch!: (response: Response) => void;
    const fetcher = vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          resolveFetch = resolve;
        }),
    );
    const store = createAuthStore({ isBrowser: true, fetcher });

    const first = store.checkAuth();
    const second = store.checkAuth();
    await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));

    resolveFetch(authResponse());
    await expect(first).resolves.toMatchObject({
      state: "authenticated",
      authenticated: true,
    });
    await expect(second).resolves.toMatchObject({
      state: "authenticated",
      authenticated: true,
    });
  });

  it("preserves the authenticated identity when the server is unavailable", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(authResponse("account-preserved"))
      .mockResolvedValueOnce(new Response("unavailable", { status: 503 }));
    const store = createAuthStore({ isBrowser: true, fetcher });

    await store.checkAuth();
    await store.checkAuth();

    expect(get(store)).toEqual({
      state: "degraded",
      authenticated: true,
      account_id: "account-preserved",
      role: "weber",
    });
  });

  it("clears the identity only after an authoritative unauthenticated response", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(authResponse())
      .mockResolvedValueOnce(new Response(null, { status: 401 }));
    const store = createAuthStore({ isBrowser: true, fetcher });

    await store.checkAuth();
    await store.checkAuth();

    expect(get(store)).toEqual({
      state: "unauthenticated",
      authenticated: false,
      account_id: undefined,
      role: "gast",
    });
  });

  it("treats a non-authoritative guest payload as degraded", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ authenticated: false, role: "gast" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const store = createAuthStore({ isBrowser: true, fetcher });

    await store.checkAuth();

    expect(get(store)).toMatchObject({
      state: "degraded",
      authenticated: false,
    });
  });

  it("can cancel and replace an in-flight auth check without stale writes", async () => {
    let firstSignal: AbortSignal | undefined;
    const fetcher = vi
      .fn<typeof fetch>()
      .mockImplementationOnce((_input, init) => {
        firstSignal = init?.signal ?? undefined;
        return new Promise<Response>((_resolve, reject) => {
          firstSignal?.addEventListener("abort", () => {
            reject(new DOMException("aborted", "AbortError"));
          });
        });
      })
      .mockResolvedValueOnce(authResponse("latest-account"));
    const store = createAuthStore({ isBrowser: true, fetcher });

    const stale = store.checkAuth();
    await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
    const latest = store.checkAuth({ force: true });

    await expect(latest).resolves.toMatchObject({
      state: "authenticated",
      account_id: "latest-account",
    });
    await stale;
    expect(firstSignal?.aborted).toBe(true);
    expect(get(store)).toMatchObject({
      state: "authenticated",
      account_id: "latest-account",
    });
  });
});
