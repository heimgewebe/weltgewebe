/* Weltgewebe Web Push worker.
 * Push is only a privacy-safe hint. The canonical message is loaded after the
 * user opens /nachrichten; no message content is cached here.
 */

self.addEventListener("push", (event) => {
  let payload;
  try {
    payload = event.data?.json() ?? {};
  } catch {
    payload = {};
  }

  const title =
    typeof payload.title === "string" ? payload.title : "Weltgewebe";
  const body =
    typeof payload.body === "string"
      ? payload.body
      : "Neue Aktivität im Weltgewebe";
  const tag =
    typeof payload.tag === "string" ? payload.tag : "weltgewebe-activity";
  const requestedUrl =
    typeof payload.url === "string" ? payload.url : "/nachrichten";

  let targetUrl = new URL("/nachrichten", self.location.origin);
  try {
    const candidate = new URL(requestedUrl, self.location.origin);
    if (candidate.origin === self.location.origin) targetUrl = candidate;
  } catch {
    // Keep the safe same-origin fallback.
  }

  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      tag,
      renotify: true,
      icon: "/icon-192.png",
      badge: "/icon-192.png",
      data: { url: targetUrl.href },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const requestedUrl = event.notification.data?.url;
  let targetUrl = new URL("/nachrichten", self.location.origin);
  try {
    const candidate = new URL(requestedUrl, self.location.origin);
    if (candidate.origin === self.location.origin) targetUrl = candidate;
  } catch {
    // Keep the safe same-origin fallback.
  }

  event.waitUntil(
    self.clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then(async (clients) => {
        for (const client of clients) {
          if (new URL(client.url).origin !== self.location.origin) continue;
          if ("navigate" in client) await client.navigate(targetUrl.href);
          return client.focus();
        }
        return self.clients.openWindow(targetUrl.href);
      }),
  );
});
