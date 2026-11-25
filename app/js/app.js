import * as store from './store.js';
import { t, setUiLang, defaultUiLang, TARGET_LANGS, langName } from './i18n.js';
import { BOOKS, LEVELS } from '../data/books.js';
import { translate } from './translate.js';
import { redeem } from './promo.js';

const FREE_PHRASE_WORDS = 25;
const $ = (sel, root = document) => root.querySelector(sel);
const esc = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

const view = $('#view');
const tabbar = $('#tabbar');

// ---------- общее ----------
function applyTheme() {
  const th = store.get('theme');
  if (th === 'auto') delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = th;
  document.documentElement.style.setProperty('--reader-size', store.get('fontSize') + 'px');
}

function formatDate(ts) {
  return new Date(ts).toLocaleString(store.get('uiLang') === 'ru' ? 'ru-RU' : 'en-GB', {
    day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

function premiumStatus() {
  const u = store.get('premiumUntil');
  if (u === store.FOREVER) return t('statusForever');
  if (u > Date.now()) return t('statusActive', { date: formatDate(u) });
  return t('statusFree');
}

function speak(text) {
  if (!('speechSynthesis' in window)) return;
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = 'de-DE';
  u.rate = 0.9;
  speechSynthesis.speak(u);
}

// ---------- нижняя панель (bottom sheet) ----------
const sheet = $('#sheet');
const backdrop = $('#backdrop');
function openSheet(html) {
  sheet.innerHTML = `<div class="sheet-handle"></div>${html}`;
  sheet.classList.add('open');
  backdrop.classList.add('open');
}
function closeSheet() {
  sheet.classList.remove('open');
  backdrop.classList.remove('open');
  document.querySelectorAll('.w.active').forEach((el) => el.classList.remove('active'));
}
backdrop.addEventListener('click', closeSheet);
document.addEventListener('keydown', (e) => e.key === 'Escape' && closeSheet());

function toast(msg) {
  const el = $('#toast');
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.remove('show'), 2600);
}

// ---------- разметка текста: предложения и слова ----------
const WORD_RE = /[\p{L}\p{M}][\p{L}\p{M}\p{N}'’-]*/gu;
function renderParagraph(text) {
  const sentences = text.match(/[^.!?…]+(?:[.!?…]+[“”»"]?|$)\s*/g) || [text];
  return sentences
    .map((s) => {
      let out = '';
      let last = 0;
      for (const m of s.matchAll(WORD_RE)) {
        out += esc(s.slice(last, m.index)) + `<span class="w">${esc(m[0])}</span>`;
        last = m.index + m[0].length;
      }
      out += esc(s.slice(last));
      return `<span class="s">${out}</span>`;
    })
    .join('');
}

// ---------- перевод слова / фразы ----------
async function showWord(word, context, bookId) {
  const clean = word.replace(/^[-'’]+|[-'’]+$/g, '');
  openSheet(`
    <div class="tr-head">
      <div class="tr-word">${esc(clean)}</div>
      <button class="icon-btn" id="sp" aria-label="speak">🔊</button>
    </div>
    <div class="tr-body" id="trb"><div class="loader">${t('translating')}</div></div>
    <div class="sheet-actions">
      <button class="btn" id="save">${t('save')}</button>
      <button class="btn ghost" id="sent">${t('sentence')}</button>
    </div>`);
  $('#sp').onclick = () => speak(clean);
  $('#sent').onclick = () => showPhrase(context.trim(), bookId);
  let result;
  try {
    result = await translate(clean, { context });
    $('#trb').innerHTML = `<div class="tr-text">${esc(result.text)}</div>
      ${result.note ? `<div class="tr-note">${esc(result.note)}</div>` : ''}
      <div class="tr-meta">de → ${esc(langName(store.get('targetLang')))} · ${esc(result.provider)}</div>`;
  } catch {
    $('#trb').innerHTML = `<div class="tr-error">${t('translationError')}</div>`;
  }
  const saveBtn = $('#save');
  const already = store.get('vocab').some((v) => v.de.toLowerCase() === clean.toLowerCase());
  if (already) {
    saveBtn.textContent = t('saved');
    saveBtn.disabled = true;
  }
  saveBtn.onclick = () => {
    store.update('vocab', (v) => [
      { de: clean, tr: result?.text || '', note: result?.note || '', lang: store.get('targetLang'), context: context.trim(), bookId, at: Date.now() },
      ...v,
    ]);
    saveBtn.textContent = t('saved');
    saveBtn.disabled = true;
  };
}

async function showPhrase(text, bookId) {
  const words = text.split(/\s+/).filter(Boolean).length;
  if (words > FREE_PHRASE_WORDS && !store.isPremium()) {
    openSheet(`<p class="tr-note">${t('phrasePremium')}</p>
      <div class="sheet-actions"><button class="btn" id="gp">${t('goPremium')}</button></div>`);
    $('#gp').onclick = () => { closeSheet(); location.hash = '#/premium'; };
    return;
  }
  openSheet(`
    <div class="tr-head"><div class="tr-quote">${esc(text)}</div>
      <button class="icon-btn" id="sp" aria-label="speak">🔊</button></div>
    <div class="tr-body" id="trb"><div class="loader">${t('translating')}</div></div>`);
  $('#sp').onclick = () => speak(text);
  try {
    const r = await translate(text);
    $('#trb').innerHTML = `<div class="tr-text phrase">${esc(r.text)}</div>
      <div class="tr-meta">de → ${esc(langName(store.get('targetLang')))} · ${esc(r.provider)}</div>`;
  } catch {
    $('#trb').innerHTML = `<div class="tr-error">${t('translationError')}</div>`;
  }
}

// ---------- выделение текста (зажать и выделить) ----------
const selBar = $('#selbar');
let selectedText = '';
let selectedBook = null;
document.addEventListener('selectionchange', () => {
  const sel = getSelection();
  const text = sel && !sel.isCollapsed ? sel.toString().replace(/\s+/g, ' ').trim() : '';
  const inReader = text && sel.anchorNode && sel.anchorNode.parentElement?.closest('.reader-text');
  if (inReader && text.length > 1) {
    selectedText = text;
    selectedBook = $('.reader-text')?.dataset.book;
    selBar.classList.add('show');
  } else {
    selBar.classList.remove('show');
  }
});
// pointerdown + preventDefault — чтобы нажатие на кнопку не сбрасывало выделение
selBar.addEventListener('pointerdown', (e) => e.preventDefault());
selBar.addEventListener('click', () => {
  const text = selectedText;
  getSelection().removeAllRanges();
  selBar.classList.remove('show');
  if (!/\s/.test(text)) {
    const s = [...document.querySelectorAll('.reader-text .s')].find((el) => el.textContent.includes(text));
    showWord(text, s?.textContent || text, selectedBook);
  } else showPhrase(text, selectedBook);
});

// ---------- онбординг ----------
function renderOnboarding(step = 0) {
  tabbar.hidden = true;
  const total = 4;
  const dots = Array.from({ length: total }, (_, i) => `<span class="dot ${i === step ? 'on' : ''}"></span>`).join('');
  let body = '';
  if (step === 0) {
    body = `<div class="ob-art">📚</div><h1>${t('ob1Title')}</h1><p>${t('ob1Text')}</p>
      <div class="ob-levels">${LEVELS.map((l) => `<span class="lvl lvl-${l}">${l}</span>`).join('')}</div>`;
  } else if (step === 1) {
    const cur = store.get('targetLang');
    body = `<h1>${t('ob4Title')}</h1><p>${t('ob4Text')}</p>
      <div class="lang-grid">${TARGET_LANGS.map(
        (l) => `<button class="lang ${l.code === cur ? 'on' : ''}" data-code="${l.code}"><span>${l.flag}</span>${esc(l.name)}</button>`,
      ).join('')}</div>`;
  } else if (step === 2) {
    body = `<div class="ob-art">👆</div><h1>${t('ob2Title')}</h1><p>${t('ob2Text')}</p>
      <div class="demo"><div class="demo-label">${t('demoTap')}</div>
      <p class="reader-text demo-text" data-book="demo">${renderParagraph('Der kleine Hund spielt heute im Park.')}</p>
      <div class="demo-out" id="demoOut">&nbsp;</div></div>`;
  } else {
    body = `<div class="ob-art">✍️</div><h1>${t('ob3Title')}</h1><p>${t('ob3Text')}</p>
      <div class="demo"><p class="demo-text"><mark>Berlin ist sehr schön</mark>, sagt der Mann.</p>
      <div class="demo-out">→ ${t('translateSel')}</div></div>`;
  }
  const canNext = step !== 1 || store.get('targetLang');
  view.innerHTML = `<section class="onboarding">
    <div class="ob-top">${step > 0 ? `<button class="link" id="obBack">← ${t('back')}</button>` : '<span></span>'}
      <span class="brand">Lesefreund</span></div>
    <div class="ob-body">${body}</div>
    <div class="ob-bottom"><div class="dots">${dots}</div>
      <button class="btn big" id="obNext" ${canNext ? '' : 'disabled'}>${step === total - 1 ? t('start') : t('next')}</button></div>
  </section>`;

  $('#obBack')?.addEventListener('click', () => renderOnboarding(step - 1));
  $('#obNext').addEventListener('click', () => {
    if (step < total - 1) renderOnboarding(step + 1);
    else {
      store.set('onboarded', true);
      location.hash = '#/library';
      route();
    }
  });
  view.querySelectorAll('.lang').forEach((b) =>
    b.addEventListener('click', () => {
      store.set('targetLang', b.dataset.code);
      store.set('uiLang', defaultUiLang(b.dataset.code));
      setUiLang(store.get('uiLang'));
      renderOnboarding(1);
    }),
  );
  if (step === 2) {
    view.querySelectorAll('.demo-text .w').forEach((w) =>
      w.addEventListener('click', async () => {
        view.querySelectorAll('.w.active').forEach((x) => x.classList.remove('active'));
        w.classList.add('active');
        const out = $('#demoOut');
        out.textContent = t('translating');
        try {
          const r = await translate(w.textContent, { context: 'Der kleine Hund spielt heute im Park.' });
          out.innerHTML = `<b>${esc(w.textContent)}</b> — ${esc(r.text)}`;
        } catch {
          out.textContent = t('translationError');
        }
      }),
    );
  }
}

// ---------- библиотека ----------
let levelFilter = 'all';
function renderLibrary() {
  const premium = store.isPremium();
  const books = BOOKS.filter((b) => levelFilter === 'all' || b.level === levelFilter);
  const lang = store.get('uiLang');
  view.innerHTML = `<header class="top"><h1>${t('library')}</h1><span class="status ${premium ? 'pro' : ''}">${premium ? '★ Premium' : t('free')}</span></header>
    <div class="chips">${['all', ...LEVELS]
      .map((l) => `<button class="chip ${l === levelFilter ? 'on' : ''}" data-l="${l}">${l === 'all' ? t('all') : l}</button>`)
      .join('')}</div>
    <div class="books">${books
      .map((b) => {
        const locked = b.premium && !premium;
        const pr = Math.round((store.get('progress')[b.id]?.scroll || 0) * 100);
        return `<button class="book ${locked ? 'locked' : ''}" data-id="${b.id}">
          <div class="cover" style="--c:${b.color}"><span>${b.emoji}</span><em class="lvl lvl-${b.level}">${b.level}</em>${locked ? '<i class="lock">🔒</i>' : ''}</div>
          <div class="meta"><strong>${esc(b.title)}</strong><small>${esc(b.author)}</small>
            <p>${esc(b.description[lang] || b.description.en)}</p>
            ${pr ? `<div class="bar"><div style="width:${pr}%"></div></div><small>${t('progress')}: ${pr}%</small>` : ''}
          </div></button>`;
      })
      .join('')}</div>`;
  view.querySelectorAll('.chip').forEach((c) => c.addEventListener('click', () => { levelFilter = c.dataset.l; renderLibrary(); }));
  view.querySelectorAll('.book').forEach((el) =>
    el.addEventListener('click', () => {
      const b = BOOKS.find((x) => x.id === el.dataset.id);
      if (b.premium && !store.isPremium()) {
        openSheet(`<h2>🔒 ${esc(b.title)}</h2><p class="tr-note">${t('unlockHint')}</p>
          <div class="sheet-actions"><button class="btn" id="gp">${t('goPremium')}</button></div>`);
        $('#gp').onclick = () => { closeSheet(); location.hash = '#/premium'; };
      } else location.hash = `#/book/${b.id}`;
    }),
  );
}

// ---------- читалка ----------
let scrollHandler;
function renderReader(id) {
  const b = BOOKS.find((x) => x.id === id);
  if (!b) return (location.hash = '#/library');
  if (b.premium && !store.isPremium()) return (location.hash = '#/premium');
  tabbar.hidden = true;
  view.innerHTML = `<header class="top reader-top">
      <button class="icon-btn" id="rb" aria-label="back">←</button>
      <div class="rt"><strong>${esc(b.title)}</strong><small>${esc(b.author)} · ${b.level}</small></div>
      <div class="fs"><button class="icon-btn" id="fsm">A−</button><button class="icon-btn" id="fsp">A+</button></div>
    </header>
    <div class="progress-line"><div id="pl"></div></div>
    <article class="reader-text" data-book="${b.id}">
      ${b.chapters.map((c) => `<h2>${esc(c.title)}</h2>${c.paragraphs.map((p) => `<p>${renderParagraph(p)}</p>`).join('')}`).join('')}
      <div class="the-end">— Ende —</div>
    </article>`;
  $('#rb').onclick = () => (location.hash = '#/library');
  const fs = (d) => {
    store.set('fontSize', Math.min(30, Math.max(14, store.get('fontSize') + d)));
    applyTheme();
  };
  $('#fsm').onclick = () => fs(-1);
  $('#fsp').onclick = () => fs(1);

  const article = $('.reader-text');
  article.addEventListener('click', (e) => {
    const w = e.target.closest('.w');
    if (!w) return;
    const sel = getSelection();
    if (sel && !sel.isCollapsed) return; // идёт выделение фразы
    document.querySelectorAll('.w.active').forEach((x) => x.classList.remove('active'));
    w.classList.add('active');
    showWord(w.textContent, w.closest('.s')?.textContent || '', b.id);
  });

  // прогресс чтения
  const saved = store.get('progress')[b.id]?.scroll || 0;
  requestAnimationFrame(() => {
    const max = document.documentElement.scrollHeight - innerHeight;
    scrollTo(0, saved * max);
  });
  let tmr;
  scrollHandler = () => {
    const max = Math.max(1, document.documentElement.scrollHeight - innerHeight);
    const ratio = Math.min(1, scrollY / max);
    $('#pl') && ($('#pl').style.width = ratio * 100 + '%');
    clearTimeout(tmr);
    tmr = setTimeout(() => store.update('progress', (p) => ({ ...p, [b.id]: { scroll: ratio } })), 300);
  };
  addEventListener('scroll', scrollHandler, { passive: true });
}

// ---------- мои слова ----------
function renderWords() {
  const vocab = store.get('vocab');
  view.innerHTML = `<header class="top"><h1>${t('words')}</h1><span class="status">${vocab.length}</span></header>
    ${vocab.length ? '' : `<p class="empty">${t('noWords')}</p>`}
    <ul class="vocab">${vocab
      .map(
        (v, i) => `<li><div><button class="link de" data-say="${esc(v.de)}">🔊 ${esc(v.de)}</button>
          <div class="trv">${esc(v.tr)}</div>${v.note ? `<small>${esc(v.note)}</small>` : ''}
          ${v.context ? `<blockquote>${esc(v.context)}</blockquote>` : ''}</div>
          <button class="icon-btn del" data-i="${i}" aria-label="${t('remove')}">✕</button></li>`,
      )
      .join('')}</ul>`;
  view.querySelectorAll('[data-say]').forEach((b) => b.addEventListener('click', () => speak(b.dataset.say)));
  view.querySelectorAll('.del').forEach((b) =>
    b.addEventListener('click', () => {
      store.update('vocab', (v) => v.filter((_, i) => i !== Number(b.dataset.i)));
      renderWords();
    }),
  );
}

// ---------- подписка и промокоды ----------
function renderPremium() {
  const premium = store.isPremium();
  view.innerHTML = `<header class="top"><h1>${t('premium')}</h1></header>
    <div class="card premium-card">
      <div class="pc-title">★ ${t('premiumTitle')}</div>
      <div class="pc-price">${t('premiumPrice')}</div>
      <ul>${t('premiumPerks').map((p) => `<li>✓ ${esc(p)}</li>`).join('')}</ul>
      <div class="pc-status ${premium ? 'pro' : ''}">${esc(premiumStatus())}</div>
      <button class="btn big" id="buy">${t('subscribe')}</button>
    </div>
    <div class="card">
      <h3>🎁 ${t('promoTitle')}</h3>
      <form id="promo" class="promo-row">
        <input id="code" autocomplete="off" autocapitalize="characters" spellcheck="false" placeholder="${t('promoPlaceholder')}" />
        <button class="btn" type="submit">${t('promoApply')}</button>
      </form>
      <div id="promoMsg" class="promo-msg"></div>
    </div>`;
  $('#buy').onclick = () => {
    // TODO: подключить Google Play Billing / App Store / Stripe Checkout.
    openSheet(`<h2>💳 ${t('premiumPrice')}</h2><p class="tr-note">${t('subscribeSoon')}</p>`);
  };
  $('#promo').addEventListener('submit', async (e) => {
    e.preventDefault();
    const msg = $('#promoMsg');
    const r = await redeem($('#code').value);
    if (r.ok) {
      msg.className = 'promo-msg ok';
      msg.textContent = r.until === store.FOREVER ? t('promoOkForever') : t('promoOk', { date: formatDate(r.until) });
      setTimeout(renderPremium, 2500);
    } else {
      msg.className = 'promo-msg err';
      msg.textContent = t({ bad: 'promoBad', used: 'promoUsed', expired: 'promoExpired' }[r.reason]);
    }
  });
}

// ---------- настройки ----------
function renderSettings() {
  const opt = (val, cur, label) => `<option value="${val}" ${val === cur ? 'selected' : ''}>${esc(label)}</option>`;
  const tr = store.get('translator');
  view.innerHTML = `<header class="top"><h1>${t('settings')}</h1></header>
    <div class="card form">
      <label>${t('targetLang')}<select id="tl">${TARGET_LANGS.map((l) => opt(l.code, store.get('targetLang'), `${l.flag} ${l.name}`)).join('')}</select></label>
      <label>${t('uiLang')}<select id="ul">${opt('ru', store.get('uiLang'), 'Русский')}${opt('en', store.get('uiLang'), 'English')}</select></label>
      <label>${t('fontSize')}: <b id="fsv">${store.get('fontSize')}px</b><input type="range" id="fs" min="14" max="30" value="${store.get('fontSize')}"></label>
      <label>${t('theme')}<select id="th">${opt('auto', store.get('theme'), t('themeAuto'))}${opt('light', store.get('theme'), t('themeLight'))}${opt('dark', store.get('theme'), t('themeDark'))}</select></label>
    </div>
    <div class="card form">
      <label>${t('translator')}<select id="tr">${opt('auto', tr, t('trAuto'))}${opt('free', tr, t('trFree'))}${opt('gemini', tr, t('trGemini'))}${opt('offline', tr, t('trOffline'))}</select></label>
      <label>${t('geminiKey')}<input id="gk" type="password" autocomplete="off" value="${esc(store.get('geminiKey'))}" placeholder="AIza…"></label>
      <label>${t('geminiModel')}<input id="gm" value="${esc(store.get('geminiModel'))}"></label>
      <small class="hint">${t('geminiHint')}</small>
    </div>
    <div class="card form">
      <button class="btn ghost" id="tut">${t('showTutorial')}</button>
      <button class="btn danger" id="reset">${t('resetAll')}</button>
    </div>
    <p class="version">Lesefreund v0.1</p>`;
  $('#tl').onchange = (e) => store.set('targetLang', e.target.value);
  $('#ul').onchange = (e) => { store.set('uiLang', e.target.value); setUiLang(e.target.value); renderSettings(); renderTabbar(); };
  $('#fs').oninput = (e) => { store.set('fontSize', Number(e.target.value)); $('#fsv').textContent = e.target.value + 'px'; applyTheme(); };
  $('#th').onchange = (e) => { store.set('theme', e.target.value); applyTheme(); };
  $('#tr').onchange = (e) => store.set('translator', e.target.value);
  $('#gk').onchange = (e) => store.set('geminiKey', e.target.value.trim());
  $('#gm').onchange = (e) => store.set('geminiModel', e.target.value.trim() || 'gemini-2.5-flash');
  $('#tut').onclick = () => { store.set('onboarded', false); location.hash = '#/welcome'; route(); };
  $('#reset').onclick = () => {
    if (confirm(t('resetConfirm'))) {
      store.resetAll();
      localStorage.removeItem('lesefreund:trcache');
      location.hash = '#/welcome';
      location.reload();
    }
  };
}

// ---------- навигация ----------
function renderTabbar() {
  const tabs = [
    ['library', '📚', t('library')],
    ['words', '🗂️', t('words')],
    ['premium', '★', t('premium')],
    ['settings', '⚙️', t('settings')],
  ];
  const cur = (location.hash.split('/')[1] || 'library');
  tabbar.innerHTML = tabs
    .map(([id, ic, label]) => `<a href="#/${id}" class="${cur === id ? 'on' : ''}"><span>${ic}</span>${esc(label)}</a>`)
    .join('');
}

function route() {
  closeSheet();
  selBar.classList.remove('show');
  selBar.textContent = '🌐 ' + t('translateSel');
  if (scrollHandler) removeEventListener('scroll', scrollHandler);
  scrollHandler = null;
  scrollTo(0, 0);

  if (!store.get('onboarded') || !store.get('targetLang')) return renderOnboarding(0);
  const [, page, arg] = location.hash.split('/');
  tabbar.hidden = false;
  renderTabbar();
  if (page === 'book') return renderReader(arg);
  if (page === 'words') return renderWords();
  if (page === 'premium') return renderPremium();
  if (page === 'settings') return renderSettings();
  renderLibrary();
}

setUiLang(store.get('uiLang') || defaultUiLang(store.get('targetLang')));
applyTheme();
addEventListener('hashchange', route);
route();

if ('serviceWorker' in navigator && location.protocol !== 'file:') {
  navigator.serviceWorker.register('sw.js').catch(() => {});
}
