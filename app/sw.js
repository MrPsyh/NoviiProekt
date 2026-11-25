// Service worker: приложение работает офлайн. Стратегия «сначала сеть, потом кеш»,
// поэтому обновления (в т.ч. новый promo-pack.json) подхватываются сразу при наличии интернета.
const CACHE = 'lesefreund-v1';
const SHELL = [
  './', 'index.html', 'css/style.css', 'icon.svg', 'manifest.webmanifest', 'promo-pack.json',
  'js/app.js', 'js/i18n.js', 'js/store.js', 'js/translate.js', 'js/promo.js',
  'data/books.js', 'data/mini-dict.js',
];
self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin) return;
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
        return res;
      })
      .catch(() => caches.match(e.request, { ignoreSearch: true })),
  );
});
