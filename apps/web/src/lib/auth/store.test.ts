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

function guestResponse(status = 200): Response {
  return new Response(
    JSON.stringify({ authenticated: false, account_id: null, role: "gast" }),
    { status, headers: { "Content-Type": "application/json" } },
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

  it("clears identity after a validated guest payload", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(authResponse())
      .mockResolvedValueOnce(guestResponse());
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

  it("accepts a validated rolling-deployment 401 guest response", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(authResponse())
      .mockResolvedValueOnce(guestResponse(401));
    const store = createAuthStore({ isBrowser: true, fetcher });
    await store.checkAuth();
    await store.checkAuth();
    expect(get(store)).toMatchObject({
      state: "unauthenticated",
      authenticated: false,
    });
  });

  it("does not treat a naked 403 as proof of logout", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(authResponse("account-preserved"))
      .mockResolvedValueOnce(new Response(null, { status: 403 }));
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

  it("times out a stalled check into degraded state", async () => {
    const fetcher = vi.fn<typeof fetch>().mockImplementation((_input, init) => {
      return new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => {
          reject(new DOMException("aborted", "AbortError"));
        });
      });
    });
    const store = createAuthStore({
      isBrowser: true,
      fetcher,
      authCheckTimeoutMs: 5,
    });
    await expect(store.checkAuth()).resolves.toMatchObject({
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

  it("propagates logout failure and preserves identity as degraded", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(authResponse("account-preserved"))
      .mockResolvedValueOnce(new Response("unavailable", { status: 503 }));
    const store = createAuthStore({ isBrowser: true, fetcher });
    await store.checkAuth();
    await expect(store.logout()).rejects.toThrow("Logout failed: 503");
    expect(get(store)).toEqual({
      state: "degraded",
      authenticated: true,
      account_id: "account-preserved",
      role: "weber",
    });
  });

  it("requires server verification before completing logout", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(authResponse("account-preserved"))
      .mockResolvedValueOnce(new Response(null, { status: 200 }))
      .mockResolvedValueOnce(new Response("unavailable", { status: 503 }));
    const store = createAuthStore({ isBrowser: true, fetcher });
    await store.checkAuth();
    await expect(store.logout()).rejects.toThrow(
      "Logout could not be verified.",
    );
    expect(get(store)).toMatchObject({
      state: "degraded",
      authenticated: true,
      account_id: "account-preserved",
    });
  });

  it("completes logout only after a validated guest response", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(authResponse())
      .mockResolvedValueOnce(new Response(null, { status: 200 }))
      .mockResolvedValueOnce(guestResponse());
    const store = createAuthStore({ isBrowser: true, fetcher });
    await store.checkAuth();
    await expect(store.logout()).resolves.toBeUndefined();
    expect(get(store)).toMatchObject({
      state: "unauthenticated",
      authenticated: false,
    });
  });
});
