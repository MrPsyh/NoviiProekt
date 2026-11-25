// Спільні дрібниці інтерфейсу: вибірка елементів, екранування, нижня шторка, тост, озвучка.
export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
export const esc = (s) =>
  String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

const sheet = () => $('#sheet');
const backdrop = () => $('#backdrop');
let onClose = null;
export function openSheet(html, { className = '', closed } = {}) {
  const s = sheet();
  s.className = className;
  s.innerHTML = `<div class="sheet-handle"></div>${html}`;
  s.scrollTop = 0;
  requestAnimationFrame(() => { s.classList.add('open'); backdrop().classList.add('open'); });
  onClose = closed || null;
  return s;
}
export function closeSheet() {
  sheet().classList.remove('open');
  backdrop().classList.remove('open');
  $$('.w.active').forEach((el) => el.classList.remove('active'));
  const cb = onClose;
  onClose = null;
  cb?.();
}

export function toast(html, ms = 2600) {
  const el = $('#toast');
  el.innerHTML = html;
  el.classList.add('show');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.remove('show'), ms);
}

export function speak(text) {
  const tts = window.Capacitor?.Plugins?.TextToSpeech;
  if (tts) return tts.speak({ text, lang: 'de-DE', rate: 0.9 }).catch(() => {});
  if (!('speechSynthesis' in window)) return;
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = 'de-DE';
  u.rate = 0.9;
  const de = speechSynthesis.getVoices().find((v) => v.lang?.startsWith('de'));
  if (de) u.voice = de;
  speechSynthesis.speak(u);
}

export function haptic() {
  window.Capacitor?.Plugins?.Haptics?.impact?.({ style: 'LIGHT' }).catch?.(() => {});
  if (!window.Capacitor && navigator.vibrate) navigator.vibrate(8);
}
