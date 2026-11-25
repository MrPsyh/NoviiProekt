#!/usr/bin/env node
// Справжні обкладинки: шукає на Wikimedia Commons ілюстрації суспільного надбання
// (старі видання, картини, гравюри, портрети авторів) і зберігає їх локально.
//
//   node tools/fetch-art.js --candidates          ← знайти варіанти (tools/.cache/art-candidates.json)
//   node tools/fetch-art.js                       ← завантажити обрані (catalog.json: art / artPick)
//
// Беремо лише файли з ліцензією «Public domain» / CC0 і зберігаємо автора ілюстрації
// (показується в картці книжки). Обкладинки видавництв захищені авторським правом,
// тому ми їх не беремо, а оформлюємо справжні старі ілюстрації в обкладинку.
'use strict';
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.join(__dirname, '..');
const API = 'https://commons.wikimedia.org/w/api.php';
const UA = 'LesefreundImporter/0.3 (educational reading app; cover art from public domain)';
const ART_DIR = path.join(ROOT, 'app', 'covers', 'art');
const CREDITS = path.join(ROOT, 'app', 'covers', 'credits.json');
const CAND = path.join(__dirname, '.cache', 'art-candidates.json');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
fs.mkdirSync(ART_DIR, { recursive: true });
fs.mkdirSync(path.dirname(CAND), { recursive: true });

async function get(url, as = 'json') {
  for (let i = 0; i < 6; i++) {
    const r = await fetch(url, { headers: { 'User-Agent': UA, 'Api-User-Agent': UA } }).catch(() => null);
    if (r && r.ok) return as === 'json' ? r.json() : Buffer.from(await r.arrayBuffer());
    const wait = Number(r?.headers.get('retry-after')) || 10 * (i + 1);
    process.stdout.write(`  …${r ? r.status : 'net'}, ${wait}s\n`);
    await sleep(wait * 1000);
  }
  throw new Error('недоступно ' + url);
}
const strip = (s) => String(s || '').replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
const isPD = (m) => /public domain|^pd|cc0|cc-zero/i.test(strip(m?.LicenseShortName?.value)) || /pd-/i.test(strip(m?.License?.value));

async function search(q, limit = 6) {
  const p = new URLSearchParams({
    action: 'query', format: 'json', generator: 'search', gsrnamespace: '6', gsrlimit: String(limit * 3),
    gsrsearch: q + ' filetype:bitmap', prop: 'imageinfo', iiprop: 'url|size|extmetadata', iiurlwidth: '700',
  });
  const d = await get(API + '?' + p);
  const pages = Object.values(d.query?.pages || {}).sort((a, b) => a.index - b.index);
  return pages
    .map((pg) => ({ title: pg.title, ii: pg.imageinfo?.[0] }))
    .filter((x) => x.ii && isPD(x.ii.extmetadata) && x.ii.height >= 300)
    .slice(0, limit)
    .map((x) => ({
      file: x.title, thumb: x.ii.thumburl, w: x.ii.width, h: x.ii.height,
      artist: strip(x.ii.extmetadata.Artist?.value).slice(0, 80), date: strip(x.ii.extmetadata.DateTimeOriginal?.value).slice(0, 30),
      license: strip(x.ii.extmetadata.LicenseShortName?.value), page: x.ii.descriptionurl,
    }));
}

async function fileInfo(file) {
  const p = new URLSearchParams({ action: 'query', format: 'json', titles: file, prop: 'imageinfo', iiprop: 'url|extmetadata', iiurlwidth: '700' });
  const d = await get(API + '?' + p);
  const ii = Object.values(d.query.pages)[0].imageinfo?.[0];
  if (!ii) throw new Error('немає файлу ' + file);
  return { file, thumb: ii.thumburl, artist: strip(ii.extmetadata.Artist?.value).slice(0, 80), date: strip(ii.extmetadata.DateTimeOriginal?.value).slice(0, 30), license: strip(ii.extmetadata.LicenseShortName?.value), page: ii.descriptionurl, pd: isPD(ii.extmetadata) };
}

(async () => {
  const catalog = JSON.parse(fs.readFileSync(path.join(__dirname, 'catalog.json'), 'utf8'));
  if (process.argv.includes('--candidates')) {
    const out = fs.existsSync(CAND) ? JSON.parse(fs.readFileSync(CAND, 'utf8')) : {};
    for (const e of catalog) {
      if (out[e.id] && !process.argv.includes('--force')) continue;
      const q = e.artQuery || `${e.title} ${e.author}`;
      try { out[e.id] = await search(q); console.log(`${e.id}: ${out[e.id].length}`); } catch (err) { console.log(e.id, err.message); }
      fs.writeFileSync(CAND, JSON.stringify(out, null, 1));
      await sleep(700);
    }
    return;
  }
  const credits = fs.existsSync(CREDITS) ? JSON.parse(fs.readFileSync(CREDITS, 'utf8')) : {};
  const cand = fs.existsSync(CAND) ? JSON.parse(fs.readFileSync(CAND, 'utf8')) : {};
  for (const e of catalog) {
    const file = path.join(ART_DIR, e.id + '.jpg');
    if (fs.existsSync(file) && credits[e.id]?.file === (e.art || credits[e.id]?.file) && !process.argv.includes('--force')) continue;
    let info = null;
    if (e.art) info = await fileInfo(e.art);
    else if (cand[e.id]?.length) info = cand[e.id][e.artPick || 0];
    if (!info) { console.log(`– ${e.id}: немає ілюстрації`); continue; }
    if (info.pd === false) { console.log(`✗ ${e.id}: ${info.file} не суспільне надбання`); continue; }
    fs.writeFileSync(file, await get(info.thumb, 'buf'));
    credits[e.id] = { file: info.file, artist: info.artist, date: info.date, license: info.license, page: info.page };
    console.log(`✓ ${e.id}: ${info.file}`);
    fs.writeFileSync(CREDITS, JSON.stringify(credits, null, 1));
    await sleep(500);
  }
})().catch((e) => { console.error('✗ ' + e.message); process.exit(1); });
