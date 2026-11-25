#!/usr/bin/env node
// Відібрані книжки з Project Gutenberg → у застосунок (працюють офлайн).
// Список — tools/gutenberg-picks.json. Метадані: Gutendex; тексти й обкладинки: офіційне дзеркало
// aleph.pglaf.org (основний сайт gutenberg.org буває недоступний).
// Обкладинка: скан справжньої обкладинки з Gutenberg-видання (суспільне надбання), якщо він є.
//   node tools/gutenberg-curated.js            (уже імпортовані пропускає; --force — перезалити)
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { textToChapters, PD_YEAR } = require('./gutenberg.js');

const ROOT = path.join(__dirname, '..');
const BOOKS = path.join(ROOT, 'app', 'books');
const ART = path.join(ROOT, 'app', 'covers', 'art');
const MIRROR = 'https://aleph.pglaf.org';
const picks = JSON.parse(fs.readFileSync(path.join(__dirname, 'gutenberg-picks.json'), 'utf8'));
const force = process.argv.includes('--force');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
fs.mkdirSync(ART, { recursive: true });

const dir = (id) => { const s = String(id); return `${MIRROR}/${s.length === 1 ? '0' : s.slice(0, -1).split('').join('/')}/${s}/`; };
async function get(url, as = 'text') {
  for (let i = 0; i < 4; i++) {
    try {
      const r = await fetch(url, { signal: AbortSignal.timeout(120_000), headers: { 'User-Agent': 'LesefreundImporter/0.3' } });
      if (r.status === 404) return null;
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return as === 'buf' ? Buffer.from(await r.arrayBuffer()) : as === 'json' ? r.json() : r.text();
    } catch (e) { process.stdout.write(`  …${e.message}\n`); await sleep(8000 * (i + 1)); }
  }
  return null;
}
const links = (html) => [...String(html || '').matchAll(/href="([^"?]+)"/g)].map((m) => m[1]).filter((h) => !h.startsWith('..'));

async function text(id) {
  const base = dir(id);
  for (const f of [`${id}-0.txt`, `${id}.txt`, `${id}-8.txt`]) {
    const buf = await get(base + f, 'buf');
    if (buf) return f.endsWith('-8.txt') || (f === `${id}.txt` && !/[äöüß]/.test(buf.toString('utf8').slice(0, 20000))) ? buf.toString('latin1') : buf.toString('utf8');
  }
  return null;
}
async function cover(id) {
  const img = `${dir(id)}${id}-h/images/`;
  const list = links(await get(img));
  const pick = list.find((h) => /^cover\.(jpe?g|png)$/i.test(h)) || list.find((h) => /cover.*\.(jpe?g)$/i.test(h) && !/light/i.test(h)) ||
    list.find((h) => /(front|titel|title).*\.(jpe?g)$/i.test(h));
  return pick ? { url: img + pick, buf: await get(img + pick, 'buf') } : null;
}
const nameOf = (n) => { const [last, first] = n.split(',').map((s) => s.trim()); return first ? `${first.replace(/\s*\(.*\)/, '')} ${last}` : last; };

(async () => {
  const idxFile = path.join(BOOKS, 'index.json');
  const index = JSON.parse(fs.readFileSync(idxFile, 'utf8'));
  const catFile = path.join(__dirname, 'catalog.json');
  const catalog = JSON.parse(fs.readFileSync(catFile, 'utf8'));
  const credits = JSON.parse(fs.existsSync(path.join(ROOT, 'app', 'covers', 'credits.json')) ? fs.readFileSync(path.join(ROOT, 'app', 'covers', 'credits.json'), 'utf8') : '{}');
  // метадані зі сторінок Gutendex, уже збережених у tools/.cache (gx-*.json), — щоб не чекати API
  const cached = new Map();
  const cacheDir = path.join(__dirname, '.cache');
  for (const f of fs.existsSync(cacheDir) ? fs.readdirSync(cacheDir) : []) {
    if (!/^gx-\d+\.json$/.test(f)) continue;
    try { for (const b of JSON.parse(fs.readFileSync(path.join(cacheDir, f), 'utf8')).results) cached.set(b.id, b); } catch {}
  }
  for (const p of picks) {
    if (index.some((b) => b.id === p.id) && !force) continue;
    const meta = cached.get(p.gutenberg) || (await get(`https://gutendex.com/books/${p.gutenberg}/`, 'json')) || {};
    const people = [...(meta.authors || []), ...(meta.translators || [])];
    if (people.some((a) => !a.death_year || a.death_year > PD_YEAR)) { console.log(`✗ ${p.id}: автор/перекладач ще захищений`); continue; }
    const txt = await text(p.gutenberg);
    if (!txt) { console.log(`✗ ${p.id}: немає тексту на дзеркалі`); continue; }
    const chapters = textToChapters(txt);
    const words = chapters.reduce((n, c) => n + c.paragraphs.join(' ').split(/\s+/).length, 0);
    if (words < 150) { console.log(`✗ ${p.id}: замало тексту`); continue; }
    fs.writeFileSync(path.join(BOOKS, p.id + '.json'), JSON.stringify({ id: p.id, chapters }));
    const c = await cover(p.gutenberg);
    if (c?.buf) {
      fs.writeFileSync(path.join(ART, p.id + '.jpg'), c.buf);
      credits[p.id] = { file: c.url, artist: 'Project Gutenberg', date: '', license: 'Public domain', page: `https://www.gutenberg.org/ebooks/${p.gutenberg}`, original: true };
    }
    const entry = {
      id: p.id, gutenberg: p.gutenberg, title: p.title, author: p.author || nameOf(meta.authors?.[0]?.name || 'Anonym'),
      authorYears: meta.authors?.[0] ? `${meta.authors[0].birth_year ?? '?'}–${meta.authors[0].death_year ?? '?'}` : null,
      year: p.year || null, translator: (meta.translators || []).map((t) => nameOf(t.name)).join(', ') || null,
      level: p.level, premium: !!p.premium, collections: p.collections, description: p.description, artQuery: p.artQuery,
    };
    const i = catalog.findIndex((x) => x.id === p.id);
    if (i >= 0) catalog[i] = entry; else catalog.push(entry);
    const j = index.findIndex((x) => x.id === p.id);
    const row = { ...entry, words, chapters: chapters.length, source: { name: 'Project Gutenberg', url: `https://www.gutenberg.org/ebooks/${p.gutenberg}` } };
    if (j >= 0) index[j] = row; else index.push(row);
    fs.writeFileSync(idxFile, JSON.stringify(index, null, 1));
    fs.writeFileSync(catFile, JSON.stringify(catalog, null, 1));
    fs.writeFileSync(path.join(ROOT, 'app', 'covers', 'credits.json'), JSON.stringify(credits, null, 1));
    console.log(`✓ ${p.id}: ${words} слів, ${chapters.length} розд.${c?.buf ? ', оригінальна обкладинка' : ''}`);
    await sleep(1500);
  }
})();
