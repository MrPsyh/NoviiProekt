#!/usr/bin/env node
// Чистка текстів з Project Gutenberg: прибирає примітки транскрибувальника, службову розмітку
// (~розрядка~, =антиква=, +---+ рамки), титульні сторінки, зливає дрібні «розділи».
//   node tools/clean-gutenberg.js
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const DIR = path.join(__dirname, '..', 'app', 'books');
const wc = (s) => (s.match(/[\p{L}\p{N}]+/gu) || []).length;
const JUNK = /^(\+[-=]{5,}|\|\s|Anmerkungen? zur Transkription|Anmerkung des Transkribenten|Transcriber|Produced by|E-text prepared|Diese(s)? (Buch|E-Book|Text) wurde|Inhalt(sverzeichnis)?\.?$|Ende\.?$|\[Illustration|Druck von|Verlag von)/i;

const idx = JSON.parse(fs.readFileSync(path.join(DIR, 'index.json'), 'utf8'));
for (const b of idx.filter((x) => x.gutenberg)) {
  const f = path.join(DIR, b.id + '.json');
  if (!fs.existsSync(f)) continue;
  const book = JSON.parse(fs.readFileSync(f, 'utf8'));
  let chapters = book.chapters.map((c) => {
    const paragraphs = [];
    for (let p of c.paragraphs) {
      if (/^Anmerkungen? zur Transkription/i.test(p) && paragraphs.length > 3) break; // хвіст з примітками
      p = p.replace(/~([^~\n]+)~/g, '$1').replace(/=([^=\n]+)=/g, '$1').replace(/\{([^}\n]+)\}/g, '$1').replace(/\[(\d+)\]/g, '').replace(/[ \t]+/g, ' ').trim();
      if (!p || JUNK.test(p) || /^[-*=_.\s]+$/.test(p)) continue;
      paragraphs.push(p);
    }
    return { title: (c.title || '').replace(/[~=_]/g, '').trim(), paragraphs };
  }).filter((c) => c.paragraphs.length);
  // титульна сторінка й дрібні розділи — злити з наступним
  const merged = [];
  for (const c of chapters) {
    const prev = merged[merged.length - 1];
    if (prev && wc(prev.paragraphs.join(' ')) < 90) { prev.paragraphs.push(...c.paragraphs); prev.title = c.title || prev.title; }
    else merged.push(c);
  }
  if (merged.length > 1 && wc(merged[0].paragraphs.join(' ')) < 150) merged.shift();
  // заголовки капсом → звичайний регістр
  for (const c of merged) if (c.title && c.title === c.title.toUpperCase() && /[A-ZÄÖÜ]{3}/.test(c.title)) c.title = c.title.charAt(0) + c.title.slice(1).toLowerCase();
  fs.writeFileSync(f, JSON.stringify({ ...book, chapters: merged }));
  b.chapters = merged.length;
  b.words = merged.reduce((n, c) => n + wc(c.paragraphs.join(' ')), 0);
  console.log(`${b.id}: ${merged.length} розд., ${b.words} слів`);
}
fs.writeFileSync(path.join(DIR, 'index.json'), JSON.stringify(idx, null, 1));
