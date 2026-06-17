// Service worker minimo: instalavel + shell cacheado. Nunca cacheia /api.
const CACHE = "pronuncia-v1";
const SHELL = ["/", "/index.html", "/manifest.json", "/icon.svg"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  // API e nao-GET: sempre rede (nada de cache de dados/login)
  if (e.request.method !== "GET" || url.pathname.startsWith("/api")) return;
  // estatico: cache-first, com fallback de rede e do shell
  e.respondWith(
    caches.match(e.request).then((hit) =>
      hit || fetch(e.request).then((resp) => {
        const copy = resp.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
        return resp;
      }).catch(() => caches.match("/index.html"))
    )
  );
});
