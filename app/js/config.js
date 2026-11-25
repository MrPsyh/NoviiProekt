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
