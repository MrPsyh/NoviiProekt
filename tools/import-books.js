#!/usr/bin/env node
// Імпорт книжок суспільного надбання з німецької Wikisource у застосунок.
//   npm run import             — імпортувати все з tools/catalog.json (вже імпортовані пропускає)
//   npm run import -- kafka-verwandlung --force   — перезалити одну книжку
// Результат: app/books/<id>.json (текст) і app/books/index.json (каталог).
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { parse } = require('./wikisource.js');

const ROOT = path.join(__dirname, '..');
const OUT = path.join(ROOT, 'app', 'books');
const catalog = fs.existsSync(path.join(__dirname, 'catalog.json')) ? JSON.parse(fs.readFileSync(path.join(__dirname, 'catalog.json'), 'utf8')) : [];
fs.mkdirSync(OUT, { recursive: true });

const args = process.argv.slice(2);
const force = args.includes('--force');
const only = args.filter((a) => !a.startsWith('--'));

// ---------- HTML → блоки тексту ----------
const SKIP_CLASS = /\b(noprint|ws-noexport|PageNumber|pagenum|reference|references|mw-editsection|hiddenStructure|mw-cite-backlink|ws-summary|metadata|navbox|toc|Vorlage_Hinweis|prp-page-qualit)/;
const SKIP_ID = /^(textdaten|toc|ws-data|headertemplate)/;
const VOID = new Set(['br', 'img', 'hr', 'wbr', 'input', 'meta', 'link', 'col', 'area', 'source']);
const BLOCK = new Set(['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'tr', 'td', 'th', 'blockquote', 'center', 'dd', 'dt', 'table', 'ul', 'ol', 'dl', 'poem']);
const ENT = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', shy: '', ndash: '–', mdash: '—', hellip: '…' };
const decode = (s) => s.replace(/&(#x[0-9a-f]+|#\d+|\w+);/gi, (m, e) =>
  e[0] === '#' ? String.fromCodePoint(e[1].toLowerCase() === 'x' ? parseInt(e.slice(2), 16) : +e.slice(1)) : ENT[e] ?? m);

function htmlToBlocks(html) {
  const blocks = [];
  let cur = '';
  let curHeading = false;
  const stack = []; // { tag, skip, heading }
  const skipping = () => stack.some((s) => s.skip);
  const inPoem = () => stack.some((s) => s.poem);
  const flush = () => {
    const text = cur.replace(/[ \t\r\f]+/g, ' ').replace(/ *\n */g, '\n').replace(/\n{2,}/g, '\n').trim();
    if (text) blocks.push({ text, heading: curHeading });
    cur = '';
    curHeading = false;
  };
  // вірш: один блок з рядками, далі ділимо на строфи по ~8 рядків
  const flushPoem = () => {
    const lines = cur.split('\n').map((l) => l.replace(/[ \t]+/g, ' ').trim()).filter(Boolean);
    cur = '';
    let group = [];
    for (const l of lines) {
      group.push(l);
      if (group.length >= 8 && /[.!?;:–—]$/.test(l) || group.length >= 14) { blocks.push({ text: group.join('\n'), heading: false }); group = []; }
    }
    if (group.length) blocks.push({ text: group.join('\n'), heading: false });
  };
  const re = /<(\/?)([a-zA-Z][\w-]*)([^>]*?)(\/?)>|([^<]+)/g;
  let m;
  while ((m = re.exec(html))) {
    if (m[5] != null) { if (!skipping()) cur += decode(m[5]).replace(/\n/g, ' '); continue; }
    const [, close, rawTag, attrs, selfClose] = m;
    const tag = rawTag.toLowerCase();
    if (tag === 'br') { if (!skipping()) cur += '\n'; continue; }
    if (close) {
      // закриваємо до найближчого такого ж тегу
      let wasPoem = false;
      for (let i = stack.length - 1; i >= 0; i--) if (stack[i].tag === tag) { wasPoem = stack[i].poem; stack.length = i; break; }
      if (BLOCK.has(tag) && !skipping() && (!inPoem() || wasPoem)) { if (wasPoem) flushPoem(); else flush(); }
      continue;
    }
    if (VOID.has(tag) || selfClose) continue;
    const cls = /class="([^"]*)"/.exec(attrs)?.[1] || '';
    const id = /id="([^"]*)"/.exec(attrs)?.[1] || '';
    const style = /style="([^"]*)"/.exec(attrs)?.[1] || '';
    const skip = SKIP_CLASS.test(cls) || SKIP_ID.test(id) || tag === 'sup' && /reference/.test(cls) || tag === 'script' || tag === 'style' || /display:\s*none/.test(style);
    const poem = /\bpoem\b/.test(cls) || tag === 'poem';
    if (BLOCK.has(tag) && !skipping() && !inPoem()) flush();
    const heading = /^h[1-6]$/.test(tag) || (tag === 'div' || tag === 'p' || tag === 'center') && /text-align:\s*center/.test(style) || tag === 'center';
    stack.push({ tag, skip: skip || tag === 'figure', poem });
    if (heading && !skipping()) curHeading = true;
  }
  flush();
  return blocks;
}

const wc = (s) => (s.match(/[\p{L}\p{N}]+/gu) || []).length;

function blocksToChapters(blocks, { defaultTitle = '', headingMaxWords = 12, minWords = 120 } = {}) {
  const chapters = [];
  let ch = { title: defaultTitle, paragraphs: [] };
  for (const b of blocks) {
    if (/^(Anmerkungen|Fußnoten|Anmerkung des|Quelle:|Lizenz|Kategorie)/i.test(b.text)) continue;
    if (b.heading && wc(b.text) <= headingMaxWords) {
      if (ch.paragraphs.length) chapters.push(ch);
      ch = { title: b.text.replace(/\n/g, ' '), paragraphs: [] };
      continue;
    }
    ch.paragraphs.push(b.text);
  }
  if (ch.paragraphs.length) chapters.push(ch);
  // злиття дрібних розділів (титули, присвяти) з наступними
  const merged = [];
  for (const c of chapters) {
    const prev = merged[merged.length - 1];
    if (prev && wc(prev.paragraphs.join(' ')) < minWords) { prev.paragraphs.push(...c.paragraphs); if (!prev.title) prev.title = c.title; }
    else merged.push(c);
  }
  return merged;
}

// Службові рядки Wikisource, яких не має бути в книжці
const JUNK = /^(Andere Ausgaben|Weitere Ausgaben|Siehe auch|Siehe unter|Dieser Text|Textdaten|Fertig!|Korrektur|Indexseite|Zum Inhaltsverzeichnis|Inhaltsverzeichnis$|\[?Bearbeiten|<<|>>|Nach oben|Anmerkungen? \(Wikisource\)|\d+$|\[\d+\]$|←|→)/i;
function clean(chapters) {
  return chapters
    .map((c) => ({ ...c, paragraphs: c.paragraphs.map((p) => p.replace(/\[\d+\]/g, '').replace(/ {2,}/g, ' ').trim()).filter((p) => p && !JUNK.test(p)) }))
    .filter((c) => c.paragraphs.length);
}

// Дуже довгі розділи ділимо на частини (~3500 слів), щоб читалка працювала плавно.
function splitLong(chapters, max = 3500) {
  const out = [];
  for (const c of chapters) {
    const total = wc(c.paragraphs.join(' '));
    if (total <= max * 1.3) { out.push(c); continue; }
    const parts = Math.ceil(total / max);
    let part = [], n = 0, k = 1;
    for (const p of c.paragraphs) {
      part.push(p); n += wc(p);
      if (n >= total / parts && k < parts) {
        out.push({ title: `${c.title || ''} (${k})`.trim(), paragraphs: part }); part = []; n = 0; k++;
      }
    }
    if (part.length) out.push({ title: `${c.title || ''} (${k})`.trim(), paragraphs: part });
  }
  return out;
}

function subpageLinks(html, page) {
  const base = '/wiki/' + encodeURIComponent(page.replace(/ /g, '_')).replace(/%2F/g, '/') + '/';
  const seen = new Set();
  const out = [];
  for (const m of html.matchAll(/href="(\/wiki\/[^"#?]+)"/g)) {
    const href = m[1];
    const norm = decodeURIComponent(href);
    const want = decodeURIComponent(base);
    if (norm.startsWith(want) && !seen.has(norm)) { seen.add(norm); out.push(norm.slice(6).replace(/_/g, ' ')); }
  }
  return out;
}

// Дані з таблички «Textdaten» на сторінці Wikisource
function extractMeta(html) {
  const get = (id) => {
    const m = new RegExp(`id="${id}"[^>]*>([\\s\\S]*?)</span>`).exec(html);
    return m ? decode(m[1].replace(/<[^>]+>/g, '')).trim() : '';
  };
  return { author: get('ws-author'), translator: get('ws-translator'), year: get('ws-year'), title: get('ws-title') };
}

async function importPages(e) {
  const chapters = [];
  let meta = null;
  for (const page of e.pages) {
    try {
      const p = await parse(page);
      const m = extractMeta(p.text);
      meta ||= m;
      const cs = blocksToChapters(htmlToBlocks(p.text), { defaultTitle: m.title || page.replace(/\s*\(.*\)$/, ''), minWords: 0, headingMaxWords: 0 });
      const paragraphs = cs.flatMap((c) => c.paragraphs).filter((x) => x !== m.title);
      if (paragraphs.length) chapters.push({ title: m.title || page.replace(/\s*\(.*\)$/, ''), paragraphs, translator: m.translator || undefined });
      process.stdout.write('.');
    } catch (err) { console.log(`   ✗ ${page}: ${err.message}`); }
  }
  const words = wc(chapters.map((c) => c.paragraphs.join(' ')).join(' '));
  return chapters.length ? { chapters: clean(chapters), words, page: e.pages[0], meta } : null;
}

async function importEntry(e) {
  if (e.pages) return importPages(e);
  let page = null, parsed = null;
  for (const cand of [e.page, ...(e.candidates || [])].filter(Boolean)) {
    try { parsed = await parse(cand); page = cand; break; } catch (err) { console.log(`   ✗ ${cand}: ${err.message}`); }
  }
  if (!parsed) return null;
  let chapters;
  const meta = extractMeta(parsed.text);
  const subs = e.subpages === false ? [] : subpageLinks(parsed.text, parsed.title || page);
  const ownWords = wc(htmlToBlocks(parsed.text).map((b) => b.text).join(' '));
  if (subs.length && (e.subpages || ownWords < 400 * subs.length)) {
    chapters = [];
    for (const s of subs) {
      if (e.skipSubpages?.some((x) => s.includes(x))) continue;
      try {
        const p = await parse(s);
        const title = s.slice(s.lastIndexOf('/') + 1);
        const cs = blocksToChapters(htmlToBlocks(p.text), { defaultTitle: title, minWords: 60 });
        if (cs.length && !cs[0].title) cs[0].title = title;
        chapters.push(...cs);
        process.stdout.write('.');
      } catch (err) { console.log(`   ✗ ${s}: ${err.message}`); }
    }
    // власний текст головної сторінки (передмова), без списку посилань на розділи
    const subTitles = new Set(subs.map((x) => x.slice(x.lastIndexOf('/') + 1)));
    const own = blocksToChapters(htmlToBlocks(parsed.text), { defaultTitle: e.title, minWords: 0 })
      .map((c) => ({ ...c, paragraphs: c.paragraphs.filter((p) => !subTitles.has(p) && p !== meta.title) }))
      .filter((c) => c.paragraphs.length && !subTitles.has(c.title));
    if (wc(own.map((c) => c.paragraphs.join(' ')).join(' ')) > 40) chapters.unshift(...own);
  } else {
    chapters = blocksToChapters(htmlToBlocks(parsed.text), { defaultTitle: e.title, minWords: e.poem ? 0 : 120 });
  }
  if (e.dropFirst) chapters = chapters.slice(e.dropFirst);
  chapters = clean(splitLong(chapters));
  const words = wc(chapters.map((c) => c.paragraphs.join(' ')).join(' '));
  if (words < 30) { console.log(`   ✗ замало тексту (${words})`); return null; }
  return { chapters, words, page: parsed.title || page, meta };
}

function metaOf(e, words, chapters, page, ws = {}) {
  return {
    id: e.id, title: e.title || ws.title, author: e.author || ws.author, authorYears: e.authorYears || null, year: e.year || ws.year || null,
    translator: e.translator || ws.translator || null, level: e.level, premium: !!e.premium, collections: e.collections,
    description: e.description, words, chapters,
    source: page ? { name: 'Wikisource', url: 'https://de.wikisource.org/wiki/' + encodeURIComponent(page.replace(/ /g, '_')) } : { name: 'Lesefreund' },
  };
}

if (require.main === module && args.includes('--clean')) {
  // перечистити вже імпортовані книжки без завантаження
  for (const f of fs.readdirSync(OUT)) {
    if (f === 'index.json' || !f.endsWith('.json')) continue;
    const b = JSON.parse(fs.readFileSync(path.join(OUT, f), 'utf8'));
    fs.writeFileSync(path.join(OUT, f), JSON.stringify({ ...b, chapters: clean(b.chapters) }));
  }
  console.log('Почищено');
} else if (require.main === module) (async () => {
  const indexFile = path.join(OUT, 'index.json');
  const index = new Map((fs.existsSync(indexFile) ? JSON.parse(fs.readFileSync(indexFile, 'utf8')) : []).map((b) => [b.id, b]));
  for (const e of catalog) {
    if (only.length && !only.includes(e.id)) continue;
    const file = path.join(OUT, e.id + '.json');
    if (e.chapters) { // власні тексти Lesefreund прямо в каталозі
      fs.writeFileSync(file, JSON.stringify({ id: e.id, chapters: e.chapters }));
      const words = wc(e.chapters.map((c) => c.paragraphs.join(' ')).join(' '));
      index.set(e.id, metaOf(e, words, e.chapters.length, null));
      continue;
    }
    if ((fs.existsSync(file) && !force && index.has(e.id)) || e.gutenberg) {
      // вже імпортовано (або додано через tools/gutenberg.js): оновлюємо лише метадані з каталогу
      const old = index.get(e.id);
      if (old) index.set(e.id, { ...old, ...Object.fromEntries(Object.entries(metaOf(e, old.words, old.chapters, null)).filter(([k, v]) => v != null && k !== 'source')) });
      continue;
    }
    console.log(`→ ${e.id}: ${e.page}`);
    const r = await importEntry(e);
    if (!r) { console.log('   пропущено'); continue; }
    fs.writeFileSync(file, JSON.stringify({ id: e.id, chapters: r.chapters }));
    index.set(e.id, metaOf(e, r.words, r.chapters.length, r.page, r.meta || {}));
    console.log(`   ✓ ${r.words} слів, ${r.chapters.length} розд.`);
    fs.writeFileSync(indexFile, JSON.stringify(orderByCatalog(index), null, 1));
  }
  fs.writeFileSync(indexFile, JSON.stringify(orderByCatalog(index), null, 1));
  console.log(`Готово. У каталозі ${index.size} книжок.`);
})();

function orderByCatalog(index) {
  const order = catalog.map((c) => c.id);
  return [...index.values()].filter((b) => order.includes(b.id)).sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id));
}

module.exports = { htmlToBlocks, blocksToChapters, extractMeta };
