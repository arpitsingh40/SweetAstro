/* SweetAstro service worker: offline app shell + cache-first static assets.
   API calls always go to the network. Registered from /app/sw.js with scope "/". */
const CACHE = "sweetastro-app-v1";
const SHELL = ["/app", "/static/app/manifest.webmanifest", "/static/app/icon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return; // live data only

  // Navigations: network first, fall back to the cached shell (deep links work offline).
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() => caches.match("/app"))
    );
    return;
  }

  // App assets + fonts: cache first, refresh in background.
  if (url.pathname.startsWith("/static/app/")) {
    event.respondWith(
      caches.match(request).then((cached) => {
        const network = fetch(request).then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE).then((cache) => cache.put(request, copy));
          }
          return response;
        }).catch(() => cached);
        return cached || network;
      })
    );
  }
});

// Substance-only notifications: dasha boundaries. Delivery needs VAPID keys
// configured server-side; this handler only renders and routes them.
self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = {};
  }
  const title = data.title || "SweetAstro";
  event.waitUntil(
    self.registration.showNotification(title, {
      body: data.body || "",
      icon: "/static/app/icon.svg",
      badge: "/static/app/icon.svg",
      data: { url: data.url || "/app/today" },
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || "/app/today";
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      for (const client of list) {
        if ("focus" in client) return client.focus();
      }
      return clients.openWindow(target);
    })
  );
});
