/* Deliberately no task/API cache: signed-in data must never survive in shared caches. */
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) =>
  event.waitUntil(self.clients.claim()),
);
self.addEventListener("push", (event) => {
  let data = { title: "kjbk projekt guru", body: "Új értesítésed érkezett.", url: "/" };
  try {
    Object.assign(data, event.data.json());
  } catch (_) {}
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: "/static/icon-192.png",
      badge: "/static/icon-192.png",
      tag: data.tag || "kozos",
      data: { url: data.url },
    }),
  );
});
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const raw = event.notification.data?.url || "/";
  const url = new URL(raw, self.location.origin);
  if (url.origin !== self.location.origin) return;
  event.waitUntil(
    self.clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then(async (clients) => {
        for (const client of clients) {
          await client.navigate(url.href);
          return client.focus();
        }
        return self.clients.openWindow(url.href);
      }),
  );
});
