// Простое хранилище поверх localStorage. Всё лежит под одним ключом.
const KEY = 'lesefreund:v1';

const DEFAULTS = {
  onboarded: false,
  targetLang: null, // язык перевода, выбирается при первом запуске
  uiLang: null,
  fontSize: 19,
  theme: 'auto',
  translator: 'auto', // auto | free | gemini | offline
  geminiKey: '',
  geminiModel: 'gemini-2.5-flash',
  premiumUntil: 0, // timestamp (ms); Infinity не сериализуется, поэтому -1 = навсегда
  premiumSource: null,
  redeemed: [], // id использованных промокодов
  vocab: [], // { de, tr, lang, context, bookId, at }
  progress: {}, // bookId -> { scroll: 0..1 }
};

let state = load();

function load() {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? { ...DEFAULTS, ...JSON.parse(raw) } : { ...DEFAULTS };
  } catch {
    return { ...DEFAULTS };
  }
}

function persist() {
  try {
    localStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    /* приватный режим / переполнено — работаем в памяти */
  }
}

export const get = (k) => state[k];
export function set(k, v) {
  state[k] = v;
  persist();
}
export function update(k, fn) {
  state[k] = fn(state[k]);
  persist();
}
export function resetAll() {
  state = { ...DEFAULTS };
  persist();
}

export const FOREVER = -1;
export function isPremium() {
  const u = state.premiumUntil;
  return u === FOREVER || u > Date.now();
}
