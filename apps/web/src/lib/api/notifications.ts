export interface NotificationPreferences {
  direct_messages_push: boolean;
}

export interface PushConfig {
  enabled: boolean;
  application_server_key: string | null;
}

export interface StoredPushSubscription {
  id: string;
}

export interface ManagedPushSubscription {
  id: string;
  created_at: string;
  updated_at: string;
  current: boolean;
}

export interface PushSubscriptionsView {
  items: ManagedPushSubscription[];
  limit: number;
}

interface ErrorPayload {
  code?: unknown;
  message?: unknown;
}

const PUSH_ENDPOINT_HASH_HEADER = "X-Weltgewebe-Push-Endpoint-Hash";

export class NotificationsApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "NotificationsApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: "include",
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as ErrorPayload;
    throw new NotificationsApiError(
      response.status,
      typeof payload.code === "string" ? payload.code : "request_failed",
      typeof payload.message === "string"
        ? payload.message
        : `HTTP ${response.status}`,
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

async function currentPushHeaders(
  endpoint?: string | null,
): Promise<Record<string, string>> {
  if (!endpoint) return {};
  if (!globalThis.crypto?.subtle) {
    throw new Error(
      "Der aktuelle Push-Browser kann nicht sicher zugeordnet werden.",
    );
  }
  const digest = await globalThis.crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(endpoint),
  );
  const hash = Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
  return { [PUSH_ENDPOINT_HASH_HEADER]: hash };
}

export function getNotificationPreferences(
  signal?: AbortSignal,
): Promise<NotificationPreferences> {
  return request<NotificationPreferences>("/api/notifications/preferences", {
    signal,
  });
}

export function updateNotificationPreferences(
  directMessagesPush: boolean,
): Promise<NotificationPreferences> {
  return request<NotificationPreferences>("/api/notifications/preferences", {
    method: "PUT",
    body: JSON.stringify({ direct_messages_push: directMessagesPush }),
  });
}

export function getPushConfig(signal?: AbortSignal): Promise<PushConfig> {
  return request<PushConfig>("/api/push/config", { signal });
}

export async function listPushSubscriptions(
  currentEndpoint?: string | null,
  signal?: AbortSignal,
): Promise<PushSubscriptionsView> {
  return request<PushSubscriptionsView>("/api/push/subscriptions", {
    signal,
    headers: await currentPushHeaders(currentEndpoint),
  });
}

export function registerPushSubscription(
  subscription: PushSubscription,
): Promise<StoredPushSubscription> {
  const value = subscription.toJSON();
  const endpoint = value.endpoint;
  const p256dh = value.keys?.p256dh;
  const auth = value.keys?.auth;
  if (!endpoint || !p256dh || !auth) {
    throw new Error(
      "Der Browser hat eine unvollständige Push-Freigabe geliefert.",
    );
  }
  return request<StoredPushSubscription>("/api/push/subscriptions", {
    method: "POST",
    body: JSON.stringify({ endpoint, p256dh, auth }),
  });
}

export function deletePushSubscription(endpoint: string): Promise<void> {
  return request<void>("/api/push/subscriptions", {
    method: "DELETE",
    body: JSON.stringify({ endpoint }),
  });
}

export async function deleteManagedPushSubscription(
  id: string,
  currentEndpoint?: string | null,
): Promise<void> {
  return request<void>(`/api/push/subscriptions/${encodeURIComponent(id)}`, {
    method: "DELETE",
    headers: await currentPushHeaders(currentEndpoint),
  });
}

/** Convert the VAPID public key into the BufferSource expected by PushManager. */
export function applicationServerKey(value: string): ArrayBuffer {
  const padding = "=".repeat((4 - (value.length % 4)) % 4);
  const base64 = (value + padding).replace(/-/g, "+").replace(/_/g, "/");
  const decoded = atob(base64);
  const bytes = new Uint8Array(decoded.length);
  for (let index = 0; index < decoded.length; index += 1) {
    bytes[index] = decoded.charCodeAt(index);
  }
  return bytes.buffer;
}
