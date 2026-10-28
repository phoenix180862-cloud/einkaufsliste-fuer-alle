// Einkaufsliste – Service Worker: App-Hülle für schnellen Start und Offline-Betrieb.
// Bei JEDER Änderung an der App die Versionsnummer erhöhen (gleich wie VERSION in app.js).
// Strategie „Netz zuerst“: ist das Gerät online, kommt immer der neueste Stand; der Cache ist nur Rückfall.
const VERSION = "1.2.0";
const CACHE = "ekl-" + VERSION;
const PRAEFIX = "ekl-";            // nur eigene Caches anfassen – andere Apps derselben Adresse bleiben unberührt
const HUELLE = [
  "./", "index.html", "app.css", "app.js", "texte.js", "manifest.webmanifest",
  "katalog/aufbau.js", "katalog/de.js", "katalog/en.js", "katalog/cs.js", "katalog/sk.js", "katalog/uk.js", "katalog/pl.js",
  "img/logo-auf-hell.webp", "img/logo-auf-dunkel.webp",
  "icons/favicon.svg", "icons/favicon-32.png", "icons/icon-192.png", "icons/icon-512.png", "icons/apple-touch-icon.png",
  "fonts/archivo-latin-400-normal.woff2", "fonts/archivo-latin-600-normal.woff2", "fonts/archivo-latin-700-normal.woff2",
  "fonts/archivo-latin-ext-400-normal.woff2", "fonts/archivo-latin-ext-600-normal.woff2", "fonts/archivo-latin-ext-700-normal.woff2",
  "fonts/archivo-narrow-latin-500-normal.woff2", "fonts/archivo-narrow-latin-600-normal.woff2", "fonts/archivo-narrow-latin-700-normal.woff2",
  "fonts/archivo-narrow-latin-ext-500-normal.woff2", "fonts/archivo-narrow-latin-ext-600-normal.woff2", "fonts/archivo-narrow-latin-ext-700-normal.woff2",
  "fonts/fira-sans-cyrillic-400-normal.woff2", "fonts/fira-sans-cyrillic-600-normal.woff2", "fonts/fira-sans-cyrillic-700-normal.woff2",
  "fonts/fira-sans-condensed-cyrillic-500-normal.woff2", "fonts/fira-sans-condensed-cyrillic-600-normal.woff2", "fonts/fira-sans-condensed-cyrillic-700-normal.woff2"
];

self.addEventListener("install", ev => {
  ev.waitUntil(caches.open(CACHE).then(c => c.addAll(HUELLE.map(u => new Request(u, { cache: "reload" })))).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener("activate", ev => {
  ev.waitUntil((async () => {
    const namen = await caches.keys();
    await Promise.all(namen.filter(n => n.startsWith(PRAEFIX) && n !== CACHE).map(n => caches.delete(n)));
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", ev => {
  const req = ev.request, url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin) return;
  // Hilfe-Videos (Teilabrufe) nicht über den Cache leiten
  if (req.headers.has("range") || url.pathname.includes("/hilfe/videos/")) return;
  ev.respondWith((async () => {
    try {
      const antwort = await fetch(req, { cache: "no-cache" });
      if (antwort && antwort.ok && antwort.status === 200) {
        const kopie = antwort.clone();
        caches.open(CACHE).then(c => c.put(req, kopie)).catch(() => {});
      }
      return antwort;
    } catch (e) {
      const treffer = await caches.match(req, { ignoreSearch: true });
      if (treffer) return treffer;
      if (req.mode === "navigate") { const start = await caches.match("index.html"); if (start) return start; }
      throw e;
    }
  })());
});
