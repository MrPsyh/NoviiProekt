// Досвід (XP) і рівні: XP дають за збережені слова, прочитані розділи й правильні відповіді.
import * as store from './store.js';

export const XP = { word: 2, chapter: 15, answer: 3, perfectBonus: 10, speak: 5, bookDone: 50 };
// рівень n потребує 100 + 50·(n−1) XP понад попередній
export function levelInfo(xp = store.get('xp')) {
  let level = 1, need = 100, rest = xp;
  while (rest >= need) { rest -= need; level++; need = 100 + 50 * (level - 1); }
  return { level, inLevel: rest, need };
}
export function addXP(n) {
  if (!n) return;
  const d = store.today();
  const before = levelInfo().level;
  store.set('xp', store.get('xp') + n);
  store.update('xpToday', (x) => (x?.date === d ? { date: d, xp: x.xp + n } : { date: d, xp: n }));
  store.markStudyDay();
  return levelInfo().level > before; // true = новий рівень
}
export const todayXP = () => { const x = store.get('xpToday'); return x?.date === store.today() ? x.xp : 0; };

// Тиждень Пн–Нд: які дні були активні
export function week() {
  const days = new Set(store.get('studyDays'));
  const now = new Date();
  const monday = new Date(now);
  monday.setDate(now.getDate() - ((now.getDay() + 6) % 7));
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday); d.setDate(monday.getDate() + i);
    const key = d.toLocaleDateString('sv-SE');
    return { key, done: days.has(key), today: key === store.today(), future: d > now };
  });
}
