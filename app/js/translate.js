// Переклад: Google Translate.
//
// Порядок, у якому пробуємо джерела:
//  1) готовий словник книжок (app/dict/<мова>.json): миттєво й офлайн, якщо його зібрали скриптом
//     `npm run dict` (tools/build-dictionary.js);
//  2) кеш на пристрої: кожне слово перекладається лише один раз;
//  3) Google Translate:
//     • якщо в config.js вказано TRANSLATE_PROXY_URL — офіційний Google Cloud Translation API
//       через ваш сервер (ключ лежить на сервері, а не в застосунку; так рекомендовано для релізу);
//     • інакше — безкоштовний публічний endpoint Google (translate.googleapis.com, client=gtx).
//       Запит іде з телефону користувача, тож у кожного свій ліміт. Endpoint неофіційний:
//       Google може обмежити його будь-коли, тому для релізу варто підключити проксі;
//  4) MyMemory, запасний безкоштовний сервіс;
//  5) вбудований міні-словник (офлайн).
import * as store from './store.js';
import { MINI_DICT } from '../data/mini-dict.js';
import { TRANSLATE_PROXY_URL } from './config.js';

const CACHE_KEY = 'lesefreund:trcache2';
let cache = {};
try { cache = JSON.parse(localStorage.getItem(CACHE_KEY) || '{}'); } catch { cache = {}; }
let saveTimer;
function remember(k, v) {
  cache[k] = v;
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    const keys = Object.keys(cache);
    if (keys.length > 5000) for (const key of keys.slice(0, 1500)) delete cache[key];
    try { localStorage.setItem(CACHE_KEY, JSON.stringify(cache)); } catch {}
  }, 300);
}

const bookDicts = {};
async function bookDict(lang) {
  if (!(lang in bookDicts)) {
    bookDicts[lang] = fetch(`dict/${lang}.json`).then((r) => (r.ok ? r.json() : {})).catch(() => ({}));
  }
  return bookDicts[lang];
}

/**
 * @param {string} text  німецький текст (слово або фраза)
 * @returns {Promise<{text: string, alts?: {pos: string, terms: string[]}[], provider: string}>}
 */
export async function translate(text, { from = 'de' } = {}) {
  text = text.trim();
  const target = store.get('targetLang') || 'en';
  const isWord = !/\s/.test(text) && from === 'de';
  const key = `${from}|${target}|${text}`;
  if (from === target) return { text, provider: 'same' };
  if (cache[key]) return cache[key];

  if (isWord) {
    const d = await bookDict(target);
    const hit = d[text] || d[text.toLowerCase()];
    if (hit) return { text: hit, provider: 'dictionary' };
  }

  const chain = TRANSLATE_PROXY_URL ? [googleProxy, googleFree, myMemory] : [googleFree, myMemory];
  let lastErr;
  for (const fn of chain) {
    try {
      const res = await fn(text, target, isWord, from);
      if (res?.text) { remember(key, res); return res; }
    } catch (e) {
      lastErr = e;
      console.warn('[translate]', fn.name, e.message);
    }
  }
  const off = isWord && MINI_DICT[text.toLowerCase()];
  if (off) return { text: off[target] || off.en, provider: 'offline' };
  throw lastErr || new Error('no translation');
}

function withTimeout(ms = 8000) {
  const c = new AbortController();
  setTimeout(() => c.abort(), ms);
  return c.signal;
}

async function googleFree(text, target, isWord, from = 'de') {
  const p = new URLSearchParams({ client: 'gtx', sl: from, tl: target, dj: '1', q: text });
  p.append('dt', 't');
  if (isWord) p.append('dt', 'bd'); // словникові варіанти + частина мови
  const res = await fetch('https://translate.googleapis.com/translate_a/single?' + p, { signal: withTimeout() });
  if (!res.ok) throw new Error('google ' + res.status);
  const data = await res.json();
  const out = (data.sentences || []).map((s) => s.trans || '').join('').trim();
  const alts = (data.dict || []).map((d) => ({ pos: d.pos, terms: (d.terms || []).slice(0, 5) }));
  return { text: out, alts, provider: 'google' };
}

async function googleProxy(text, target, _w, from = 'de') {
  const res = await fetch(TRANSLATE_PROXY_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ q: text, source: from, target }),
    signal: withTimeout(),
  });
  if (!res.ok) throw new Error('proxy ' + res.status);
  const data = await res.json();
  return { text: decode(data.translation || data?.data?.translations?.[0]?.translatedText || ''), provider: 'google' };
}

async function myMemory(text, target, _w, from = 'de') {
  const res = await fetch(
    `https://api.mymemory.translated.net/get?q=${encodeURIComponent(text)}&langpair=${from}|${target}`,
    { signal: withTimeout() },
  );
  const data = await res.json();
  const out = data?.responseData?.translatedText;
  if (!out || data.responseStatus !== 200 || /MYMEMORY WARNING/i.test(out)) throw new Error('mymemory');
  return { text: decode(out), provider: 'mymemory' };
}

function decode(s) {
  const el = document.createElement('textarea');
  el.innerHTML = s;
  return el.value;
}
