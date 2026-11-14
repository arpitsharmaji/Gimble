// Network-first for the app shell so updates always arrive; cache is only an offline fallback.
const CACHE = "gimble-shell-v6";
const SHELL = ["/", "/index.html", "/styles.css", "/manifest.webmanifest", "/fonts/inter-latin-wght-normal.woff2", "/fonts/bricolage-grotesque-latin-wght-normal.woff2", "/fonts/instrument-serif-latin-400-italic.woff2", "/logo-sm.png", "/logo.png",
  "/js/app.js", "/js/core.js", "/js/auth.js", "/js/discover.js", "/js/account.js", "/js/admin.js", "/js/safety.js", "/js/legal.js", "/js/home.js", "/js/fx.js", "/js/deck.js", "/js/pages.js", "/js/wallet.js"];
self.addEventListener("install", e => { self.skipWaiting(); e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL).catch(() => {}))); });
self.addEventListener("activate", e => e.waitUntil((async () => {
  for (const k of await caches.keys()) if (k !== CACHE) await caches.delete(k);
  await self.clients.claim();
})()));
self.addEventListener("fetch", e => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin) return;
  // Never cache API responses, uploads or other private data.
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/uploads/")) return;
  e.respondWith((async () => {
    try {
      const res = await fetch(req);
      if (res.ok && SHELL.includes(url.pathname)) (await caches.open(CACHE)).put(req, res.clone());
      return res;
    } catch {
      return (await caches.match(req)) || (await caches.match("/index.html")) || Response.error();
    }
  })());
});
