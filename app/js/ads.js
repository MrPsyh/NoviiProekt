// Реклама (Google AdMob через @capacitor-community/admob).
//  • Межсторінкова (interstitial): у безкоштовній версії кожні N сторінок книжки.
//  • За винагороду (rewarded): 2 перегляди → 1 година Premium; 1 перегляд → імпорт власної книжки.
// ID рекламних блоків — в app/js/config.js (зараз офіційні ТЕСТОВІ ID Google; перед релізом замінити на свої).
// У браузері (не в застосунку) показується лише імітація з позначкою «тест».
import * as store from './store.js';
import { ADS } from './config.js';
import { t } from './i18n.js';

const AdMob = () => window.Capacitor?.Plugins?.AdMob;
const platform = () => window.Capacitor?.getPlatform?.() || 'web';
let ready = null;

export function initAds() {
  if (ready) return ready;
  ready = (async () => {
    const ad = AdMob();
    if (!ad) return false;
    try {
      await ad.initialize({ initializeForTesting: ADS.testing });
      // згода користувача (GDPR, ЄС) — обов'язкова для реклами в Європі
      const consent = await ad.requestConsentInfo().catch(() => null);
      if (consent?.isConsentFormAvailable && consent.status === 'REQUIRED') await ad.showConsentForm().catch(() => {});
      if (platform() === 'ios') await ad.requestTrackingAuthorization?.().catch(() => {});
      return true;
    } catch { return false; }
  })();
  return ready;
}

const unit = (kind) => ADS[platform() === 'ios' ? 'ios' : 'android'][kind];

export async function showInterstitial() {
  if (store.isPremium()) return;
  if (await initAds()) {
    try { await AdMob().prepareInterstitial({ adId: unit('interstitial'), isTesting: ADS.testing }); await AdMob().showInterstitial(); } catch {}
    return;
  }
  await fakeAd(false);
}

/** @returns {Promise<boolean>} true — користувач додивився рекламу до кінця */
export async function showRewarded() {
  if (await initAds()) {
    const ad = AdMob();
    return new Promise(async (resolve) => {
      let rewarded = false;
      const subs = [
        await ad.addListener('onRewardedVideoAdReward', () => { rewarded = true; }),
        await ad.addListener('onRewardedVideoAdDismissed', () => { subs.forEach((s) => s.remove()); resolve(rewarded); }),
        await ad.addListener('onRewardedVideoAdFailedToShow', () => { subs.forEach((s) => s.remove()); resolve(false); }),
      ];
      try { await ad.prepareRewardVideoAd({ adId: unit('rewarded'), isTesting: ADS.testing }); await ad.showRewardVideoAd(); }
      catch { subs.forEach((s) => s.remove()); resolve(false); }
    });
  }
  return fakeAd(true);
}

// Імітація реклами у веб-версії (щоб перевіряти логіку без телефона)
function fakeAd(rewarded) {
  return new Promise((resolve) => {
    const el = document.createElement('div');
    el.className = 'fake-ad';
    let left = rewarded ? 5 : 3;
    el.innerHTML = `<div class="fa-box"><small>${t('adLabel')} · TEST</small><div class="fa-owl" data-sticker="star"></div>
      <b>Lesefreund Premium</b><p>${t('adPitch')}</p><button class="btn" disabled id="faClose">${left}</button></div>`;
    document.body.appendChild(el);
    const btn = el.querySelector('#faClose');
    const timer = setInterval(() => {
      left--;
      btn.textContent = left > 0 ? String(left) : `✕ ${t('close')}`;
      if (left <= 0) { clearInterval(timer); btn.disabled = false; }
    }, 1000);
    btn.onclick = () => { el.remove(); resolve(true); };
  });
}

// Лічильник «подивись 2 реклами — отримай годину Premium»
export async function watchForPremiumHour() {
  const ok = await showRewarded();
  if (!ok) return { ok: false };
  const n = (store.get('adCredits') || 0) + 1;
  if (n >= ADS.adsPerPremiumHour) {
    store.set('adCredits', 0);
    const base = Math.max(Date.now(), store.get('premiumUntil') > 0 ? store.get('premiumUntil') : 0);
    if (store.get('premiumUntil') !== store.FOREVER) store.set('premiumUntil', base + 3600_000);
    store.set('premiumSource', 'ads');
    return { ok: true, granted: true };
  }
  store.set('adCredits', n);
  return { ok: true, granted: false, left: ADS.adsPerPremiumHour - n };
}
