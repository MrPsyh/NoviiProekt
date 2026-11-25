// Промокоды.
// Админ-панель генерирует коды и публикует «пак» в app/promo-pack.json.
// В паке лежат НЕ сами коды, а их SHA-256 хеши — по файлу приложения коды не узнать.
// Пак попадает в приложение с обновлением (и дополнительно подтягивается из сети, если
// приложение раздаётся как сайт/PWA).
import * as store from './store.js';

export const PEPPER = 'lesefreund-v1:'; // должен совпадать с admin/server.js

export function normalizeCode(code) {
  return String(code || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
}

export async function hashCode(code) {
  const data = new TextEncoder().encode(PEPPER + normalizeCode(code));
  const buf = await crypto.subtle.digest('SHA-256', data);
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

let packPromise;
function loadPack() {
  packPromise ||= fetch('promo-pack.json', { cache: 'no-cache' })
    .then((r) => (r.ok ? r.json() : { codes: [] }))
    .catch(() => ({ codes: [] }));
  return packPromise;
}

/**
 * @returns {Promise<{ok: true, until: number} | {ok: false, reason: 'bad'|'used'|'expired'}>}
 */
export async function redeem(code) {
  const norm = normalizeCode(code);
  if (norm.length < 4) return { ok: false, reason: 'bad' };
  const [pack, h] = await Promise.all([loadPack(), hashCode(norm)]);
  const entry = (pack.codes || []).find((c) => c.h === h);
  if (!entry) return { ok: false, reason: 'bad' };
  if (store.get('redeemed').includes(entry.id)) return { ok: false, reason: 'used' };
  if (entry.validUntil && Date.parse(entry.validUntil) < Date.now()) return { ok: false, reason: 'expired' };

  let until;
  if (entry.minutes == null || entry.minutes < 0) {
    until = store.FOREVER;
  } else {
    const cur = store.get('premiumUntil');
    if (cur === store.FOREVER) until = store.FOREVER;
    else until = Math.max(Date.now(), cur || 0) + entry.minutes * 60_000;
  }
  store.set('premiumUntil', until);
  store.set('premiumSource', 'promo');
  store.update('redeemed', (r) => [...r, entry.id]);
  return { ok: true, until };
}
