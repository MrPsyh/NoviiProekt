#!/usr/bin/env node
// Для книжок без справжньої обкладинки (скану видання або старовинної ілюстрації) малюємо стриману
// «тканинну палітурку» з золотим тисненням назви й автора — як у старих бібліотечних виданнях.
// Без вигаданих малюнків. Результат: app/covers/<id>.svg.   npm run covers
'use strict';
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.join(__dirname, '..', 'app');
const books = JSON.parse(fs.readFileSync(path.join(ROOT, 'books', 'index.json'), 'utf8'));
fs.mkdirSync(path.join(ROOT, 'covers'), { recursive: true });
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
const hue = (id) => [...id].reduce((a, c) => (a * 31 + c.charCodeAt(0)) % 360, 7);

function wrap(text, max) {
  const lines = []; let cur = '';
  for (const w of text.split(/\s+/)) {
    if ((cur + ' ' + w).trim().length > max && cur) { lines.push(cur); cur = w; } else cur = (cur + ' ' + w).trim();
  }
  if (cur) lines.push(cur);
  return lines;
}

function cover(b) {
  const h = hue(b.id);
  const title = b.title.replace(/\s*\(.*\)$/, '');
  const lines = wrap(title, title.length > 30 ? 16 : 13).slice(0, 5);
  const fs = lines.length > 3 ? 24 : 30;
  const y0 = 205 - (lines.length - 1) * fs * 0.6;
  const tl = lines.map((l, i) => `<text x="150" y="${y0 + i * fs * 1.2}" text-anchor="middle">${esc(l)}</text>`).join('');
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 450" width="300" height="450">
<defs>
  <linearGradient id="c" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="hsl(${h} 42% 30%)"/><stop offset="1" stop-color="hsl(${h} 48% 15%)"/></linearGradient>
  <pattern id="w" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="2" height="5" fill="#fff" opacity=".035"/></pattern>
  <linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f6e3ae"/><stop offset="1" stop-color="#c79a4e"/></linearGradient>
</defs>
<rect width="300" height="450" fill="url(#c)"/><rect width="300" height="450" fill="url(#w)"/>
<rect x="0" y="0" width="16" height="450" fill="#000" opacity=".22"/><rect x="16" y="0" width="2" height="450" fill="#fff" opacity=".06"/>
<rect x="34" y="30" width="248" height="390" fill="none" stroke="url(#g)" stroke-width="1.5" opacity=".75"/>
<rect x="40" y="36" width="236" height="378" fill="none" stroke="url(#g)" stroke-width=".7" opacity=".5"/>
<text x="158" y="92" text-anchor="middle" font-family="Georgia,'Times New Roman',serif" font-size="13" letter-spacing="3" fill="url(#g)">${esc(b.author.toUpperCase())}</text>
<path d="M118 112h80" stroke="url(#g)" stroke-width="1"/>
<g font-family="Georgia,'Times New Roman',serif" font-weight="700" font-size="${fs}" fill="url(#g)">${tl}</g>
<text x="158" y="352" text-anchor="middle" font-size="22" fill="url(#g)">❦</text>
${b.year ? `<text x="158" y="392" text-anchor="middle" font-family="Georgia,serif" font-size="12" letter-spacing="4" fill="url(#g)" opacity=".8">${esc(String(b.year).replace(/^\D*(\d{4}).*$/, '$1'))}</text>` : ''}
</svg>`;
}

for (const b of books) fs.writeFileSync(path.join(ROOT, 'covers', b.id + '.svg'), cover(b));
console.log(`Палітурок: ${books.length}`);
