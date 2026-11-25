// Книжки з Project Gutenberg прямо в застосунку: великий каталог (books/catalog.json, ~1500 німецьких книжок),
// завантаження тексту з офіційного дзеркала за запитом, розбір на розділи і збереження на телефоні (IndexedDB),
// пошук і імпорт будь-якої книжки через Gutendex.
const MIRRORS = ['https://aleph.pglaf.org', 'https://gutenberg.pglaf.org'];
const WC = /[\p{L}\p{N}]+/gu;
const wc = (s) => (s.match(WC) || []).length;

// ---------- сховище завантажених книжок ----------
let dbp;
function db() {
  dbp ||= new Promise((res, rej) => {
    const r = indexedDB.open('lesefreund-books', 1);
    r.onupgradeneeded = () => r.result.createObjectStore('books');
    r.onsuccess = () => res(r.result);
    r.onerror = () => rej(r.error);
  });
  return dbp;
}
async function idb(mode, fn) {
  const d = await db();
  return new Promise((res, rej) => {
    const tx = d.transaction('books', mode);
    const req = fn(tx.objectStore('books'));
    tx.oncomplete = () => res(req?.result);
    tx.onerror = () => rej(tx.error);
  });
}
export const getSaved = (id) => idb('readonly', (s) => s.get(id)).catch(() => null);
export const saveBook = (id, book) => idb('readwrite', (s) => s.put(book, id)).catch(() => null);

// ---------- розбір тексту Gutenberg ----------
const JUNK = /^(\+[-=]{5,}|\|\s|Anmerkungen? zur Transkription|Anmerkung des Transkribenten|Transcriber|Produced by|E-text prepared|Inhalt(sverzeichnis)?\.?$|\[Illustration)/i;
export function parseGutenberg(txt) {
  const start = txt.search(/\*\*\*\s*START OF (THE|THIS) PROJECT GUTENBERG/i);
  const end = txt.search(/\*\*\*\s*END OF (THE|THIS) PROJECT GUTENBERG/i);
  let body = txt.slice(start >= 0 ? txt.indexOf('\n', start) + 1 : 0, end > 0 ? end : undefined).replace(/\r/g, '');
  body = body.replace(/_([^_\n]+)_/g, '$1').replace(/~([^~\n]+)~/g, '$1').replace(/=([^=\n]+)=/g, '$1');
  const blocks = body.split(/\n\s*\n/).map((b) => b.trim()).filter(Boolean);
  const isHeading = (b) => !b.includes('\n') && b.length < 70 && (
    /^(\w+es|\d+\.)\s+(Kapitel|Buch|Teil|Akt|Aufzug)/i.test(b) || /^(Kapitel|Buch|Teil|Erster|Zweiter|Dritter|Vierter|Fünfter|Sechster|Siebenter)\b/i.test(b) ||
    /^[IVXLC]+\.?$/.test(b) || /^[IVXLC]+\.\s+\S/.test(b) || (b === b.toUpperCase() && /[A-ZÄÖÜ]{4}/.test(b) && b.split(' ').length < 9));
  const chapters = [];
  let ch = { title: '', paragraphs: [] };
  for (const b of blocks) {
    if (/^Anmerkungen? zur Transkription/i.test(b) && chapters.length > 2) break;
    if (JUNK.test(b) || /^[-*=_.\s]+$/.test(b)) continue;
    if (isHeading(b)) { if (ch.paragraphs.length) chapters.push(ch); ch = { title: niceTitle(b), paragraphs: [] }; continue; }
    const lines = b.split('\n');
    const verse = lines.length > 1 && lines.every((l) => l.trim().length < 60);
    ch.paragraphs.push(verse ? lines.map((l) => l.trim()).join('\n') : b.replace(/\s*\n\s*/g, ' '));
  }
  if (ch.paragraphs.length) chapters.push(ch);
  const merged = [];
  for (const c of chapters) {
    const prev = merged[merged.length - 1];
    if (prev && wc(prev.paragraphs.join(' ')) < 90) { prev.paragraphs.push(...c.paragraphs); prev.title = c.title || prev.title; } else merged.push(c);
  }
  if (merged.length > 1 && wc(merged[0].paragraphs.join(' ')) < 150) merged.shift();
  return split(merged);
}
const niceTitle = (t) => (t === t.toUpperCase() && /[A-ZÄÖÜ]{3}/.test(t) ? t.charAt(0) + t.slice(1).toLowerCase() : t);
function split(chapters, MAX = 3500) {
  const out = [];
  for (const c of chapters) {
    const total = wc(c.paragraphs.join(' '));
    if (total <= MAX * 1.3) { out.push(c); continue; }
    const parts = Math.ceil(total / MAX);
    let part = [], n = 0, k = 1;
    for (const p of c.paragraphs) {
      part.push(p); n += wc(p);
      if (n >= total / parts && k < parts) { out.push({ title: c.title ? `${c.title} (${k})` : '', paragraphs: part }); part = []; n = 0; k++; }
    }
    if (part.length) out.push({ title: c.title ? `${c.title} (${k})` : '', paragraphs: part });
  }
  return out;
}

async function fetchText(g) {
  let lastErr;
  for (const m of MIRRORS) {
    try {
      const r = await fetch(`${m}/cache/epub/${g}/pg${g}.txt`, { signal: AbortSignal.timeout?.(60_000) });
      if (r.ok) return await r.text();
      lastErr = new Error('HTTP ' + r.status);
    } catch (e) { lastErr = e; }
  }
  throw lastErr || new Error('offline');
}

/** Книжка з Gutenberg: з телефона, якщо вже завантажена, інакше — з дзеркала (і зберегти). */
export async function loadGutenbergBook(id, g, onProgress) {
  const saved = await getSaved(id);
  if (saved) return saved;
  onProgress?.('download');
  const txt = await fetchText(g);
  onProgress?.('parse');
  const chapters = parseGutenberg(txt);
  if (!chapters.length) throw new Error('empty');
  const book = { id, chapters, words: chapters.reduce((n, c) => n + wc(c.paragraphs.join(' ')), 0) };
  await saveBook(id, book);
  return book;
}

// ---------- каталог ----------
let catalogPromise;
export function loadCatalog() {
  catalogPromise ||= fetch('books/catalog.json').then((r) => (r.ok ? r.json() : [])).catch(() => []).then((list) => list.map(toMeta));
  return catalogPromise;
}
export function toMeta(b) {
  return {
    id: 'pg' + b.g, gutenberg: b.g, remote: 'gutenberg', title: b.t, subtitle: b.st || '', author: b.a, authorYears: b.ay || null,
    translator: b.tr || null, year: b.y || null, level: b.lv || 'B2', premium: true, collections: b.c || ['world'],
    downloads: b.d || 0, subjects: b.s || [], cover: b.cover || `covers/pg/${b.g}.jpg`, coverFallback: true,
    source: { name: 'Project Gutenberg', url: `https://www.gutenberg.org/ebooks/${b.g}` },
    description: null,
  };
}

// ---------- пошук будь-якої книжки (Gutendex) для імпорту ----------
export async function searchGutenberg(q, lang = 'de') {
  const url = `https://gutendex.com/books/?search=${encodeURIComponent(q)}${lang ? `&languages=${lang}` : ''}&copyright=false`;
  const r = await fetch(url, { signal: AbortSignal.timeout?.(45_000) });
  if (!r.ok) throw new Error('HTTP ' + r.status);
  const d = await r.json();
  const PD = new Date().getFullYear() - 71;
  return d.results
    .filter((b) => b.media_type === 'Text')
    .map((b) => {
      const people = [...b.authors, ...(b.translators || [])];
      const free = !b.copyright && people.every((p) => p.death_year && p.death_year <= PD);
      const name = (n) => { const [l, f] = n.split(',').map((s) => s.trim()); return f ? `${f} ${l}` : l; };
      return {
        g: b.id, t: b.title.split(/[\r\n]/)[0].split(/:\s/)[0], a: b.authors[0] ? name(b.authors[0].name) : 'Anonym',
        ay: b.authors[0] ? `${b.authors[0].birth_year ?? '?'}-${b.authors[0].death_year ?? '?'}` : '',
        tr: (b.translators || []).map((t) => name(t.name)).join(', ') || null, d: b.download_count, free,
        lang: b.languages.join(', '), cover: b.formats['image/jpeg'] || null, c: ['world'], lv: 'B2',
      };
    });
}
