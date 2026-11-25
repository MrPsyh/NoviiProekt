// Переводчик с несколькими провайдерами:
//  1) Google Gemini — точный перевод с учётом контекста (нужен API-ключ пользователя);
//  2) MyMemory — бесплатный онлайн-перевод без ключа (лимит ~5000 символов/день);
//  3) встроенный мини-словарь — работает офлайн для частых слов.
// Результаты кешируются в localStorage.
import * as store from './store.js';
import { MINI_DICT } from '../data/mini-dict.js';
import { langName } from './i18n.js';

const CACHE_KEY = 'lesefreund:trcache';
let cache = {};
try {
  cache = JSON.parse(localStorage.getItem(CACHE_KEY) || '{}');
} catch {
  cache = {};
}
function saveCache() {
  const keys = Object.keys(cache);
  if (keys.length > 3000) for (const k of keys.slice(0, 1000)) delete cache[k];
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(cache));
  } catch {}
}

/**
 * @param {string} text  немецкий текст (слово или фраза)
 * @param {object} opts  { context?: string — предложение, в котором стоит слово }
 * @returns {Promise<{text: string, note?: string, provider: string}>}
 */
export async function translate(text, { context = '' } = {}) {
  const target = store.get('targetLang') || 'en';
  const mode = store.get('translator');
  const key = store.get('geminiKey');
  const isWord = !/\s/.test(text.trim());
  const cacheKey = `${target}|${mode}|${text}|${isWord ? context : ''}`;
  if (cache[cacheKey]) return cache[cacheKey];

  const chain = [];
  if (mode === 'gemini' || (mode === 'auto' && key)) chain.push(gemini);
  if (mode === 'free' || mode === 'auto' || mode === 'gemini') chain.push(myMemory);
  chain.push(offline);

  let lastErr;
  for (const provider of chain) {
    try {
      const res = await provider(text, target, context, isWord);
      if (res && res.text) {
        if (res.provider !== 'offline') {
          cache[cacheKey] = res;
          saveCache();
        }
        return res;
      }
    } catch (e) {
      lastErr = e;
      console.warn('[translate]', provider.name, e);
    }
  }
  throw lastErr || new Error('no translation');
}

async function gemini(text, target, context, isWord) {
  const key = store.get('geminiKey');
  if (!key) throw new Error('no gemini key');
  const model = store.get('geminiModel') || 'gemini-2.5-flash';
  const lang = langName(target);
  const prompt = isWord
    ? `You are a German teacher. Translate the German word "${text}" into ${lang}, as it is used in this sentence: "${context}".
Reply ONLY with JSON: {"translation": "...", "note": "..."} where "note" (in ${lang}) gives the base form (infinitive / nominative with article der/die/das), part of speech and, if useful, a very short grammar hint. Keep note under 20 words.`
    : `Translate this German text into ${lang}. Keep the meaning, style and tone. Reply ONLY with JSON: {"translation": "..."}.
Text: """${text}"""`;
  const res = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-goog-api-key': key },
      body: JSON.stringify({
        contents: [{ parts: [{ text: prompt }] }],
        generationConfig: { temperature: 0.2, responseMimeType: 'application/json' },
      }),
    },
  );
  if (!res.ok) throw new Error(`gemini ${res.status}`);
  const data = await res.json();
  const raw = data?.candidates?.[0]?.content?.parts?.map((p) => p.text).join('') || '';
  const json = JSON.parse(raw.replace(/^```(json)?|```$/g, '').trim());
  return { text: String(json.translation || '').trim(), note: json.note ? String(json.note) : '', provider: 'gemini' };
}

async function myMemory(text, target) {
  const url = `https://api.mymemory.translated.net/get?q=${encodeURIComponent(text)}&langpair=de|${target}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`mymemory ${res.status}`);
  const data = await res.json();
  const out = data?.responseData?.translatedText;
  if (!out || data.responseStatus !== 200 || /MYMEMORY WARNING|QUERY LENGTH LIMIT/i.test(out)) {
    throw new Error('mymemory: ' + (data?.responseDetails || 'empty'));
  }
  return { text: decodeEntities(out), provider: 'mymemory' };
}

async function offline(text, target, _context, isWord) {
  if (!isWord) return null;
  const entry = MINI_DICT[text.toLowerCase()];
  if (!entry) return null;
  const tr = entry[target] || entry.en;
  return tr ? { text: tr, provider: 'offline' } : null;
}

function decodeEntities(s) {
  const el = document.createElement('textarea');
  el.innerHTML = s;
  return el.value;
}
