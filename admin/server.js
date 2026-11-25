#!/usr/bin/env node
// Локальная админ-панель Lesefreund: создание промокодов и публикация «пака» в приложение.
// Без внешних зависимостей. Запуск: `npm run admin` (или `node admin/server.js`).
// Открывается на компьютере (http://localhost:4000) и на телефоне в той же Wi‑Fi сети
// (адрес будет выведен в консоль).
'use strict';
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const os = require('node:os');

const PORT = Number(process.env.ADMIN_PORT || 4000);
const HOST = process.env.ADMIN_HOST || '0.0.0.0';
const DATA_DIR = path.join(__dirname, 'data');
const CODES_FILE = path.join(DATA_DIR, 'codes.json');
const CONFIG_FILE = path.join(DATA_DIR, 'config.json');
const PACK_FILE = path.resolve(process.env.PACK_FILE || path.join(__dirname, '..', 'app', 'promo-pack.json'));
const PEPPER = 'lesefreund-v1:'; // должен совпадать с app/js/promo.js
const ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; // без 0/O/1/I — чтобы не путать
const UNIT_MINUTES = { minutes: 1, hours: 60, days: 1440, weeks: 10080, months: 43200 };

fs.mkdirSync(DATA_DIR, { recursive: true });

// ---------- хранилище ----------
const readJson = (f, def) => {
  try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch { return def; }
};
const writeJson = (f, v) => {
  const tmp = f + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(v, null, 2));
  fs.renameSync(tmp, f);
};
let codes = readJson(CODES_FILE, []);
const saveCodes = () => writeJson(CODES_FILE, codes);

// ---------- пароль ----------
function hashPassword(pw, salt = crypto.randomBytes(16).toString('hex')) {
  return { salt, hash: crypto.scryptSync(pw, salt, 32).toString('hex') };
}
let config = readJson(CONFIG_FILE, null);
let firstRunPassword = null;
if (process.env.ADMIN_PASSWORD) {
  config = hashPassword(process.env.ADMIN_PASSWORD);
} else if (!config) {
  firstRunPassword = crypto.randomBytes(6).toString('base64url');
  config = hashPassword(firstRunPassword);
  writeJson(CONFIG_FILE, config);
}
function checkPassword(pw) {
  const h = crypto.scryptSync(String(pw || ''), config.salt, 32);
  return crypto.timingSafeEqual(h, Buffer.from(config.hash, 'hex'));
}

// ---------- сессии и защита от перебора ----------
const sessions = new Map(); // token -> expires
const SESSION_MS = 7 * 24 * 3600 * 1000;
const attempts = new Map(); // ip -> { n, until }
function isAuthed(req) {
  const m = /(?:^|;\s*)lf_admin=([\w-]+)/.exec(req.headers.cookie || '');
  const exp = m && sessions.get(m[1]);
  return Boolean(exp && exp > Date.now());
}

// ---------- промокоды ----------
function normalize(code) {
  return String(code || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
}
const hashCode = (code) => crypto.createHash('sha256').update(PEPPER + normalize(code)).digest('hex');
function randomBlock(n) {
  let s = '';
  for (let i = 0; i < n; i++) s += ALPHABET[crypto.randomInt(ALPHABET.length)];
  return s;
}
function generateCode(prefix) {
  const existing = new Set(codes.map((c) => normalize(c.code)));
  for (;;) {
    const code = [prefix, randomBlock(4), randomBlock(4)].filter(Boolean).join('-');
    if (!existing.has(normalize(code))) return code;
  }
}
function buildPack() {
  return {
    format: 1,
    generatedAt: new Date().toISOString(),
    codes: codes
      .filter((c) => !c.disabled)
      .map((c) => ({ id: c.id, h: hashCode(c.code), minutes: c.minutes, validUntil: c.validUntil || null })),
    // відкликані коди: застосунок знімає Premium, виданий цими кодами
    revoked: codes.filter((c) => c.disabled).map((c) => c.id),
  };
}
function packIsStale() {
  const cur = readJson(PACK_FILE, { codes: [] });
  const a = JSON.stringify((cur.codes || []).map((c) => [c.id, c.h, c.minutes, c.validUntil]).sort());
  const b = JSON.stringify(buildPack().codes.map((c) => [c.id, c.h, c.minutes, c.validUntil]).sort());
  return a !== b;
}

// ---------- HTTP ----------
function send(res, status, body, headers = {}) {
  const isObj = typeof body === 'object' && !Buffer.isBuffer(body);
  res.writeHead(status, {
    'Content-Type': isObj ? 'application/json; charset=utf-8' : 'text/plain; charset=utf-8',
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
    ...headers,
  });
  res.end(isObj ? JSON.stringify(body) : body);
}
function readBody(req) {
  return new Promise((resolve, reject) => {
    let data = '';
    req.on('data', (c) => {
      data += c;
      if (data.length > 1e5) reject(new Error('too large'));
    });
    req.on('end', () => {
      try { resolve(data ? JSON.parse(data) : {}); } catch (e) { reject(e); }
    });
    req.on('error', reject);
  });
}
const csvCell = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;

async function handleApi(req, res, url) {
  const ip = req.socket.remoteAddress;

  if (url.pathname === '/api/login' && req.method === 'POST') {
    const a = attempts.get(ip) || { n: 0, until: 0 };
    if (a.until > Date.now()) return send(res, 429, { error: 'Слишком много попыток. Подождите 15 минут.' });
    const { password } = await readBody(req);
    if (!checkPassword(password)) {
      a.n += 1;
      if (a.n >= 8) Object.assign(a, { n: 0, until: Date.now() + 15 * 60_000 });
      attempts.set(ip, a);
      return send(res, 401, { error: 'Неверный пароль' });
    }
    attempts.delete(ip);
    const token = crypto.randomBytes(24).toString('base64url');
    sessions.set(token, Date.now() + SESSION_MS);
    return send(res, 200, { ok: true }, {
      'Set-Cookie': `lf_admin=${token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=${SESSION_MS / 1000}`,
    });
  }
  if (url.pathname === '/api/logout' && req.method === 'POST') {
    const m = /(?:^|;\s*)lf_admin=([\w-]+)/.exec(req.headers.cookie || '');
    if (m) sessions.delete(m[1]);
    return send(res, 200, { ok: true }, { 'Set-Cookie': 'lf_admin=; Path=/; Max-Age=0' });
  }

  if (!isAuthed(req)) return send(res, 401, { error: 'auth' });

  if (url.pathname === '/api/codes' && req.method === 'GET') {
    return send(res, 200, { codes, stale: packIsStale(), packFile: PACK_FILE });
  }
  if (url.pathname === '/api/codes' && req.method === 'POST') {
    const b = await readBody(req);
    const count = Math.min(500, Math.max(1, parseInt(b.count, 10) || 1));
    const prefix = normalize(b.prefix).slice(0, 10);
    let minutes;
    if (b.unit === 'forever') minutes = -1;
    else {
      const mult = UNIT_MINUTES[b.unit];
      const value = Number(b.value);
      if (!mult || !(value > 0)) return send(res, 400, { error: 'Неверная длительность' });
      minutes = Math.round(value * mult);
    }
    const validUntil = b.validUntil ? new Date(b.validUntil).toISOString() : null;
    const custom = b.customCode ? String(b.customCode).toUpperCase().trim() : '';
    if (custom) {
      if (normalize(custom).length < 4) return send(res, 400, { error: 'Код слишком короткий (минимум 4 символа)' });
      if (codes.some((c) => normalize(c.code) === normalize(custom))) return send(res, 400, { error: 'Такой код уже есть' });
    }
    const created = [];
    for (let i = 0; i < (custom ? 1 : count); i++) {
      const c = {
        id: crypto.randomBytes(5).toString('hex'),
        code: custom || generateCode(prefix),
        minutes,
        validUntil,
        note: String(b.note || '').slice(0, 200),
        createdAt: new Date().toISOString(),
        disabled: false,
      };
      codes.unshift(c);
      created.push(c);
    }
    saveCodes();
    return send(res, 200, { created });
  }
  const m = /^\/api\/codes\/([a-f0-9]+)$/.exec(url.pathname);
  if (m && req.method === 'PATCH') {
    const c = codes.find((x) => x.id === m[1]);
    if (!c) return send(res, 404, { error: 'not found' });
    const b = await readBody(req);
    if (typeof b.disabled === 'boolean') c.disabled = b.disabled;
    if (typeof b.note === 'string') c.note = b.note.slice(0, 200);
    saveCodes();
    return send(res, 200, { code: c });
  }
  if (m && req.method === 'DELETE') {
    codes = codes.filter((x) => x.id !== m[1]);
    saveCodes();
    return send(res, 200, { ok: true });
  }
  if (url.pathname === '/api/publish' && req.method === 'POST') {
    const pack = buildPack();
    writeJson(PACK_FILE, pack);
    return send(res, 200, { ok: true, count: pack.codes.length, file: PACK_FILE });
  }
  if (url.pathname === '/api/export.csv' && req.method === 'GET') {
    const rows = [['code', 'minutes', 'validUntil', 'note', 'createdAt', 'disabled']]
      .concat(codes.map((c) => [c.code, c.minutes, c.validUntil, c.note, c.createdAt, c.disabled]));
    return send(res, 200, '﻿' + rows.map((r) => r.map(csvCell).join(';')).join('\r\n'), {
      'Content-Type': 'text/csv; charset=utf-8',
      'Content-Disposition': 'attachment; filename="promocodes.csv"',
    });
  }
  return send(res, 404, { error: 'not found' });
}

const INDEX = path.join(__dirname, 'public', 'index.html');
const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://x');
  try {
    if (url.pathname.startsWith('/api/')) return await handleApi(req, res, url);
    if (url.pathname === '/' || url.pathname === '/index.html') {
      return send(res, 200, fs.readFileSync(INDEX), {
        'Content-Type': 'text/html; charset=utf-8',
        'X-Frame-Options': 'DENY',
      });
    }
    send(res, 404, 'Not found');
  } catch (e) {
    console.error(e);
    send(res, 500, { error: String(e.message || e) });
  }
});

server.listen(PORT, HOST, () => {
  console.log('\n  Lesefreund — админ-панель промокодов\n');
  console.log(`  На этом компьютере:  http://localhost:${PORT}`);
  for (const list of Object.values(os.networkInterfaces())) {
    for (const a of list || []) {
      if (a.family === 'IPv4' && !a.internal) console.log(`  С телефона (Wi‑Fi):  http://${a.address}:${PORT}`);
    }
  }
  if (firstRunPassword) {
    console.log(`\n  Пароль для входа (первый запуск): ${firstRunPassword}`);
    console.log('  Сохраните его! Сменить: удалите admin/data/config.json или задайте ADMIN_PASSWORD.');
  } else if (process.env.ADMIN_PASSWORD) {
    console.log('\n  Пароль: из переменной ADMIN_PASSWORD');
  }
  console.log(`\n  Пак промокодов публикуется в: ${PACK_FILE}\n`);
});
