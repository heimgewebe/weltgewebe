import { afterEach, describe, expect, it, vi } from "vitest";
import {
  applicationServerKey,
  deleteManagedPushSubscription,
  deletePushSubscription,
  listPushSubscriptions,
  registerPushSubscription,
  updateNotificationPreferences,
} from "./notifications";

afterEach(() => vi.unstubAllGlobals());

function stubPushHash(): void {
  const digest = new Uint8Array(32).fill(0xab).buffer;
  vi.stubGlobal("crypto", {
    subtle: {
      digest: vi.fn().mockResolvedValue(digest),
    },
  });
}

describe("notification API", () => {
  it("decodes an unpadded base64url VAPID key", () => {
    expect(Array.from(new Uint8Array(applicationServerKey("AQID-_8")))).toEqual(
      [1, 2, 3, 251, 255],
    );
  });

  it("updates the explicit account preference", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ direct_messages_push: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(updateNotificationPreferences(true)).resolves.toEqual({
      direct_messages_push: true,
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/notifications/preferences",
      expect.objectContaining({
        method: "PUT",
        credentials: "include",
        body: JSON.stringify({ direct_messages_push: true }),
      }),
    );
  });

  it("sends only the browser subscription contract", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: "subscription-a" }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const subscription = {
      toJSON: () => ({
        endpoint: "https://push.example.invalid/subscription-a",
        expirationTime: null,
        keys: { p256dh: "public-key", auth: "auth-secret" },
      }),
    } as unknown as PushSubscription;

    await registerPushSubscription(subscription);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/push/subscriptions",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          endpoint: "https://push.example.invalid/subscription-a",
          p256dh: "public-key",
          auth: "auth-secret",
        }),
      }),
    );
  });

  it("accepts an empty 204 response when the current device is removed", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      deletePushSubscription("https://push.example.invalid/subscription-a"),
    ).resolves.toBeUndefined();
  });

  it("lists managed subscriptions with only a one-way current-device marker", async () => {
    stubPushHash();
    const endpoint = "https://push.example.invalid/subscription-current";
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          items: [
            {
              id: "11111111-1111-4111-8111-111111111111",
              created_at: "2026-08-25T18:00:00Z",
              updated_at: "2026-08-25T18:30:00Z",
              current: true,
            },
          ],
          limit: 20,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(listPushSubscriptions(endpoint)).resolves.toMatchObject({
      limit: 20,
      items: [{ current: true }],
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/push/subscriptions",
      expect.objectContaining({
        credentials: "include",
        headers: {
          "X-Weltgewebe-Push-Endpoint-Hash": "ab".repeat(32),
        },
      }),
    );
    expect(JSON.stringify(fetchMock.mock.calls[0])).not.toContain(endpoint);
  });

  it("removes an old managed subscription by opaque id without sending its endpoint", async () => {
    stubPushHash();
    const currentEndpoint = "https://push.example.invalid/subscription-current";
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      deleteManagedPushSubscription(
        "22222222-2222-4222-8222-222222222222",
        currentEndpoint,
      ),
    ).resolves.toBeUndefined();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/push/subscriptions/22222222-2222-4222-8222-222222222222",
      expect.objectContaining({
        method: "DELETE",
        credentials: "include",
        headers: {
          "X-Weltgewebe-Push-Endpoint-Hash": "ab".repeat(32),
        },
      }),
    );
    expect(JSON.stringify(fetchMock.mock.calls[0])).not.toContain(
      currentEndpoint,
    );
  });

  it("refuses to guess the current device when Web Crypto is unavailable", async () => {
    vi.stubGlobal("crypto", undefined);
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      listPushSubscriptions(
        "https://push.example.invalid/subscription-current",
      ),
    ).rejects.toThrow("nicht sicher zugeordnet");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
