// Service worker для веб-версії (PWA): працює офлайн. «Спершу мережа, потім кеш».
// У нативному застосунку (Capacitor) усі файли й так лежать на пристрої.
const CACHE = 'lesefreund-v2';
const SHELL = ['./', 'index.html', 'css/style.css', 'icon.svg', 'manifest.webmanifest', 'books/index.json',
  'js/app.js', 'js/i18n.js', 'js/store.js', 'js/translate.js', 'js/promo.js', 'js/ui.js', 'js/library.js', 'js/reader.js',
  'js/learn.js', 'js/srs.js', 'js/stickers.js', 'js/theme.js', 'js/achievements.js', 'js/config.js', 'data/mini-dict.js'];
self.addEventListener('install', (e) => e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())));
self.addEventListener('activate', (e) => e.waitUntil(caches.keys()
  .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin) return;
  e.respondWith(fetch(e.request).then((res) => {
    const copy = res.clone();
    caches.open(CACHE).then((c) => c.put(e.request, copy));
    return res;
  }).catch(() => caches.match(e.request, { ignoreSearch: true })));
});
