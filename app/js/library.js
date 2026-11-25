// Каталог книжок: app/books/index.json (вбудовані книжки, працюють офлайн одразу)
// + app/books/remote.json (масовий імпорт з Gutenberg; текст завантажується під час першого відкриття
// з BOOKS_CDN_URL і зберігається на телефоні).
import { BOOKS_CDN_URL } from './config.js';
import * as store from './store.js';
import { loadCatalog, loadGutenbergBook } from './gutenberg.js';

let indexPromise;
const cache = new Map();
const getJson = (url) => fetch(url).then((r) => (r.ok ? r.json() : [])).catch(() => []);

// вбудовані книжки + великий каталог Gutenberg + книжки, які імпортував сам користувач
export function loadIndex() {
  indexPromise ||= Promise.all([getJson('books/index.json'), BOOKS_CDN_URL ? getJson('books/remote.json') : [], loadCatalog()])
    .then(([local, remote, catalog]) => {
      const seen = new Set(local.map((b) => b.id));
      const add = (list) => list.filter((b) => !seen.has(b.id) && seen.add(b.id));
      return [...local, ...add(store.get('imported') || []), ...add(remote), ...add(catalog)];
    });
  return indexPromise;
}
export function resetIndex() { indexPromise = null; }

async function loadRemote(id) {
  const url = `${BOOKS_CDN_URL.replace(/\/$/, '')}/${id}.json`;
  try {
    const c = await caches.open('lesefreund-books');
    const hit = await c.match(url);
    if (hit) return hit.json();
    const res = await fetch(url);
    if (!res.ok) throw new Error(res.status);
    await c.put(url, res.clone());
    return res.json();
  } catch {
    const res = await fetch(url);
    return res.json();
  }
}

export async function loadBook(id, onProgress) {
  if (!cache.has(id)) {
    const meta = (await loadIndex()).find((b) => b.id === id);
    cache.set(id, meta?.remote === 'gutenberg' ? loadGutenbergBook(id, meta.gutenberg, onProgress)
      : meta?.remote ? loadRemote(id) : fetch(`books/${id}.json`).then((r) => r.json()));
    cache.get(id).catch(() => cache.delete(id));
  }
  return cache.get(id);
}

export const COLLECTION_ORDER = ['kids', 'graded', 'school-de', 'school-ua', 'world', 'slavic', 'ukraine', 'japan', 'poetry', 'drama', 'philosophy'];
export const COLLECTION_ICON = {
  kids: '🧸', graded: '🌱', 'school-de': '🇩🇪', 'school-ua': '🎒', world: '🌍', slavic: '📜', ukraine: '🌻', japan: '🎌', poetry: '🪶', drama: '🎭', philosophy: '🦉',
};
export const LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1'];
export const readingMinutes = (words) => Math.max(1, Math.round(words / 130));
