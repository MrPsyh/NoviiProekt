#!/usr/bin/env node
// Масовий імпорт німецьких книжок з Project Gutenberg через API Gutendex (gutendex.com).
//
//   npm run bulk                  ← до 2000 найпопулярніших німецьких книжок
//   npm run bulk -- --max 500     ← менше
//   npm run bulk -- --meta-only   ← лише каталог (назви, автори, теми), без текстів
//
// Що робить:
//  • бере тільки книжки суспільного надбання: copyright=false, автор і перекладач померли
//    понад 70 років тому (правило ЄС і України);
//  • завантажує текст (.txt), ділить на розділи, сам оцінює рівень A2–C1 (довжина речень і слів);
//  • розкладає по колекціях за темами Gutenberg (дитячі, поезія, слов’янські, японські автори…);
//  • кладе тексти в remote-books/<id>.json, а в застосунок — лише каталог app/books/remote.json.
//
// Чому тексти не в самому застосунку: 2000 книжок ≈ 500–800 МБ, такий застосунок магазини не пропустять.
// Тому папку remote-books/ треба викласти на будь-який статичний хостинг (Cloudflare R2, GitHub Pages,
// Firebase Hosting) і вписати адресу в BOOKS_CDN_URL (app/js/config.js). Застосунок завантажує книжку,
// коли її відкривають, і зберігає на телефоні, тож далі вона читається офлайн.
//
// Скрипт можна переривати: уже завантажене пропускається. Між запитами — пауза (етикет Gutenberg).
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { textToChapters, PD_YEAR } = require('./gutenberg.js');

const ROOT = path.join(__dirname, '..');
const OUT = path.join(ROOT, 'remote-books');
const INDEX = path.join(ROOT, 'app', 'books', 'remote.json');
const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf('--' + k); return i < 0 ? d : args[i + 1] && !args[i + 1].startsWith('--') ? args[i + 1] : true; };
const MAX = Number(opt('max', 2000));
const META_ONLY = !!opt('meta-only', false);
const GAP = Number(opt('gap', 2000));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
fs.mkdirSync(OUT, { recursive: true });

async function get(url, as = 'json', tries = 6) {
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(url, { headers: { 'User-Agent': 'LesefreundImporter/0.2 (educational reading app)' }, signal: AbortSignal.timeout(90_000) });
      if (r.status === 429 || r.status >= 500) throw new Error('HTTP ' + r.status);
      if (!r.ok) return null;
      return as === 'json' ? await r.json() : await r.text();
    } catch (e) {
      process.stdout.write(`  …${e.message}, повтор через ${10 * (i + 1)}с\n`);
      await sleep(10_000 * (i + 1));
    }
  }
  throw new Error('недоступно: ' + url);
}

const SLAVIC = /tolstoy|tolstoi|dostoyevsky|dostojewski|pushkin|puschkin|gogol|chekhov|tschechow|turgenev|turgenjew|lermontov|gorky|gorki|andreyev|korolenko|shevchenko|schewtschenko|franko|kotsiubynsky|kobylianska/i;
const JAPAN = /japan|japon|nippon|akutagawa|natsume|mori, ōgai|hearn, lafcadio/i;
function collections(b) {
  const subj = [...b.subjects, ...b.bookshelves].join(' ').toLowerCase();
  const who = b.authors.map((a) => a.name).join(' ');
  const c = [];
  if (/juvenile|children|kinder|fairy tales|märchen/.test(subj)) c.push('kids');
  if (/ukrain/.test(subj + ' ' + who.toLowerCase())) c.push('ukraine');
  if (SLAVIC.test(who)) c.push('slavic');
  if (JAPAN.test(subj + ' ' + who)) c.push('japan');
  if (/poetry|poems|gedichte|lyrik/.test(subj)) c.push('poetry');
  if (!c.length || c.every((x) => x === 'poetry')) c.push('world');
  return [...new Set(c)];
}

// Груба оцінка рівня: середня довжина речення й частка довгих слів
function estimateLevel(chapters) {
  const text = chapters.slice(0, 3).flatMap((c) => c.paragraphs).join(' ').slice(0, 60_000);
  const sentences = text.split(/[.!?]+\s/).filter((s) => s.length > 3);
  const words = text.match(/[\p{L}]+/gu) || [];
  if (!words.length) return 'B2';
  const avgSent = words.length / Math.max(1, sentences.length);
  const longShare = words.filter((w) => w.length >= 10).length / words.length;
  const score = avgSent / 6 + longShare * 20;
  return score < 3.2 ? 'A2' : score < 4.2 ? 'B1' : score < 5.4 ? 'B2' : 'C1';
}
const isFree = (people) => people.every((p) => p.death_year && p.death_year <= PD_YEAR);
const nameOf = (n) => { const [last, first] = n.split(',').map((s) => s.trim()); return first ? `${first.replace(/\s*\(.*\)/, '')} ${last}` : last; };
const slug = (s) => s.normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/ß/g, 'ss').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 40);

(async () => {
  const index = fs.existsSync(INDEX) ? JSON.parse(fs.readFileSync(INDEX, 'utf8')) : [];
  const have = new Set(index.map((b) => b.gutenberg));
  let url = 'https://gutendex.com/books/?languages=de&copyright=false&sort=popular';
  let seen = 0, added = 0, skipped = 0;
  while (url && index.length < MAX) {
    const page = await get(url);
    if (!page) break;
    for (const b of page.results) {
      if (index.length >= MAX) break;
      seen++;
      if (have.has(b.id)) continue;
      if (b.copyright || !b.languages.includes('de') || !isFree(b.authors) || !isFree(b.translators || [])) { skipped++; continue; }
      if (b.media_type !== 'Text') { skipped++; continue; }
      const txtUrl = Object.entries(b.formats).find(([k]) => k.startsWith('text/plain'))?.[1];
      if (!txtUrl) { skipped++; continue; }
      const author = b.authors[0] ? nameOf(b.authors[0].name) : 'Anonym';
      const id = `pg${b.id}-${slug(b.title)}`;
      const meta = {
        id, gutenberg: b.id, remote: true, title: b.title.split(/[\r\n]|: /)[0].trim(), author,
        authorYears: b.authors[0] ? `${b.authors[0].birth_year ?? '?'}–${b.authors[0].death_year ?? '?'}` : null,
        translator: (b.translators || []).map((t) => nameOf(t.name)).join(', ') || null,
        premium: true, collections: collections(b), subjects: b.subjects.slice(0, 6), downloads: b.download_count,
        description: { uk: '', ru: '', en: (b.summaries?.[0] || '').slice(0, 400) },
        source: { name: 'Project Gutenberg', url: `https://www.gutenberg.org/ebooks/${b.id}` },
      };
      if (!META_ONLY) {
        await sleep(GAP);
        const txt = await get(txtUrl, 'text');
        if (!txt) { skipped++; continue; }
        const chapters = textToChapters(txt);
        const words = chapters.reduce((n, c) => n + c.paragraphs.join(' ').split(/\s+/).length, 0);
        if (words < 300) { skipped++; continue; }
        fs.writeFileSync(path.join(OUT, id + '.json'), JSON.stringify({ id, chapters }));
        Object.assign(meta, { words, chapters: chapters.length, level: estimateLevel(chapters) });
      } else meta.level = 'B2';
      index.push(meta);
      have.add(b.id);
      added++;
      console.log(`✓ ${index.length}. ${meta.title} — ${author} [${meta.level}, ${meta.collections.join('/')}]`);
      if (added % 10 === 0) fs.writeFileSync(INDEX, JSON.stringify(index));
    }
    url = page.next;
    await sleep(GAP);
  }
  fs.writeFileSync(INDEX, JSON.stringify(index));
  console.log(`\nГотово: у каталозі ${index.length} книжок (нових ${added}, переглянуто ${seen}, пропущено ${skipped}).`);
  console.log('Далі: npm run covers, викласти папку remote-books/ на хостинг і вписати BOOKS_CDN_URL у app/js/config.js.');
})().catch((e) => { console.error('✗ ' + e.message); process.exit(1); });
