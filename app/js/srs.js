// Інтервальне повторення (система Лейтнера): кожне слово лежить у «коробці» 0–5.
// Правильна відповідь переносить слово в наступну коробку й відкладає повторення,
// помилка повертає в коробку 0 (повторити сьогодні ж).
import * as store from './store.js';

const DAY = 86_400_000;
const INTERVALS = [0, 1, 3, 7, 16, 35].map((d) => d * DAY);
export const MASTERED_BOX = 4;

export function addWord({ de, tr, alts = [], context = '', bookId = null }) {
  const exists = store.get('vocab').some((v) => v.de.toLowerCase() === de.toLowerCase());
  if (exists) return false;
  const id = Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  store.update('vocab', (v) => [{ id, de, tr, alts, context, bookId, at: Date.now(), box: 0, due: Date.now(), seen: 0, ok: 0 }, ...v]);
  return true;
}
export const hasWord = (de) => store.get('vocab').some((v) => v.de.toLowerCase() === de.toLowerCase());
export function removeWord(id) { store.update('vocab', (v) => v.filter((w) => w.id !== id)); }

export function grade(id, correct) {
  store.update('vocab', (list) =>
    list.map((w) => {
      if (w.id !== id) return w;
      const box = correct ? Math.min(5, w.box + 1) : 0;
      return { ...w, box, due: Date.now() + INTERVALS[box], seen: w.seen + 1, ok: w.ok + (correct ? 1 : 0) };
    }),
  );
}

export function dueWords(limit = Infinity) {
  const now = Date.now();
  return store.get('vocab').filter((w) => w.due <= now).sort((a, b) => a.box - b.box || a.due - b.due).slice(0, limit);
}
export const masteredCount = () => store.get('vocab').filter((w) => w.box >= MASTERED_BOX).length;

export function shuffle(a) {
  a = [...a];
  for (let i = a.length - 1; i > 0; i--) { const j = (Math.random() * (i + 1)) | 0; [a[i], a[j]] = [a[j], a[i]]; }
  return a;
}

// Порівняння відповіді в режимі «Письмо»: без урахування регістру, артикля, ä=ae і т.д.
export function sameWord(a, b) {
  const n = (s) => s.toLowerCase().trim()
    .replace(/^(der|die|das|ein|eine)\s+/, '')
    .replace(/ä/g, 'ae').replace(/ö/g, 'oe').replace(/ü/g, 'ue').replace(/ß/g, 'ss')
    .replace(/[^a-z]/g, '');
  return n(a) === n(b);
}
