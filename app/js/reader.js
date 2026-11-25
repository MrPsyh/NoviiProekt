// Екран читання: розділ книжки, переклад слова за дотиком, переклад/цитата виділеного фрагмента.
import * as store from './store.js';
import { t, langName } from './i18n.js';
import { translate } from './translate.js';
import { addWord, hasWord } from './srs.js';
import { $, $$, esc, openSheet, closeSheet, speak, toast, haptic } from './ui.js';
import { applyTheme } from './theme.js';
import { checkAchievements } from './achievements.js';
import { addXP, XP } from './xp.js';
import { showInterstitial } from './ads.js';
import { ADS } from './config.js';
import { lookup, headword, grammarLines, ipaToCyr, ARTICLE, POS_NAME } from './lexicon.js';

const FREE_PASSAGE_WORDS = 40;
const WORD_RE = /[\p{L}\p{M}][\p{L}\p{M}\p{N}'’-]*/gu;

export function renderText(text) {
  const sentences = text.match(/[^.!?…]+(?:[.!?…]+[“”»«"’)]*|$)\s*/g) || [text];
  return sentences
    .map((s) => {
      let out = '';
      let last = 0;
      for (const m of s.matchAll(WORD_RE)) {
        out += esc(s.slice(last, m.index)) + `<span class="w">${esc(m[0])}</span>`;
        last = m.index + m[0].length;
      }
      out += esc(s.slice(last));
      return `<span class="s">${out.replace(/\n/g, '<br>')}</span>`;
    })
    .join('');
}

const cleanWord = (w) => w.replace(/^[-'’]+|[-'’]+$/g, '');

// ---------- переклад слова: словник Лесі + Google ----------
export async function showWord(raw, context = '', bookId = null) {
  const word = cleanWord(raw);
  if (store.get('speakOnTap')) speak(word);
  const lang = store.get('uiLang') || 'uk';
  openSheet(`
    <div class="tr-head">
      <div class="tr-hw"><div class="tr-word" id="hw">${esc(word)}</div><div class="tr-sub" id="sub">Deutsch → ${esc(langName(store.get('targetLang')))}</div></div>
      <button class="icon-btn big-speak" id="sp" aria-label="speak">🔊</button>
    </div>
    <div class="tr-body" id="trb"><div class="skeleton"></div><div class="skeleton short"></div></div>
    <div class="sheet-actions">
      <button class="btn" id="save" disabled>＋ ${t('save')}</button>
      ${context ? `<button class="btn ghost" id="sent">${t('sentence')}</button>` : ''}
    </div>`, { className: 'word-sheet' });
  $('#sent') && ($('#sent').onclick = () => showPhrase(context.trim(), bookId));
  // з великої літери на початку речення — ще не означає іменник
  const atStart = context && context.trim().startsWith(word);
  const [entries, tr] = await Promise.all([
    lookup(word, { capitalized: atStart ? null : /^[A-ZÄÖÜ]/.test(word) }).catch(() => []),
    translate(word).catch(() => null),
  ]);
  const e = entries[0];
  const head = e ? headword(e) : word;
  $('#sp').onclick = () => speak(e ? e.w : word);
  if (e) {
    $('#hw').innerHTML = `${e.p === 'noun' && ARTICLE[e.g] ? `<span class="art art-${e.g}">${ARTICLE[e.g]}</span> ` : ''}${esc(e.w)}`;
    $('#sub').innerHTML = `<span class="pos">${esc(POS_NAME[lang]?.[e.p] || e.p)}</span>
      ${e.ipa ? `<span class="ipa">${esc(e.ipa)}</span><span class="cyr">≈ ${esc(ipaToCyr(e.ipa, lang === 'ru' ? 'ru' : 'uk'))}</span>` : ''}`;
  }
  if (!tr && !e) { $('#trb').innerHTML = `<div class="tr-error">${t('trError')}</div>`; return; }
  const grammar = e ? grammarLines(e) : [];
  const alts = (tr?.alts || []).filter((a) => a.terms?.length);
  $('#trb').innerHTML = `
    ${e && e.w.toLowerCase() !== word.toLowerCase() ? `<div class="form-note">${t('inText')}: <b>${esc(word)}</b> → ${esc(head)}</div>` : ''}
    ${tr ? `<div class="tr-text">${esc(tr.text)}</div>` : ''}
    ${grammar.length ? `<div class="gram">${grammar.map(([k, v]) => `<div><small>${k}</small><button class="gv" data-say="${esc(v.replace(/^er\/sie\/es /, ''))}">${esc(v)}</button></div>`).join('')}</div>` : ''}
    ${e?.en?.length ? `<div class="tr-alts"><div class="tr-label">${t('meanings')}</div><ol class="means" id="means">${e.en.map((g) => `<li>${esc(g)}</li>`).join('')}</ol></div>` : ''}
    ${!e && alts.length ? `<div class="tr-alts"><div class="tr-label">${t('alts')}</div>${alts.map((a) => `<div><i>${esc(a.pos)}</i> ${a.terms.map(esc).join(', ')}</div>`).join('')}</div>` : ''}
    ${context ? `<blockquote class="tr-context">${highlight(context, word)}</blockquote>` : ''}
    ${e ? '<div class="lex-src">Wiktionary · CC BY-SA</div>' : ''}`;
  $('#trb').onclick = (ev) => { const b = ev.target.closest('[data-say]'); if (b) speak(b.dataset.say); };
  // значення зі словника — перекладаємо на мову користувача
  if (e?.en?.length && store.get('targetLang') !== 'en') {
    translate(e.en.join('\n'), { from: 'en' }).then((r) => {
      const items = r.text.split('\n');
      const ol = $('#means');
      if (ol && items.length === e.en.length) ol.innerHTML = items.map((x, i) => `<li>${esc(x)} <small>${esc(e.en[i])}</small></li>`).join('');
    }).catch(() => {});
  }
  const btn = $('#save');
  if (!btn) return;
  if (hasWord(head) || hasWord(word)) { btn.textContent = t('saved'); return; }
  btn.disabled = false;
  btn.onclick = () => {
    addWord({ de: head, tr: tr?.text || e?.en?.[0] || '', alts: (tr?.alts || []).slice(0, 2), context: context.trim(), bookId, ipa: e?.ipa, form: word });
    haptic();
    addXP(XP.word);
    btn.textContent = t('saved');
    btn.disabled = true;
    checkAchievements();
  };
}

function highlight(context, word) {
  const i = context.toLowerCase().indexOf(word.toLowerCase());
  if (i < 0) return esc(context);
  return esc(context.slice(0, i)) + `<mark>${esc(context.slice(i, i + word.length))}</mark>` + esc(context.slice(i + word.length));
}

// ---------- переклад фрази ----------
export async function showPhrase(text, bookId) {
  const n = text.split(/\s+/).filter(Boolean).length;
  if (n > FREE_PASSAGE_WORDS && !store.isPremium()) {
    openSheet(`<div class="sheet-sticker" data-sticker="star"></div><p class="center">${t('longPassage')}</p>
      <div class="sheet-actions"><button class="btn" id="gp">${t('goPremium')}</button></div>`);
    $('#gp').onclick = () => { closeSheet(); location.hash = '#/premium'; };
    return;
  }
  openSheet(`
    <div class="tr-head"><blockquote class="tr-quote">${esc(text)}</blockquote>
      <button class="icon-btn" id="sp" aria-label="speak">🔊</button></div>
    <div class="tr-body" id="trb"><div class="skeleton"></div><div class="skeleton"></div></div>
    <div class="sheet-actions"><button class="btn ghost" id="qc">🖼️ ${t('shareQuote')}</button></div>`);
  $('#sp').onclick = () => speak(text);
  $('#qc').onclick = () => quoteCard(text, bookId);
  try {
    const r = await translate(text);
    $('#trb').innerHTML = `<div class="tr-text phrase">${esc(r.text)}</div>`;
  } catch {
    $('#trb').innerHTML = `<div class="tr-error">${t('trError')}</div>`;
  }
}

// ---------- картинка-цитата з водяним знаком ----------
let currentMeta = null;
export async function quoteCard(text, bookId) {
  const meta = currentMeta && currentMeta.id === bookId ? currentMeta : null;
  const W = 1080, H = 1350;
  const c = document.createElement('canvas');
  c.width = W; c.height = H;
  const x = c.getContext('2d');
  const g = x.createLinearGradient(0, 0, W, H);
  g.addColorStop(0, '#1d3557'); g.addColorStop(1, '#0b1d33');
  x.fillStyle = g; x.fillRect(0, 0, W, H);
  // водяний знак: великі сови-силуети
  x.globalAlpha = 0.06; x.fillStyle = '#fff';
  for (const [cx, cy, s] of [[880, 1120, 4.2], [160, 260, 2.4]]) owlPath(x, cx, cy, s);
  x.globalAlpha = 1;
  x.fillStyle = '#f4a261'; x.font = 'bold 260px Georgia, serif'; x.fillText('“', 70, 380);
  x.fillStyle = '#f1faee';
  let size = text.length > 260 ? 44 : text.length > 140 ? 54 : 66;
  x.font = `${size}px Georgia, 'Times New Roman', serif`;
  const lines = wrapCanvas(x, text, W - 200);
  let y = 420;
  for (const l of lines.slice(0, 14)) { x.fillText(l, 100, y); y += size * 1.4; }
  x.fillStyle = '#a8dadc'; x.font = '600 38px system-ui, sans-serif';
  if (meta) { x.fillText(`— ${meta.author}`, 100, y + 50); x.font = 'italic 34px Georgia, serif'; x.fillText(meta.title, 100, y + 100); }
  // підпис-водяний знак
  x.globalAlpha = 0.9; x.fillStyle = '#fff'; owlPath(x, 120, 1230, 0.9);
  x.font = '800 34px system-ui, sans-serif'; x.fillText('LESEFREUND', 175, 1245);
  x.globalAlpha = 0.6; x.font = '28px system-ui, sans-serif'; x.fillText('Deutsch lesen · Wörter lernen', 175, 1285);
  x.globalAlpha = 1;
  const url = c.toDataURL('image/png');
  openSheet(`<img class="quote-img" src="${url}" alt="">
    <div class="sheet-actions"><button class="btn" id="shr">↗ ${t('shareQuote')}</button><a class="btn ghost" download="lesefreund-quote.png" href="${url}">⬇ ${t('download')}</a></div>`);
  $('#shr').onclick = async () => {
    try {
      const blob = await (await fetch(url)).blob();
      const file = new File([blob], 'lesefreund-quote.png', { type: 'image/png' });
      if (navigator.canShare?.({ files: [file] })) await navigator.share({ files: [file], text: `„${text}“ — Lesefreund` });
      else await navigator.share?.({ text: `„${text}“${meta ? ` — ${meta.author}` : ''} · Lesefreund` });
    } catch {}
  };
}
function owlPath(x, cx, cy, s) {
  x.save(); x.translate(cx, cy); x.scale(s, s);
  x.beginPath(); x.ellipse(0, 6, 20, 23, 0, 0, Math.PI * 2); x.fill();
  x.beginPath(); x.moveTo(-14, -14); x.lineTo(-18, -25); x.lineTo(-7, -18); x.fill();
  x.beginPath(); x.moveTo(14, -14); x.lineTo(18, -25); x.lineTo(7, -18); x.fill();
  x.restore();
}
function wrapCanvas(x, text, max) {
  const out = []; let cur = '';
  for (const w of text.split(/\s+/)) {
    const test = cur ? cur + ' ' + w : w;
    if (x.measureText(test).width > max && cur) { out.push(cur); cur = w; } else cur = test;
  }
  if (cur) out.push(cur);
  return out;
}

// ---------- виділення тексту ----------
let selText = '';
let selBook = null;
export function initSelection() {
  const bar = $('#selbar');
  document.addEventListener('selectionchange', () => {
    const sel = getSelection();
    const text = sel && !sel.isCollapsed ? sel.toString().replace(/\s+/g, ' ').trim() : '';
    const inside = text && sel.anchorNode?.parentElement?.closest('.reader-text');
    if (inside && text.length > 1) {
      selText = text;
      selBook = $('.reader-text')?.dataset.book || null;
      bar.classList.add('show');
    } else bar.classList.remove('show');
  });
  bar.addEventListener('pointerdown', (e) => e.preventDefault()); // не скидати виділення
  bar.addEventListener('click', (e) => {
    const action = e.target.closest('button')?.dataset.act;
    if (!action) return;
    const text = selText;
    getSelection().removeAllRanges();
    bar.classList.remove('show');
    if (action === 'quote') return quoteCard(text, selBook);
    if (!/\s/.test(text)) {
      const s = $$('.reader-text .s').find((el) => el.textContent.includes(text));
      showWord(text, s?.textContent || '', selBook);
    } else showPhrase(text, selBook);
  });
}
export function selbarLabels() {
  $('#selbar').innerHTML = `<button data-act="translate">🌐 ${t('translate')}</button><button data-act="quote">❝ ${t('quote')}</button>`;
}

// ---------- сам екран ----------
let scrollHandler = null;
let pagerCleanup = null;
let pageTurns = 0; // для реклами кожні N сторінок
export function teardownReader() {
  if (scrollHandler) removeEventListener('scroll', scrollHandler);
  scrollHandler = null;
  pagerCleanup?.();
  pagerCleanup = null;
}

function saveProgress(meta, ch, total, r) {
  const prev = store.get('progress')[meta.id] || {};
  const chDone = new Set(prev.chDone || []);
  const finishedNow = r > 0.95 && !chDone.has(ch);
  if (finishedNow) chDone.add(ch);
  const done = prev.done || (ch === total - 1 && r > 0.95);
  store.update('progress', (p) => ({ ...p, [meta.id]: { ch, scroll: r, done, chDone: [...chDone], at: Date.now(), pct: Math.max(prev.pct || 0, (ch + r) / total) } }));
  if (finishedNow) addXP(XP.chapter + (done && !prev.done ? XP.bookDone : 0));
  if (done) checkAchievements();
}

export function renderReader(view, meta, book, ch) {
  currentMeta = meta;
  const total = book.chapters.length;
  ch = Math.min(Math.max(0, ch), total - 1);
  const chapter = book.chapters[ch];
  const prog = store.get('progress')[meta.id] || {};
  const paged = store.get('readMode') !== 'scroll';
  const isLast = ch === total - 1;
  const endBlock = isLast
    ? `<div class="the-end"><div class="end-sticker" data-sticker="party"></div>${t('theEnd')}
        <p class="source-line">${esc(meta.author)} · ${esc(meta.title)}${meta.translator ? ` · ${t('translationBy')}: ${esc(meta.translator)}` : ''} · ${esc(meta.source?.name || '')}</p></div>`
    : '';
  const body = `${chapter.title ? `<h2>${esc(chapter.title)}</h2>` : ''}
      ${chapter.paragraphs.map((p) => `<p class="${p.includes('\n') ? 'verse' : ''}">${renderText(p)}</p>`).join('')}`;
  document.body.classList.toggle('paged-mode', paged);
  view.innerHTML = `
    <header class="reader-top">
      <button class="icon-btn" id="rb" aria-label="back">←</button>
      <div class="rt"><strong>${esc(meta.title)}</strong><small>${esc(meta.author)}${total > 1 ? ` · ${ch + 1}/${total}` : ''}</small></div>
      <button class="icon-btn" id="disp" aria-label="display">Aa</button>
      ${total > 1 ? '<button class="icon-btn" id="toc" aria-label="contents">☰</button>' : ''}
    </header>
    ${paged
      ? `<div class="pager" id="pager"><article class="reader-text paged font-${store.get('font')}" id="art" data-book="${esc(meta.id)}" lang="de">${body}${endBlock}</article></div>
         <footer class="pager-foot"><span id="pgn"></span><div class="pf-bar"><div id="pl"></div></div><span class="pf-ch">${ch + 1}/${total}</span></footer>`
      : `<div class="progress-line"><div id="pl"></div></div>
         <article class="reader-text font-${store.get('font')}" id="art" data-book="${esc(meta.id)}" lang="de">${body}</article>
         <nav class="chapter-nav">
           ${ch > 0 ? `<a class="btn ghost" href="#/read/${meta.id}/${ch - 1}">${t('prevCh')}</a>` : '<span></span>'}
           ${ch < total - 1 ? `<a class="btn" href="#/read/${meta.id}/${ch + 1}">${t('nextCh')}</a>` : endBlock}
         </nav>`}`;

  $('#rb').onclick = () => (location.hash = '#/library');
  $('#disp').onclick = () => displaySheet(() => {
    if (!location.hash.startsWith(`#/read/${meta.id}/`)) return; // шторку закрив перехід на інший екран
    teardownReader();
    renderReader(view, meta, book, ch);
  });
  $('#toc') && ($('#toc').onclick = () => {
    openSheet(`<h2>${t('contents')}</h2><ol class="toc">${book.chapters
      .map((c, i) => `<li class="${i === ch ? 'on' : ''}"><a href="#/read/${meta.id}/${i}">${esc(c.title || `${t('chapter')} ${i + 1}`)}</a></li>`)
      .join('')}</ol>`);
  });

  const art = $('#art');
  const openWord = (w) => {
    $$('.w.active').forEach((x) => x.classList.remove('active'));
    w.classList.add('active');
    showWord(w.textContent, w.closest('.s')?.textContent.replace(/\s+/g, ' ').trim() || '', meta.id);
  };

  if (!paged) {
    art.addEventListener('click', (e) => {
      const w = e.target.closest('.w');
      const sel = getSelection();
      if (w && !(sel && !sel.isCollapsed)) openWord(w);
    });
    requestAnimationFrame(() => {
      if (prog.ch === ch && prog.scroll) scrollTo(0, prog.scroll * (document.documentElement.scrollHeight - innerHeight));
    });
    let tmr;
    scrollHandler = () => {
      const r = Math.min(1, scrollY / Math.max(1, document.documentElement.scrollHeight - innerHeight));
      $('#pl') && ($('#pl').style.width = ((ch + r) / total) * 100 + '%');
      clearTimeout(tmr);
      tmr = setTimeout(() => saveProgress(meta, ch, total, r), 400);
    };
    addEventListener('scroll', scrollHandler, { passive: true });
    scrollHandler();
    return;
  }

  // ---------- сторінки ----------
  const pager = $('#pager');
  let page = 0, pages = 1, W = 1;
  const layout = (keepRatio) => {
    const ratio = pages > 1 ? page / (pages - 1) : 0;
    W = pager.clientWidth;
    art.style.columnWidth = W - 44 + 'px';
    art.style.columnGap = '44px';
    pages = Math.max(1, Math.round(art.scrollWidth / W));
    if (keepRatio) page = Math.round(ratio * (pages - 1));
    go(page, false);
  };
  const go = (p, animate = true) => {
    page = Math.max(0, Math.min(pages - 1, p));
    art.style.transition = animate ? 'transform .28s cubic-bezier(.2,.8,.3,1)' : 'none';
    art.style.transform = `translate3d(${-page * W}px,0,0)`;
    $('#pgn').textContent = `${page + 1} / ${pages}`;
    $('#pl').style.width = ((ch + (page + 1) / pages) / total) * 100 + '%';
    saveProgress(meta, ch, total, pages > 1 ? page / (pages - 1) : 1);
  };
  const next = async () => {
    if (page < pages - 1) {
      go(page + 1);
      pageTurns++;
      if (!store.isPremium() && pageTurns % ADS.pagesPerAd === 0) setTimeout(() => showInterstitial(), 320);
    } else if (ch < total - 1) location.hash = `#/read/${meta.id}/${ch + 1}`;
  };
  const prev = () => {
    if (page > 0) go(page - 1);
    else if (ch > 0) { sessionStorage.setItem('lf:lastPage', '1'); location.hash = `#/read/${meta.id}/${ch - 1}`; }
  };

  let x0 = null, y0 = 0, t0 = 0, moved = false;
  pager.addEventListener('pointerdown', (e) => { x0 = e.clientX; y0 = e.clientY; t0 = Date.now(); moved = false; });
  pager.addEventListener('pointermove', (e) => {
    if (x0 == null) return;
    const dx = e.clientX - x0;
    if (Math.abs(dx) > 10 && Math.abs(dx) > Math.abs(e.clientY - y0)) {
      moved = true;
      art.style.transition = 'none';
      art.style.transform = `translate3d(${-page * W + dx * 0.9}px,0,0)`;
    }
  });
  pager.addEventListener('pointerup', (e) => {
    if (x0 == null) return;
    const dx = e.clientX - x0;
    x0 = null;
    const sel = getSelection();
    if (sel && !sel.isCollapsed) return go(page);
    if (moved && Math.abs(dx) > 50) return dx < 0 ? next() : prev();
    if (moved) return go(page);
    if (Date.now() - t0 > 450) return; // довге натискання — це виділення фрази
    const w = e.target.closest('.w');
    if (w) return openWord(w);
    const rx = (e.clientX - pager.getBoundingClientRect().left) / W;
    if (rx > 0.66) next(); else if (rx < 0.34) prev();
  });
  const key = (e) => { if (e.key === 'ArrowRight' || e.key === 'PageDown') next(); if (e.key === 'ArrowLeft' || e.key === 'PageUp') prev(); };
  const onResize = () => layout(true);
  addEventListener('keydown', key);
  addEventListener('resize', onResize);
  pagerCleanup = () => { removeEventListener('keydown', key); removeEventListener('resize', onResize); document.body.classList.remove('paged-mode'); };

  (document.fonts?.ready || Promise.resolve()).then(() => {
    layout(false);
    if (sessionStorage.getItem('lf:lastPage')) { sessionStorage.removeItem('lf:lastPage'); go(pages - 1, false); }
    else if (prog.ch === ch && prog.scroll) go(Math.round(prog.scroll * (pages - 1)), false);
  });
}

function displaySheet(rerender) {
  const themes = ['light', 'sepia', 'grey', 'black'];
  const mode = store.get('readMode') === 'scroll' ? 'scroll' : 'pages';
  openSheet(`<h2>Aa</h2>
    <div class="theme-row">${themes.map((th) => `<button class="theme-dot th-${th} ${store.get('theme') === th ? 'on' : ''}" data-th="${th}">${t('themes.' + th)}</button>`).join('')}</div>
    <div class="row-between"><span>${t('fontSize')}</span><div class="stepper"><button class="icon-btn" data-fs="-1">A−</button><b id="fsv">${store.get('fontSize')}</b><button class="icon-btn" data-fs="1">A+</button></div></div>
    <div class="seg">${['serif', 'sans'].map((f) => `<button class="${store.get('font') === f ? 'on' : ''}" data-font="${f}">${t(f === 'serif' ? 'fontSerif' : 'fontSans')}</button>`).join('')}</div>
    <div class="seg" style="margin-top:10px">${['pages', 'scroll'].map((m) => `<button class="${mode === m ? 'on' : ''}" data-mode="${m}">${t(m === 'pages' ? 'modePages' : 'modeScroll')}</button>`).join('')}</div>`,
  { closed: rerender });
  const s = $('#sheet');
  s.onclick = (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    if (b.dataset.th) { store.set('theme', b.dataset.th); $$('.theme-dot', s).forEach((x) => x.classList.toggle('on', x === b)); }
    if (b.dataset.fs) { store.set('fontSize', Math.min(32, Math.max(14, store.get('fontSize') + Number(b.dataset.fs)))); $('#fsv').textContent = store.get('fontSize'); }
    if (b.dataset.font) { store.set('font', b.dataset.font); $$('[data-font]', s).forEach((x) => x.classList.toggle('on', x === b)); }
    if (b.dataset.mode) { store.set('readMode', b.dataset.mode); $$('[data-mode]', s).forEach((x) => x.classList.toggle('on', x === b)); }
    applyTheme();
  };
}

export { toast };
