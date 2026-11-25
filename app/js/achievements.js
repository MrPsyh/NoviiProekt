// Досягнення-стікери: перевіряються після збереження слова, тренування й дочитаної книжки.
import * as store from './store.js';
import { ACHIEVEMENTS, badge } from './stickers.js';
import { masteredCount } from './srs.js';
import { t } from './i18n.js';
import { toast } from './ui.js';
import { levelInfo } from './xp.js';

export function stats() {
  return {
    words: store.get('vocab').length,
    sessions: store.get('sessions'),
    streak: store.streak(),
    mastered: masteredCount(),
    booksDone: Object.values(store.get('progress')).filter((p) => p.done).length,
    perfect: store.get('perfect'), spoken: store.get('spoken'), level: levelInfo().level,
  };
}
export function checkAchievements() {
  const s = stats();
  const have = new Set(store.get('achievements'));
  const fresh = ACHIEVEMENTS.filter((a) => !have.has(a.id) && a.test(s));
  if (!fresh.length) return;
  store.update('achievements', (a) => [...a, ...fresh.map((f) => f.id)]);
  const a = fresh[0];
  toast(`<div class="toast-sticker">${badge(a)}</div><div><b>${t('newSticker')}</b><br>${t('ach.' + a.id)}</div>`, 3500);
}
