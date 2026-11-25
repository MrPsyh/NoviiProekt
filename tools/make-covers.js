#!/usr/bin/env node
// Генерує власні обкладинки (SVG) для всіх книжок з app/books/index.json → app/covers/<id>.svg.
// Обкладинки видавництв захищені авторським правом, тому малюємо свої: вони легкі,
// чіткі на будь-якому екрані й лежать локально в застосунку (працюють офлайн).
// Запуск: npm run covers
'use strict';
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.join(__dirname, '..', 'app');
const books = JSON.parse(fs.readFileSync(path.join(ROOT, 'books', 'index.json'), 'utf8'));
const remoteFile = path.join(ROOT, 'books', 'remote.json');
if (fs.existsSync(remoteFile)) books.push(...JSON.parse(fs.readFileSync(remoteFile, 'utf8')));
fs.mkdirSync(path.join(ROOT, 'covers'), { recursive: true });

// Палітри за колекціями: [фон1, фон2, акцент, текст]
const PALETTES = {
  graded: [['#2a9d8f', '#1d6f66', '#e9c46a', '#fff'], ['#f4a261', '#c8743a', '#264653', '#fff'], ['#8ecae6', '#219ebc', '#023047', '#023047']],
  kids: [['#ffb703', '#fb8500', '#023047', '#023047'], ['#ff8fab', '#fb6f92', '#fff', '#3d0b1e'], ['#90be6d', '#43aa8b', '#f9c74f', '#fff'], ['#bde0fe', '#a2d2ff', '#ef476f', '#1d3557']],
  'school-de': [['#1d3557', '#0b1d33', '#e63946', '#f1faee'], ['#3d405b', '#24263a', '#f2cc8f', '#f4f1de'], ['#283618', '#1a240f', '#dda15e', '#fefae0']],
  'school-ua': [['#005bbb', '#003f86', '#ffd500', '#fff'], ['#264653', '#13262e', '#e9c46a', '#fff']],
  world: [['#6d597a', '#463950', '#eaac8b', '#fff'], ['#355070', '#1f3045', '#e56b6f', '#fff'], ['#5f0f40', '#3a0827', '#fb8b24', '#fff']],
  slavic: [['#7f0000', '#4d0000', '#f2d0a4', '#fff5e6'], ['#22333b', '#0e1518', '#c6ac8f', '#eae0d5']],
  ukraine: [['#005bbb', '#002f62', '#ffd500', '#fff'], ['#ffd500', '#e0b800', '#005bbb', '#002f62']],
  japan: [['#f8f4ec', '#e9e0cf', '#bc002d', '#1b1b1b'], ['#1b1b1b', '#000', '#bc002d', '#f8f4ec']],
  poetry: [['#cdb4db', '#a98fbf', '#fff', '#2b2d42'], ['#2b2d42', '#14151f', '#ef233c', '#edf2f4']],
};

function hash(s) {
  let h = 2166136261;
  for (const c of s) h = Math.imul(h ^ c.codePointAt(0), 16777619);
  return h >>> 0;
}
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);

function wrap(text, max) {
  const words = text.split(/\s+/);
  const lines = [];
  let cur = '';
  for (const w of words) {
    if ((cur + ' ' + w).trim().length > max && cur) { lines.push(cur); cur = w; } else cur = (cur + ' ' + w).trim();
  }
  if (cur) lines.push(cur);
  return lines;
}

function pattern(kind, accent, rnd) {
  const r = (n) => (rnd() * n) | 0;
  switch (kind) {
    case 0: // кола
      return Array.from({ length: 6 }, (_, i) => `<circle cx="${40 + r(220)}" cy="${170 + r(200)}" r="${20 + r(60)}" fill="none" stroke="${accent}" stroke-width="${2 + (i % 3)}" opacity=".35"/>`).join('');
    case 1: // діагональні смуги
      return Array.from({ length: 9 }, (_, i) => `<path d="M${-100 + i * 50} 450L${150 + i * 50} 150" stroke="${accent}" stroke-width="14" opacity=".14"/>`).join('');
    case 2: // хвилі
      return Array.from({ length: 6 }, (_, i) => `<path d="M0 ${210 + i * 34}q37-22 75 0t75 0t75 0t75 0" fill="none" stroke="${accent}" stroke-width="5" opacity="${0.15 + i * 0.05}"/>`).join('');
    case 3: // крапки
      return Array.from({ length: 70 }, (_, i) => `<circle cx="${18 + (i % 10) * 30}" cy="${200 + ((i / 10) | 0) * 30}" r="${3 + r(4)}" fill="${accent}" opacity=".25"/>`).join('');
    case 4: // сонце / велика дуга
      return `<circle cx="${80 + r(140)}" cy="330" r="95" fill="${accent}" opacity=".85"/><circle cx="150" cy="330" r="150" fill="none" stroke="${accent}" stroke-width="2" opacity=".35"/>`;
    default: // трикутники-гори
      return `<path d="M-20 420L90 250L200 420z" fill="${accent}" opacity=".35"/><path d="M80 420L200 220L320 420z" fill="${accent}" opacity=".6"/>`;
  }
}

const OWL = (color, op) => `<g transform="translate(212 356) scale(1.25)" fill="${color}" opacity="${op}">
  <path d="M18 18l-4-11 11 7zM46 18l4-11-11 7z"/><ellipse cx="32" cy="38" rx="20" ry="23"/></g>`;

function cover(b) {
  const pal = PALETTES[b.collections[0]] || PALETTES.world;
  const h = hash(b.id);
  const [bg1, bg2, accent, fg] = pal[h % pal.length];
  let seed = h;
  const rnd = () => ((seed = Math.imul(seed ^ (seed >>> 15), 2246822507) >>> 0) % 10000) / 10000;
  const kind = (h >>> 8) % 6;
  const title = b.title.replace(/\s*\(.*\)$/, '');
  const maxChars = title.length > 40 ? 15 : 12;
  const lines = wrap(title, maxChars).slice(0, 5);
  const fs = lines.length > 3 ? 26 : lines.some((l) => l.length > 10) ? 30 : 36;
  const tl = lines.map((l, i) => `<tspan x="24" dy="${i ? fs * 1.12 : 0}">${esc(l)}</tspan>`).join('');
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 450" width="300" height="450">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${bg1}"/><stop offset="1" stop-color="${bg2}"/></linearGradient></defs>
<rect width="300" height="450" fill="url(#g)"/>
${pattern(kind, accent, rnd)}
<rect x="0" y="0" width="10" height="450" fill="#000" opacity=".12"/>
<text x="24" y="44" font-family="system-ui,-apple-system,Segoe UI,Roboto,sans-serif" font-size="12" font-weight="700" letter-spacing="2.5" fill="${fg}" opacity=".8">${esc(b.author.toUpperCase())}</text>
<rect x="24" y="56" width="36" height="3" fill="${accent}"/>
<text y="${100 + fs}" font-family="Georgia,'Iowan Old Style','Times New Roman',serif" font-size="${fs}" font-weight="700" fill="${fg}">${tl}</text>
${OWL(fg, 0.12)}
<text x="24" y="426" font-family="system-ui,sans-serif" font-size="10" font-weight="800" letter-spacing="3" fill="${fg}" opacity=".7">LESEFREUND</text>
<rect x="232" y="20" width="46" height="24" rx="6" fill="${accent}"/>
<text x="255" y="37" text-anchor="middle" font-family="system-ui,sans-serif" font-size="13" font-weight="800" fill="${bg2}">${esc(b.level)}</text>
</svg>`;
}

for (const b of books) fs.writeFileSync(path.join(ROOT, 'covers', b.id + '.svg'), cover(b));
console.log(`Обкладинок створено: ${books.length}`);
