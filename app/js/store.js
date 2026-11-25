// Сховище поверх localStorage (усе під одним ключем). У нативному застосунку (Capacitor)
// localStorage WebView зберігається між запусками.
const KEY = 'lesefreund:v2';

const DEFAULTS = {
  onboarded: false,
  targetLang: null,
  uiLang: null,
  fontSize: 19,
  font: 'serif',
  theme: 'light', // light | sepia | grey | black
  speakOnTap: false,
  premiumUntil: 0, // мс; -1 = назавжди
  premiumSource: null,
  redeemed: [],
  vocab: [], // { id, de, tr, alts, context, bookId, at, box, due, seen, ok }
  progress: {}, // bookId -> { ch, scroll, done, at }
  studyDays: [], // 'YYYY-MM-DD'
  sessions: 0,
  achievements: [],
  xp: 0,
  xpToday: { date: null, xp: 0 },
  dailyGoal: 50, // XP на день
  perfect: 0, // тренувань без помилок
  spoken: 0, // правильно вимовлених фраз
  ratings: {}, // bookId -> 1..5
  unlocked: [], // книжки, відкриті переглядом реклами
  imported: [], // книжки, які користувач додав сам
  adCredits: 0,
  readMode: 'pages',
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
  try { localStorage.setItem(KEY, JSON.stringify(state)); } catch {}
}

export const get = (k) => state[k];
export function set(k, v) { state[k] = v; persist(); }
export function update(k, fn) { state[k] = fn(state[k]); persist(); }
export function resetAll() { state = structuredClone(DEFAULTS); persist(); }

export const FOREVER = -1;
export function isPremium() {
  const u = state.premiumUntil;
  return u === FOREVER || u > Date.now();
}

export const today = () => new Date().toLocaleDateString('sv-SE'); // YYYY-MM-DD у місцевому часі
export function markStudyDay() {
  const d = today();
  if (!state.studyDays.includes(d)) update('studyDays', (a) => [...a.slice(-400), d]);
}
export function streak() {
  const days = new Set(state.studyDays);
  let n = 0;
  const d = new Date();
  if (!days.has(today())) d.setDate(d.getDate() - 1); // серія не згорає, поки не скінчився сьогоднішній день
  while (days.has(d.toLocaleDateString('sv-SE'))) { n++; d.setDate(d.getDate() - 1); }
  return n;
}
