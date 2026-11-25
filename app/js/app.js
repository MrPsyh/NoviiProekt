import * as store from './store.js';
import { t, setUiLang, defaultUiLang, TARGET_LANGS, UI_LANGS } from './i18n.js';
import { translate } from './translate.js';
import { redeem } from './promo.js';
import { $, $$, esc, openSheet, closeSheet, toast } from './ui.js';
import { applyTheme } from './theme.js';
import { sticker, hydrateStickers, LOGO_MARK } from './stickers.js';
import { loadIndex, loadBook, COLLECTION_ORDER, COLLECTION_ICON, LEVELS, readingMinutes } from './library.js';
import { renderReader, renderText, initSelection, selbarLabels, teardownReader } from './reader.js';
import { renderLearn, renderStudy, renderAchievements } from './learn.js';
import { renderHome, topStats } from './home.js';
import { levelInfo } from './xp.js';
import { PLANS } from './config.js';

const view = $('#view');
const tabbar = $('#tabbar');

const fmtDate = (ts) => new Date(ts).toLocaleString(store.get('uiLang') || 'uk', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' });
function premiumStatus() {
  const u = store.get('premiumUntil');
  if (u === store.FOREVER) return t('statusForever');
  if (u > Date.now()) return t('statusActive', { date: fmtDate(u) });
  return t('statusFree');
}
const desc = (b) => b.description?.[store.get('uiLang')] || b.description?.en || '';
const locked = (b) => b.premium && !store.isPremium();

// ---------- навчання при першому запуску ----------
function renderOnboarding(step = 0) {
  tabbar.hidden = true;
  const total = 5;
  const demo = 'Der kleine Hund spielt heute im Park.';
  const bodies = [
    () => `<div class="ob-sticker" data-sticker="wave"></div><h1>${t('ob1Title')}</h1><p>${t('ob1Text')}</p>
      <div class="ob-levels">${LEVELS.map((l) => `<span class="lvl lvl-${l}">${l}</span>`).join('')}</div>`,
    () => `<div class="ob-sticker small" data-sticker="globe"></div><h1>${t('ob2Title')}</h1><p>${t('ob2Text')}</p>
      <div class="lang-grid">${TARGET_LANGS.map((l) => `<button class="lang ${l.code === store.get('targetLang') ? 'on' : ''}" data-code="${l.code}"><span>${l.flag}</span>${esc(l.name)}</button>`).join('')}</div>`,
    () => `<div class="ob-sticker" data-sticker="read"></div><h1>${t('ob3Title')}</h1><p>${t('ob3Text')}</p>
      <div class="demo"><p class="demo-text" lang="de">${renderText(demo)}</p><div class="demo-out" id="demoOut">👆 ${t('tapHint')}</div></div>`,
    () => `<div class="ob-sticker" data-sticker="think"></div><h1>${t('ob4Title')}</h1><p>${t('ob4Text')}</p>
      <div class="demo"><p class="demo-text" lang="de"><mark>Berlin ist sehr schön</mark>, sagt der Mann.</p>
      <div class="demo-pill">🌐 ${t('translate')}</div></div>`,
    () => `<div class="ob-sticker" data-sticker="party"></div><h1>${t('ob5Title')}</h1><p>${t('ob5Text')}</p>
      <div class="demo mini-card"><b>der Hund</b><span>→</span><b class="tr">${esc(store.get('targetLang') === 'en' ? 'dog' : store.get('targetLang') === 'ru' ? 'собака' : 'собака')}</b></div>`,
  ];
  const canNext = step !== 1 || store.get('targetLang');
  view.innerHTML = `<section class="onboarding watermark">
    <div class="ob-top">${step > 0 ? `<button class="link" id="obBack">← ${t('back')}</button>` : '<span></span>'}
      <span class="brand"><i class="logo">${LOGO_MARK}</i>Lesefreund</span></div>
    <div class="ob-body" key="${step}">${bodies[step]()}</div>
    <div class="ob-bottom"><div class="dots">${Array.from({ length: total }, (_, i) => `<span class="dot ${i === step ? 'on' : ''}"></span>`).join('')}</div>
      <button class="btn big" id="obNext" ${canNext ? '' : 'disabled'}>${step === total - 1 ? t('start') : t('next')}</button></div>
  </section>`;
  hydrateStickers(view);
  $('#obBack')?.addEventListener('click', () => renderOnboarding(step - 1));
  $('#obNext').onclick = () => {
    if (step < total - 1) return renderOnboarding(step + 1);
    store.set('onboarded', true);
    location.hash = '#/home';
    route();
  };
  $$('.lang', view).forEach((b) => (b.onclick = () => {
    store.set('targetLang', b.dataset.code);
    store.set('uiLang', defaultUiLang(b.dataset.code));
    setUiLang(store.get('uiLang'));
    renderOnboarding(1);
  }));
  $$('.demo-text .w', view).forEach((w) => (w.onclick = async () => {
    $$('.w.active', view).forEach((x) => x.classList.remove('active'));
    w.classList.add('active');
    const out = $('#demoOut');
    out.textContent = t('translating');
    try { out.innerHTML = `<b>${esc(w.textContent)}</b> — ${esc((await translate(w.textContent)).text)}`; }
    catch { out.textContent = t('trError'); }
  }));
}

// ---------- бібліотека ----------
let query = '';
let level = 'all';
const coverImg = (b) => `<div class="cover ${locked(b) ? 'is-locked' : ''}"><img src="covers/${b.id}.svg" alt="" loading="lazy">${locked(b) ? '<i class="lock">🔒</i>' : ''}${progressBar(b)}</div>`;
function progressBar(b) {
  const p = store.get('progress')[b.id];
  if (!p?.pct) return '';
  return `<div class="cover-prog"><div style="width:${Math.round((p.done ? 1 : p.pct) * 100)}%"></div></div>`;
}
const bookTile = (b) => `<button class="tile" data-book="${b.id}">${coverImg(b)}<strong>${esc(b.title)}</strong><small>${esc(b.author)}</small></button>`;

async function renderLibrary() {
  const books = await loadIndex();
  const filtered = books.filter((b) => (level === 'all' || b.level === level) &&
    (!query || (b.title + ' ' + b.author).toLowerCase().includes(query.toLowerCase())));
  const recent = books.map((b) => ({ b, p: store.get('progress')[b.id] })).filter((x) => x.p && !x.p.done && !locked(x.b))
    .sort((a, b) => b.p.at - a.p.at)[0];
  view.innerHTML = `
    <header class="top lib-top"><div><small class="muted">${t('hello')}</small><h1>${t('tabLibrary')}</h1></div>
      ${topStats(false)}</header>
    <input class="search" id="q" type="search" placeholder="🔎 ${t('search')}" value="${esc(query)}">
    <div class="chips">${['all', ...LEVELS].map((l) => `<button class="chip ${l === level ? 'on' : ''}" data-l="${l}">${l === 'all' ? t('levelAll') : l}</button>`).join('')}</div>
    ${recent && !query && level === 'all' ? `<button class="continue" data-book="${recent.b.id}">
      <img src="covers/${recent.b.id}.svg" alt=""><div><small>${t('continue')}</small><strong>${esc(recent.b.title)}</strong>
      <span class="muted">${esc(recent.b.author)}</span><div class="bar"><div style="width:${Math.round(recent.p.pct * 100)}%"></div></div></div>
      <span class="play">▶</span></button>` : ''}
    <div id="shelves"></div>`;
  const shelves = $('#shelves');
  if (query || level !== 'all') {
    shelves.innerHTML = filtered.length ? `<div class="grid">${filtered.map(bookTile).join('')}</div>`
      : `<div class="empty"><div class="empty-sticker" data-sticker="think"></div><p>${t('nothingFound')}</p></div>`;
  } else {
    shelves.innerHTML = COLLECTION_ORDER.map((c) => {
      const list = books.filter((b) => b.collections.includes(c));
      if (!list.length) return '';
      return `<section class="shelf"><div class="shelf-head"><h2>${COLLECTION_ICON[c]} ${t('collections.' + c)}</h2>
        <a href="#/c/${c}">${t('seeAll')} ${list.length} ›</a></div>
        <div class="shelf-row">${list.slice(0, 24).map(bookTile).join('')}</div></section>`;
    }).join('');
  }
  hydrateStickers(view);
  const q = $('#q');
  q.oninput = () => { query = q.value; renderLibrary().then(() => { const n = $('#q'); n.focus(); n.setSelectionRange(n.value.length, n.value.length); }); };
  $$('.chip', view).forEach((c) => (c.onclick = () => { level = c.dataset.l; renderLibrary(); }));
}

async function renderCollection(id) {
  const books = (await loadIndex()).filter((b) => b.collections.includes(id));
  view.innerHTML = `<header class="top"><a class="icon-btn" href="#/library">←</a><h1 class="h-coll">${COLLECTION_ICON[id] || ''} ${t('collections.' + id)}</h1><span></span></header>
    <div class="grid">${books.map(bookTile).join('')}</div>`;
}

async function bookSheet(id) {
  const b = (await loadIndex()).find((x) => x.id === id);
  if (!b) return;
  const p = store.get('progress')[b.id];
  openSheet(`<div class="book-detail">
      <img class="bd-cover" src="covers/${b.id}.svg" alt="">
      <div class="bd-meta"><span class="lvl lvl-${b.level}">${b.level}</span>
        <h2>${esc(b.title)}</h2><div class="muted">${esc(b.author)}${b.authorYears ? ` (${esc(b.authorYears)})` : ''}</div>
        <div class="bd-facts">${b.words ? `<span>📖 ${b.words.toLocaleString()} ${t('words')}</span><span>⏱ ${readingMinutes(b.words)} ${t('minutes')}</span>` : ''}
        ${b.chapters > 1 ? `<span>☰ ${b.chapters} ${t('chapters')}</span>` : ''}</div></div>
    </div>
    <p class="bd-desc">${esc(desc(b))}</p>
    <p class="bd-source">© ${t('publicDomain')}${b.year ? ` · ${esc(b.year)}` : ''}${b.translator ? ` · ${t('translationBy')}: ${esc(b.translator)}` : ''}${b.source?.name ? ` · ${t('source')}: ${esc(b.source.name)}` : ''}</p>
    <div class="sheet-actions">${locked(b)
      ? `<button class="btn" id="gp">🔒 ${t('goPremium')}</button>`
      : `<a class="btn" href="#/read/${b.id}/${p?.ch || 0}">${p ? t('continueBtn') : t('readBtn')}</a>`}</div>`);
  $('#gp') && ($('#gp').onclick = () => { closeSheet(); location.hash = '#/premium'; });
}

// ---------- Premium ----------
function renderPremium() {
  const prem = store.isPremium();
  view.innerHTML = `<header class="top"><a class="icon-btn" href="#/profile">←</a><h1 class="h-coll">${t('tabPremium')}</h1><span></span></header>
    <div class="premium-hero watermark-light">
      <div class="ph-sticker" data-sticker="star"></div>
      <div class="pc-title">${t('premiumTitle')}</div>
      <div class="pc-status ${prem ? 'pro' : ''}">${esc(premiumStatus())}</div>
      <ul>${t('perks').map((p) => `<li>✓ ${esc(p)}</li>`).join('')}</ul>
    </div>
    <div class="plans">${PLANS.map((p, i) => `<button class="plan ${i === 1 ? 'best' : ''}" data-plan="${p.id}">
      ${p.badge ? `<em>${p.badge}</em>` : ''}<b>${p.price}</b><span>${t(p.period === 'year' ? 'perYear' : 'perMonth')}</span></button>`).join('')}</div>
    <button class="btn big" id="buy">${t('subscribe')}</button>
    <div class="card">
      <h3>🎁 ${t('promoTitle')}</h3>
      <form id="promo" class="promo-row"><input id="code" autocomplete="off" autocapitalize="characters" spellcheck="false" placeholder="XXXX-XXXX-XXXX">
        <button class="btn" type="submit">${t('promoApply')}</button></form>
      <div id="promoMsg" class="promo-msg"></div>
    </div>`;
  hydrateStickers(view);
  $$('.plan').forEach((b) => (b.onclick = () => { $$('.plan').forEach((x) => x.classList.toggle('sel', x === b)); }));
  $('.plan.best')?.classList.add('sel');
  // TODO: Google Play Billing / App Store In-App Purchase (наприклад, через RevenueCat).
  $('#buy').onclick = () => openSheet(`<div class="sheet-sticker" data-sticker="heart"></div><p class="center">${t('payLater')}</p>`) && hydrateStickers();
  $('#promo').onsubmit = async (e) => {
    e.preventDefault();
    const msg = $('#promoMsg');
    const r = await redeem($('#code').value);
    if (r.ok) {
      msg.className = 'promo-msg ok';
      msg.textContent = r.until === store.FOREVER ? t('promoOkForever') : t('promoOk', { date: fmtDate(r.until) });
      toast(`<div class="toast-sticker">${sticker('party')}</div><b>★ Premium</b>`);
      setTimeout(renderPremium, 2200);
    } else {
      msg.className = 'promo-msg err';
      msg.textContent = t({ bad: 'promoBad', used: 'promoUsed', expired: 'promoExpired' }[r.reason]);
    }
  };
}

// ---------- налаштування ----------
function renderSettings() {
  const opt = (v, cur, label) => `<option value="${v}" ${v === cur ? 'selected' : ''}>${esc(label)}</option>`;
  const li = levelInfo();
  view.innerHTML = `<header class="top"><h1>${t('tabProfile')}</h1>${topStats(false)}</header>
    <section class="profile-card">
      <div class="pf-owl" data-sticker="star"></div>
      <div><b>${t('level')} ${li.level}</b><div class="xpbar light"><div style="width:${(li.inLevel / li.need) * 100}%"></div></div>
        <small>${li.inLevel} / ${li.need} XP</small></div>
    </section>
    <a class="card premium-link" href="#/premium"><span class="pl-star">★</span><div><b>${t('premiumTitle')}</b><small>${esc(premiumStatus())}</small></div><span class="chev">›</span></a>
    <a class="card premium-link" href="#/achievements"><span class="pl-star ach">🏆</span><div><b>${t('qAchievements')}</b><small>${store.get('achievements').length} ${t('badges').toLowerCase()}</small></div><span class="chev">›</span></a>
    <h3 class="section-title">${t('settings')}</h3>
    <div class="card form">
      <label>${t('targetLang')}<select id="tl">${TARGET_LANGS.map((l) => opt(l.code, store.get('targetLang'), `${l.flag} ${l.name}`)).join('')}</select></label>
      <label>${t('uiLang')}<select id="ul">${UI_LANGS.map((l) => opt(l.code, store.get('uiLang'), l.name)).join('')}</select></label>
    </div>
    <div class="card form">
      <div class="lbl">${t('theme')}</div>
      <div class="theme-row">${['light', 'sepia', 'grey', 'black'].map((th) => `<button class="theme-dot th-${th} ${store.get('theme') === th ? 'on' : ''}" data-th="${th}">${t('themes.' + th)}</button>`).join('')}</div>
      <label>${t('fontSize')}: <b id="fsv">${store.get('fontSize')}px</b><input type="range" id="fs" min="14" max="32" value="${store.get('fontSize')}"></label>
      <p class="preview font-${store.get('font')}" lang="de">Als Gregor Samsa eines Morgens aus unruhigen Träumen erwachte…</p>
      <div class="seg">${['serif', 'sans'].map((f) => `<button class="${store.get('font') === f ? 'on' : ''}" data-font="${f}">${t(f === 'serif' ? 'fontSerif' : 'fontSans')}</button>`).join('')}</div>
      <label class="switch"><input type="checkbox" id="sot" ${store.get('speakOnTap') ? 'checked' : ''}><span>${t('speak')}</span></label>
    </div>
    <div class="card form">
      <button class="btn ghost" id="tut">${t('showTutorial')}</button>
      <button class="btn danger" id="reset">${t('resetAll')}</button>
    </div>
    <p class="about"><i class="logo">${LOGO_MARK}</i> Lesefreund 0.2<br>${t('aboutBooks')}</p>`;
  $('#tl').onchange = (e) => store.set('targetLang', e.target.value);
  $('#ul').onchange = (e) => { store.set('uiLang', e.target.value); setUiLang(e.target.value); renderSettings(); renderTabbar(); selbarLabels(); };
  $('#fs').oninput = (e) => { store.set('fontSize', +e.target.value); $('#fsv').textContent = e.target.value + 'px'; applyTheme(); };
  $('#sot').onchange = (e) => store.set('speakOnTap', e.target.checked);
  view.onclick = (e) => {
    const b = e.target.closest('button');
    if (b?.dataset.th) { store.set('theme', b.dataset.th); applyTheme(); $$('.theme-dot').forEach((x) => x.classList.toggle('on', x === b)); }
    if (b?.dataset.font) { store.set('font', b.dataset.font); $$('[data-font]').forEach((x) => x.classList.toggle('on', x === b)); $('.preview').className = `preview font-${b.dataset.font}`; }
  };
  $('#tut').onclick = () => { store.set('onboarded', false); route(); };
  $('#reset').onclick = () => {
    if (!confirm(t('resetConfirm'))) return;
    store.resetAll();
    localStorage.removeItem('lesefreund:trcache2');
    location.hash = '';
    location.reload();
  };
}

// ---------- навігація ----------
const ICONS = {
  home: '<svg viewBox="0 0 24 24"><path d="M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z"/></svg>',
  library: '<svg viewBox="0 0 24 24"><path d="M4 4.5C6.5 3.5 9.5 3.5 12 5.5v15c-2.5-2-5.5-2-8-1zM20 4.5c-2.5-1-5.5-1-8 1v15c2.5-2 5.5-2 8-1z"/></svg>',
  learn: '<svg viewBox="0 0 24 24"><rect x="3" y="6" width="13" height="15" rx="2.5"/><path d="M8 3h10.5A2.5 2.5 0 0 1 21 5.5V17" fill="none" stroke-width="2.2"/></svg>',
  profile: '<svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4.5"/><path d="M3.5 21c.8-4.5 4.3-7 8.5-7s7.7 2.5 8.5 7z"/></svg>',
};
function renderTabbar() {
  const cur = location.hash.split('/')[1] || 'home';
  const active = { c: 'library', read: 'library', study: 'learn', achievements: 'learn', premium: 'profile', settings: 'profile' }[cur] || cur;
  const tabs = [['home', t('tabHome')], ['library', t('tabLibrary')], ['learn', t('tabLearn')], ['profile', t('tabProfile')]];
  tabbar.innerHTML = tabs.map(([id, label]) => `<a href="#/${id}" class="${active === id ? 'on' : ''}"><span class="ti">${ICONS[id]}</span>${esc(label)}</a>`).join('');
}

async function route() {
  closeSheet();
  teardownReader();
  $('#selbar').classList.remove('show');
  view.onclick = null;
  scrollTo(0, 0);
  if (!store.get('onboarded') || !store.get('targetLang')) return renderOnboarding(0);
  const [, page, a, b] = location.hash.split('/');
  document.body.dataset.page = page || 'library';
  tabbar.hidden = page === 'read' || page === 'study';
  renderTabbar();
  if (page === 'read') {
    const meta = (await loadIndex()).find((x) => x.id === a);
    if (!meta) return (location.hash = '#/library');
    if (locked(meta)) return (location.hash = '#/premium');
    view.innerHTML = '<div class="empty"><div class="skeleton"></div><div class="skeleton short"></div></div>';
    try { return renderReader(view, meta, await loadBook(a), Number(b) || 0); }
    catch { view.innerHTML = `<div class="empty"><div class="empty-sticker" data-sticker="think"></div><p>${t('loadError')}</p><a class="btn" href="#/library">← ${t('tabLibrary')}</a></div>`; return; }
  }
  if (page === 'c') return renderCollection(a);
  if (page === 'learn') return renderLearn(view, a);
  if (page === 'achievements') return renderAchievements(view);
  if (page === 'library') return renderLibrary();
  if (page === 'profile') return renderSettings();
  if (page === 'study') return renderStudy(view, a, b === 'all');
  if (page === 'premium') return renderPremium();
  if (page === 'settings') return renderSettings();
  return renderHome(view);
}

// клік по обкладинці → картка книжки
document.addEventListener('click', (e) => {
  const el = e.target.closest('[data-book]');
  if (el && !el.closest('.reader-text')) bookSheet(el.dataset.book);
});
$('#backdrop').addEventListener('click', closeSheet);
document.addEventListener('keydown', (e) => e.key === 'Escape' && closeSheet());
new MutationObserver(() => hydrateStickers()).observe(document.body, { childList: true, subtree: true });

setUiLang(store.get('uiLang') || defaultUiLang(store.get('targetLang')));
applyTheme();
selbarLabels();
initSelection();
addEventListener('hashchange', route);
route();

// Android: апаратна кнопка «Назад»
window.Capacitor?.Plugins?.App?.addListener?.('backButton', () => {
  if ($('#sheet').classList.contains('open')) return closeSheet();
  if (location.hash && !/^#\/(home)?$/.test(location.hash)) history.back();
  else window.Capacitor.Plugins.App.exitApp();
});
if ('serviceWorker' in navigator && location.protocol.startsWith('http') && !window.Capacitor) {
  navigator.serviceWorker.register('sw.js').catch(() => {});
}
