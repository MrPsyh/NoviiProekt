import * as store from './store.js';
const THEME_COLOR = { light: '#fbf8f3', sepia: '#f4ecd8', grey: '#2b2d31', black: '#000000' };
export function applyTheme() {
  const th = store.get('theme') || 'light';
  document.documentElement.dataset.theme = th;
  document.documentElement.style.setProperty('--reader-size', store.get('fontSize') + 'px');
  document.querySelector('meta[name=theme-color]')?.setAttribute('content', THEME_COLOR[th]);
  const sb = window.Capacitor?.Plugins?.StatusBar;
  if (sb) {
    sb.setStyle({ style: th === 'grey' || th === 'black' ? 'DARK' : 'LIGHT' }).catch(() => {});
    sb.setBackgroundColor?.({ color: THEME_COLOR[th] }).catch?.(() => {});
  }
}
