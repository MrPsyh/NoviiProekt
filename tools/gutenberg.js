#!/usr/bin/env node
// Додавання книжок з Project Gutenberg (там багато старих німецьких перекладів:
// Толстой, Достоєвський, Пушкін, Гоголь, японські казки тощо).
//
//   npm run gutenberg -- search Dostojewski          ← пошук німецьких книжок за автором/назвою
//   npm run gutenberg -- add 12345 --id dostojewski-schuld --collection slavic --level C1 --premium
//
// Скрипт перевіряє роки життя перекладача: у ЄС переклад вільний, якщо перекладач помер
// понад 70 років тому (тобто до 1956 р. включно, станом на 2026 р.). Інакше книжку не додає.
'use strict';
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.join(__dirname, '..');
const CACHE = path.join(__dirname, '.cache');
const CATALOG_URL = 'https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv';
const PD_YEAR = new Date().getFullYear() - 71; // помер у цьому році або раніше → вільно в ЄС
fs.mkdirSync(CACHE, { recursive: true });

function parseCsv(text) {
  const rows = []; let row = [], cur = '', q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { if (c === '"') { if (text[i + 1] === '"') { cur += '"'; i++; } else q = false; } else cur += c; }
    else if (c === '"') q = true;
    else if (c === ',') { row.push(cur); cur = ''; }
    else if (c === '\n') { row.push(cur); rows.push(row); row = []; cur = ''; }
    else if (c !== '\r') cur += c;
  }
  if (cur || row.length) { row.push(cur); rows.push(row); }
  const [head, ...rest] = rows;
  return rest.map((r) => Object.fromEntries(head.map((h, i) => [h, r[i] || ''])));
}
async function catalog() {
  const file = path.join(CACHE, 'pg_catalog.csv');
  if (!fs.existsSync(file) || Date.now() - fs.statSync(file).mtimeMs > 7 * 864e5) {
    const r = await fetch(CATALOG_URL);
    if (!r.ok) throw new Error(`Gutenberg недоступний (${r.status}). Спробуйте пізніше.`);
    fs.writeFileSync(file, await r.text());
  }
  return parseCsv(fs.readFileSync(file, 'utf8'));
}

// "Tolstoy, Leo, graf, 1828-1910; Löwenfeld, Raphael, 1854-1910 [Translator]"
function people(authors) {
  return authors.split(/;\s*/).map((a) => {
    const role = /\[([^\]]+)\]/.exec(a)?.[1] || 'Author';
    const years = /(\d{4})\??-(\d{4})?/.exec(a);
    const name = a.replace(/\[.*?\]/, '').replace(/,?\s*\d{4}.*$/, '').split(',').map((s) => s.trim()).filter(Boolean);
    return { role, name: name.length > 1 ? `${name[1]} ${name[0]}` : name[0], died: years?.[2] ? +years[2] : null };
  });
}

function textToChapters(txt) {
  const start = txt.search(/\*\*\*\s*START OF (THE|THIS) PROJECT GUTENBERG/i);
  const end = txt.search(/\*\*\*\s*END OF (THE|THIS) PROJECT GUTENBERG/i);
  let body = txt.slice(start >= 0 ? txt.indexOf('\n', start) + 1 : 0, end > 0 ? end : undefined).replace(/\r/g, '');
  body = body.replace(/_([^_]+)_/g, '$1');
  const blocks = body.split(/\n\s*\n/).map((b) => b.trim()).filter(Boolean);
  const isHeading = (b) => !b.includes('\n') && b.length < 70 && (
    /^(\w+es|\d+\.)\s+(Kapitel|Buch|Teil)/i.test(b) || /^(Kapitel|Buch|Teil|Erster|Zweiter|Dritter|Vierter|Fünfter)\b/i.test(b) ||
    /^[IVXLC]+\.?$/.test(b) || /^[IVXLC]+\.\s+\S/.test(b) || (b === b.toUpperCase() && /[A-ZÄÖÜ]{4}/.test(b) && b.split(' ').length < 9));
  const chapters = []; let ch = { title: '', paragraphs: [] };
  for (const b of blocks) {
    if (isHeading(b)) { if (ch.paragraphs.length) chapters.push(ch); ch = { title: b, paragraphs: [] }; continue; }
    const verse = b.split('\n').every((l) => l.length < 60) && b.split('\n').length > 1;
    ch.paragraphs.push(verse ? b.split('\n').map((l) => l.trim()).join('\n') : b.replace(/\s*\n\s*/g, ' '));
  }
  if (ch.paragraphs.length) chapters.push(ch);
  return chapters;
}

if (require.main === module) (async () => {
  const [cmd, ...rest] = process.argv.slice(2);
  const opt = (k) => { const i = rest.indexOf('--' + k); return i >= 0 ? (rest[i + 1] && !rest[i + 1].startsWith('--') ? rest[i + 1] : true) : null; };
  if (cmd === 'search') {
    const q = rest.filter((a) => !a.startsWith('--')).join(' ').toLowerCase();
    const rows = (await catalog()).filter((r) => r.Language.split(/;\s*/).includes('de') && (r.Title + ' ' + r.Authors).toLowerCase().includes(q));
    for (const r of rows.slice(0, 60)) {
      const tr = people(r.Authors).find((p) => /Translator/i.test(p.role));
      const ok = !tr || (tr.died && tr.died <= PD_YEAR);
      console.log(`${r['Text#'].padStart(6)}  ${ok ? '✓' : '✗'}  ${r.Title.replace(/\s+/g, ' ').slice(0, 70)} — ${r.Authors.slice(0, 90)}`);
    }
    console.log(`\n✓ — вільний переклад (перекладач помер до ${PD_YEAR + 1}) або оригінал; ✗ — переклад може бути захищений.`);
    return;
  }
  if (cmd === 'add') {
    const num = rest[0];
    const row = (await catalog()).find((r) => r['Text#'] === num);
    if (!row) throw new Error('Не знайдено книжку ' + num);
    const ps = people(row.Authors);
    const author = ps.find((p) => p.role === 'Author') || ps[0];
    const tr = ps.find((p) => /Translator/i.test(p.role));
    if (tr && !(tr.died && tr.died <= PD_YEAR) && !opt('force')) throw new Error(`Перекладач ${tr.name} (помер: ${tr.died || '?'}) — переклад може бути захищений. Не додаю.`);
    if (author.died && author.died > PD_YEAR && !opt('force')) throw new Error(`Автор ${author.name} помер у ${author.died} — твір ще захищений.`);
    const r = await fetch(`https://www.gutenberg.org/cache/epub/${num}/pg${num}.txt`);
    if (!r.ok) throw new Error('Не вдалося завантажити текст: ' + r.status);
    const chapters = textToChapters(await r.text());
    const id = opt('id') || `gutenberg-${num}`;
    fs.writeFileSync(path.join(ROOT, 'app', 'books', id + '.json'), JSON.stringify({ id, chapters }));
    const words = chapters.reduce((n, c) => n + c.paragraphs.join(' ').split(/\s+/).length, 0);
    const entry = {
      id, gutenberg: +num, title: opt('title') || row.Title.split(/[\n:]/)[0].trim(), author: author.name,
      translator: tr?.name || null, level: opt('level') || 'C1', premium: !!opt('premium'),
      collections: String(opt('collection') || 'world').split(','), description: { uk: '', ru: '', en: '' },
    };
    const catFile = path.join(__dirname, 'catalog.json');
    const cat = JSON.parse(fs.readFileSync(catFile, 'utf8')).filter((c) => c.id !== id);
    cat.push(entry);
    fs.writeFileSync(catFile, JSON.stringify(cat, null, 1));
    const idxFile = path.join(ROOT, 'app', 'books', 'index.json');
    const idx = JSON.parse(fs.readFileSync(idxFile, 'utf8')).filter((b) => b.id !== id);
    idx.push({ ...entry, words, chapters: chapters.length, source: { name: 'Project Gutenberg', url: `https://www.gutenberg.org/ebooks/${num}` } });
    fs.writeFileSync(idxFile, JSON.stringify(idx, null, 1));
    console.log(`✓ ${entry.title} (${words} слів, ${chapters.length} розд.). Додайте опис у tools/catalog.json і запустіть npm run covers.`);
    return;
  }
  console.log('Команди: search <текст> | add <номер> --id slug --collection slavic --level C1 [--premium]');
})().catch((e) => { console.error('✗ ' + e.message); process.exit(1); });

module.exports = { textToChapters, people, PD_YEAR };
