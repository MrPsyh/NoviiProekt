#!/usr/bin/env node
// Готовий словник книжок: перекладає всі слова, що трапляються в app/books/*.json, і кладе
// результат у app/dict/<мова>.json. Тоді переклад слова за дотиком миттєвий і працює офлайн.
//
//   GOOGLE_TRANSLATE_KEY=... npm run dict -- uk ru en      ← офіційний Google Cloud API (рекомендовано)
//   npm run dict -- uk                                     ← без ключа: публічний endpoint (повільно, з паузами)
//
// Скрипт можна переривати: уже перекладене зберігається і наступного разу пропускається.
// Вартість з ключем: усі книжки ≈ 60–80 тис. унікальних слів ≈ 0,6 млн символів на мову (~12 $ за мову
// після безкоштовних 500 тис. символів на місяць).
'use strict';
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.join(__dirname, '..', 'app');
const KEY = process.env.GOOGLE_TRANSLATE_KEY;
const langs = process.argv.slice(2).filter((a) => !a.startsWith('-'));
const MIN_COUNT = Number(process.env.MIN_COUNT || 1); // перекладати лише слова, що трапились ≥ N разів
if (!langs.length) { console.log('Вкажіть мови: npm run dict -- uk ru en'); process.exit(1); }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// 1. збираємо слова
const counts = new Map();
for (const f of fs.readdirSync(path.join(ROOT, 'books'))) {
  if (f === 'index.json' || !f.endsWith('.json')) continue;
  const book = JSON.parse(fs.readFileSync(path.join(ROOT, 'books', f), 'utf8'));
  for (const ch of book.chapters) for (const p of ch.paragraphs)
    for (const m of p.matchAll(/[\p{L}\p{M}][\p{L}\p{M}\p{N}'’-]*/gu)) {
      const w = m[0].replace(/^[-'’]+|[-'’]+$/g, '');
      if (w.length > 1) counts.set(w, (counts.get(w) || 0) + 1);
    }
}
const words = [...counts].filter(([, n]) => n >= MIN_COUNT).sort((a, b) => b[1] - a[1]).map(([w]) => w);
console.log(`Унікальних слів: ${words.length}`);

async function googleOfficial(batch, tl) {
  const r = await fetch(`https://translation.googleapis.com/language/translate/v2?key=${KEY}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ q: batch, source: 'de', target: tl, format: 'text' }),
  });
  if (!r.ok) throw new Error('google ' + r.status + ' ' + (await r.text()).slice(0, 200));
  return (await r.json()).data.translations.map((t) => t.translatedText);
}
async function googleFree(batch, tl) {
  // кілька слів одним запитом, кожне з нового рядка
  const q = batch.join('\n');
  const r = await fetch(`https://translate.googleapis.com/translate_a/single?client=gtx&sl=de&tl=${tl}&dt=t&q=${encodeURIComponent(q)}`);
  if (r.status === 429 || r.status === 302) throw Object.assign(new Error('rate'), { rate: true });
  if (!r.ok) throw new Error('google ' + r.status);
  const out = (await r.json())[0].map((s) => s[0]).join('').split('\n').map((s) => s.trim());
  if (out.length !== batch.length) throw new Error('lines mismatch');
  return out;
}

(async () => {
  fs.mkdirSync(path.join(ROOT, 'dict'), { recursive: true });
  for (const tl of langs) {
    const file = path.join(ROOT, 'dict', tl + '.json');
    const dict = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) : {};
    const todo = words.filter((w) => !(w in dict));
    console.log(`[${tl}] залишилось ${todo.length}`);
    const size = KEY ? 100 : 40;
    for (let i = 0; i < todo.length; i += size) {
      const batch = todo.slice(i, i + size);
      try {
        const tr = KEY ? await googleOfficial(batch, tl) : await googleFree(batch, tl);
        batch.forEach((w, k) => { if (tr[k]) dict[w] = tr[k]; });
      } catch (e) {
        console.log(`  пауза (${e.message})`);
        await sleep(e.rate ? 60_000 : 5000);
        i -= size;
        continue;
      }
      if ((i / size) % 10 === 0) { fs.writeFileSync(file, JSON.stringify(dict)); process.stdout.write(`  ${i + batch.length}/${todo.length}\r`); }
      if (!KEY) await sleep(1500);
    }
    fs.writeFileSync(file, JSON.stringify(dict));
    console.log(`[${tl}] готово: ${Object.keys(dict).length} слів`);
  }
})();
