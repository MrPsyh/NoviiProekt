// Налаштування застосунку, які змінює власник.

// Адреса вашого сервера-перекладача (server/translate-proxy.js), який ходить в офіційний
// Google Cloud Translation API. Порожньо = безкоштовний публічний endpoint Google з телефона.
export const TRANSLATE_PROXY_URL = '';

// Ціни підписки (показуються в застосунку; реальна оплата через Google Play / App Store — пізніше).
export const PLANS = [
  { id: 'month', price: '3,99 €', period: 'month' },
  { id: 'year', price: '29,99 €', period: 'year', badge: '-37%' },
];

// Скільки слів можна вчити в картках без Premium.
export const FREE_CARD_LIMIT = 30;

// Звідки завантажувати «хмарні» книжки (масовий імпорт з Gutenberg, tools/gutendex-import.js).
// Сюди викладається папка remote-books/ (Cloudflare R2, GitHub Pages, Firebase Hosting…).
export const BOOKS_CDN_URL = '';

// Реклама Google AdMob. Зараз — ОФІЦІЙНІ ТЕСТОВІ ID (безпечно для розробки).
// Перед релізом: створіть застосунок в admob.google.com, вставте свої ID тут
// і App ID в android/app/src/main/AndroidManifest.xml та ios/App/App/Info.plist (GADApplicationIdentifier).
export const ADS = {
  testing: true,
  pagesPerAd: 5, // межсторінкова реклама кожні 5 сторінок (лише без Premium)
  adsPerPremiumHour: 2, // 2 рекламні ролики → 1 година Premium
  android: { interstitial: 'ca-app-pub-3940256099942544/1033173712', rewarded: 'ca-app-pub-3940256099942544/5224354917' },
  ios: { interstitial: 'ca-app-pub-3940256099942544/4411468910', rewarded: 'ca-app-pub-3940256099942544/1712485313' },
};
