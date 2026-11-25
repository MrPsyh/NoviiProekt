#!/usr/bin/env node
// Сервер-перекладач для релізу: застосунок → цей сервер → офіційний Google Cloud Translation API.
// Ключ Google лежить ТІЛЬКИ тут (змінна GOOGLE_TRANSLATE_KEY), у застосунок він не потрапляє.
// Кешує переклади на диск, тому одне й те саме слово оплачується лише раз для всіх користувачів.
// Ціна Google: перші 500 000 символів на місяць безкоштовно, далі близько 20 $ за 1 млн символів.
//
// Запуск:  GOOGLE_TRANSLATE_KEY=... node server/translate-proxy.js
// Потім у app/js/config.js:  TRANSLATE_PROXY_URL = 'https://ваш-домен/translate'
'use strict';
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');

const KEY = process.env.GOOGLE_TRANSLATE_KEY;
const PORT = Number(process.env.PORT || 8787);
const CACHE_FILE = path.join(__dirname, 'translate-cache.json');
if (!KEY) { console.error('Задайте GOOGLE_TRANSLATE_KEY'); process.exit(1); }

let cache = {};
try { cache = JSON.parse(fs.readFileSync(CACHE_FILE, 'utf8')); } catch {}
let dirty = false;
setInterval(() => { if (dirty) { fs.writeFileSync(CACHE_FILE, JSON.stringify(cache)); dirty = false; } }, 10_000);

const hits = new Map(); // простий ліміт: 120 запитів на хвилину з однієї IP
function limited(ip) {
  const now = Date.now();
  const h = (hits.get(ip) || []).filter((t) => now - t < 60_000);
  h.push(now);
  hits.set(ip, h);
  return h.length > 120;
}

http.createServer(async (req, res) => {
  const cors = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'Content-Type', 'Access-Control-Allow-Methods': 'POST, OPTIONS' };
  if (req.method === 'OPTIONS') return res.writeHead(204, cors).end();
  if (req.method !== 'POST') return res.writeHead(404, cors).end();
  if (limited(req.socket.remoteAddress)) return res.writeHead(429, cors).end();
  let body = '';
  for await (const c of req) { body += c; if (body.length > 20_000) return res.writeHead(413, cors).end(); }
  try {
    const { q, target, source = 'de' } = JSON.parse(body);
    if (!q || !/^[a-z]{2,3}(-[A-Za-z]+)?$/.test(target) || q.length > 5000) throw new Error('bad request');
    const k = `${source}|${target}|${q}`;
    if (!cache[k]) {
      const r = await fetch(`https://translation.googleapis.com/language/translate/v2?key=${KEY}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ q, source, target, format: 'text' }),
      });
      if (!r.ok) throw new Error('google ' + r.status);
      cache[k] = (await r.json()).data.translations[0].translatedText;
      dirty = true;
    }
    res.writeHead(200, { ...cors, 'Content-Type': 'application/json' }).end(JSON.stringify({ translation: cache[k] }));
  } catch (e) {
    res.writeHead(400, { ...cors, 'Content-Type': 'application/json' }).end(JSON.stringify({ error: e.message }));
  }
}).listen(PORT, () => console.log(`translate-proxy: http://localhost:${PORT}`));
