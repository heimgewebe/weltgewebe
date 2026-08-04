import { afterEach, describe, expect, it, vi } from "vitest";
import {
  applicationServerKey,
  deletePushSubscription,
  registerPushSubscription,
  updateNotificationPreferences,
} from "./notifications";

afterEach(() => vi.unstubAllGlobals());

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

  it("accepts an empty 204 response when a device is removed", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      deletePushSubscription("https://push.example.invalid/subscription-a"),
    ).resolves.toBeUndefined();
  });
});
