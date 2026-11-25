#!/usr/bin/env node
// Збирає справжні обкладинки: старовинна ілюстрація (app/covers/art/<id>.jpg, суспільне надбання)
// + назва й автор у стилі класичних видань → app/covers/<id>.jpg (600×900).
// Потрібен Playwright (npx playwright install chromium). Для книжок без ілюстрації лишається SVG.
//   node tools/compose-covers.js
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const ROOT = path.join(__dirname, '..', 'app');
const idxFile = path.join(ROOT, 'books', 'index.json');
const credits = fs.existsSync(path.join(ROOT, 'covers', 'credits.json')) ? JSON.parse(fs.readFileSync(path.join(ROOT, 'covers', 'credits.json'), 'utf8')) : {};
const font = (f) => 'data:font/woff2;base64,' + fs.readFileSync(path.join(ROOT, 'fonts', f)).toString('base64');
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);

// стиль за колекцією: «paper» — кремовий папір з рамкою (класика), «full» — ілюстрація на всю обкладинку (дитячі)
const STYLE = { kids: 'full', graded: 'full', poetry: 'paper' };
const PAPER = ['#f3ead7', '#efe4cc', '#ece6d8', '#f1e7dc'];
const INK = ['#7a1f1f', '#1d3557', '#2f4f2f', '#5b2a63', '#3b2f22'];

function html(b, img, colorful, original) {
  // чорно-білі гравюри — на «папір», кольорові картини — на всю обкладинку; оригінальні скани — як є
  const style = original ? 'orig' : colorful ? 'full' : 'paper';
  const h = [...b.id].reduce((a, c) => a + c.charCodeAt(0), 0);
  const paper = PAPER[h % PAPER.length], ink = INK[h % INK.length];
  const long = b.title.length > 26;
  return `<!doctype html><html><head><style>
  @font-face{font-family:L;src:url(${font('literata-latin-400-normal.woff2')})}
  @font-face{font-family:L;font-weight:700;src:url(${font('literata-latin-700-normal.woff2')})}
  @font-face{font-family:L;font-style:italic;src:url(${font('literata-latin-400-italic.woff2')})}
  *{margin:0;box-sizing:border-box} body{width:600px;height:900px;overflow:hidden;font-family:L,Georgia,serif}
  .full{position:relative;width:600px;height:900px;background:#222 url(${img}) center/cover}
  .full::after{content:'';position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.55) 0%,rgba(0,0,0,0) 34%,rgba(0,0,0,0) 62%,rgba(0,0,0,.6) 100%)}
  .full .t{position:absolute;z-index:2;left:40px;right:40px;top:44px;color:#fff;text-align:center;text-shadow:0 3px 14px rgba(0,0,0,.6)}
  .full .t h1{font-size:${long ? 50 : 66}px;line-height:1.02;font-weight:700;letter-spacing:-.5px}
  .full .a{position:absolute;z-index:2;bottom:40px;left:0;right:0;text-align:center;color:#fff;font-size:24px;letter-spacing:4px;text-transform:uppercase;text-shadow:0 2px 10px rgba(0,0,0,.6)}
  .paper{width:600px;height:900px;background:${paper};padding:34px;position:relative}
  .paper .frame{position:absolute;inset:20px;border:2px solid ${ink};opacity:.55}
  .paper .frame::after{content:'';position:absolute;inset:6px;border:1px solid ${ink}}
  .paper .a{margin-top:30px;text-align:center;color:${ink};font-size:21px;letter-spacing:3px;text-transform:uppercase}
  .paper h1{margin:14px 26px 0;text-align:center;color:${ink};font-size:${long ? 44 : 58}px;line-height:1.05;font-weight:700}
  .paper .orn{text-align:center;color:${ink};font-size:22px;margin:10px 0 16px;opacity:.8}
  .paper .img{position:absolute;left:58px;right:58px;bottom:70px;top:${long ? 330 : 280}px;background:url(${img}) center/cover;box-shadow:0 0 0 1px ${ink}55, 0 8px 20px rgba(0,0,0,.18)}
  .paper .y{position:absolute;left:0;right:0;bottom:34px;text-align:center;color:${ink};font-size:15px;letter-spacing:5px;opacity:.8}
  .lvl{position:absolute;z-index:3;right:26px;top:${style === 'full' ? 'auto' : '26px'};bottom:${style === 'full' ? '96px' : 'auto'};font:800 20px system-ui,sans-serif;background:#fff;color:#1d3557;border-radius:10px;padding:5px 12px;box-shadow:0 2px 8px rgba(0,0,0,.25)}
  </style></head><body>
  ${style === 'orig' ? `<div style="position:relative;width:600px;height:900px;overflow:hidden;background:#e9e2d3">
      <div style="position:absolute;inset:-40px;background:url(${img}) center/cover;filter:blur(24px) brightness(.85)"></div>
      <div style="position:absolute;inset:0;background:url(${img}) center/contain no-repeat;box-shadow:inset 0 0 0 1px rgba(0,0,0,.05)"></div></div>` : style === 'full'
    ? `<div class="full"><div class="t"><h1>${esc(b.title)}</h1></div><div class="a">${esc(b.author)}</div></div>`
    : `<div class="paper"><div class="frame"></div><div class="a">${esc(b.author)}</div><h1>${esc(b.title)}</h1><div class="orn">❦</div><div class="img"></div><div class="y">${esc(String(b.year || '').replace(/^\D*(\d{4}).*$/, '$1'))}</div></div>`}
  <div class="lvl">${esc(b.level)}</div></body></html>`;
}

(async () => {
  const idx = JSON.parse(fs.readFileSync(idxFile, 'utf8'));
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 600, height: 900 } });
  let n = 0;
  for (const b of idx) {
    const art = path.join(ROOT, 'covers', 'art', b.id + '.jpg');
    if (!fs.existsSync(art)) { b.cover = `covers/${b.id}.svg`; continue; }
    const img = 'data:image/jpeg;base64,' + fs.readFileSync(art).toString('base64');
    await page.setContent(`<img id="i" src="${img}">`, { waitUntil: 'load' });
    const colorful = await page.evaluate(() => {
      const i = document.getElementById('i'); const c = document.createElement('canvas'); c.width = 64; c.height = 64;
      const x = c.getContext('2d'); x.drawImage(i, 0, 0, 64, 64); const d = x.getImageData(0, 0, 64, 64).data; let s = 0;
      for (let k = 0; k < d.length; k += 4) s += Math.max(d[k], d[k + 1], d[k + 2]) - Math.min(d[k], d[k + 1], d[k + 2]);
      return s / (d.length / 4) > 28;
    });
    await page.setContent(html(b, img, colorful, credits[b.id]?.original), { waitUntil: 'load' });
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: path.join(ROOT, 'covers', b.id + '.jpg'), type: 'jpeg', quality: 84 });
    b.cover = `covers/${b.id}.jpg`;
    const c = credits[b.id];
    b.coverCredit = c ? { artist: c.artist, date: c.date, license: c.license, page: c.page } : null;
    n++;
  }
  await browser.close();
  fs.writeFileSync(idxFile, JSON.stringify(idx, null, 1));
  console.log(`Справжніх обкладинок: ${n} з ${idx.length}`);
})();
