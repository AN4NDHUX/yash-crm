// Yash CRM service worker: makes the app installable and keeps the app shell available.
// Data is never cached: /api requests always go to the server, so the app needs the server running.
const CACHE = "yash-crm-shell-v3";
// Do not prefetch the protected HTML shell during service-worker install. The
// first authenticated navigation stores it for offline use without creating a
// second Basic-auth challenge or caching a 401 response.
const SHELL = ["/static/css/app.css", "/static/js/app.js", "/favicon.svg", "/static/icons/icon-192.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()));
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
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/") || url.pathname === "/health") return;

  if (request.mode === "navigate") {
    // Every page is the same single-page shell; fall back to it when the server is unreachable.
    event.respondWith(
      fetch(request)
        .then((response) => { if (response.ok) { const copy = response.clone(); caches.open(CACHE).then((cache) => cache.put("/", copy)); } return response; })
        .catch(() => caches.match("/"))
    );
    return;
  }

  // Network first so updates are picked up immediately; cache is only the offline fallback.
  event.respondWith(
    fetch(request)
      .then((response) => { if (response.ok) { const copy = response.clone(); caches.open(CACHE).then((cache) => cache.put(request, copy)); } return response; })
      .catch(() => caches.match(request))
  );
});
