#!/usr/bin/env node
// Ділить задовгі розділи книжок (app/books/*.json) на частини ~3500 слів, щоб читалка працювала плавно,
// і оновлює кількість розділів в index.json.   node tools/split-long.js
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const DIR = path.join(__dirname, '..', 'app', 'books');
const MAX = 3500;
const wc = (s) => (s.match(/[\p{L}\p{N}]+/gu) || []).length;

function split(chapters) {
  const out = [];
  for (const c of chapters) {
    const total = wc(c.paragraphs.join(' '));
    if (total <= MAX * 1.3) { out.push(c); continue; }
    const parts = Math.ceil(total / MAX);
    let part = [], n = 0, k = 1;
    const base = (c.title || '').replace(/\s*\(\d+\)$/, '');
    for (const p of c.paragraphs) {
      part.push(p); n += wc(p);
      if (n >= total / parts && k < parts) { out.push({ title: base ? `${base} (${k})` : '', paragraphs: part }); part = []; n = 0; k++; }
    }
    if (part.length) out.push({ title: base ? `${base} (${k})` : '', paragraphs: part });
  }
  return out;
}

const idxFile = path.join(DIR, 'index.json');
const idx = JSON.parse(fs.readFileSync(idxFile, 'utf8'));
for (const b of idx) {
  const f = path.join(DIR, b.id + '.json');
  if (!fs.existsSync(f)) continue;
  const book = JSON.parse(fs.readFileSync(f, 'utf8'));
  const chapters = split(book.chapters);
  if (chapters.length !== book.chapters.length) {
    fs.writeFileSync(f, JSON.stringify({ ...book, chapters }));
    console.log(`${b.id}: ${book.chapters.length} → ${chapters.length}`);
  }
  b.chapters = chapters.length;
}
fs.writeFileSync(idxFile, JSON.stringify(idx, null, 1));
