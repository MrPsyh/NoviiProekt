// Екран читання: розділ книжки, переклад слова за дотиком, переклад/цитата виділеного фрагмента.
import * as store from './store.js';
import { t, langName } from './i18n.js';
import { translate } from './translate.js';
import { addWord, hasWord } from './srs.js';
import { $, $$, esc, openSheet, closeSheet, speak, toast, haptic } from './ui.js';
import { applyTheme } from './theme.js';
import { checkAchievements } from './achievements.js';
import { addXP, XP } from './xp.js';

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

// ---------- переклад слова ----------
export async function showWord(raw, context = '', bookId = null) {
  const word = cleanWord(raw);
  if (store.get('speakOnTap')) speak(word);
  openSheet(`
    <div class="tr-head">
      <div><div class="tr-word">${esc(word)}</div><div class="tr-lang">Deutsch → ${esc(langName(store.get('targetLang')))}</div></div>
      <button class="icon-btn" id="sp" aria-label="speak">🔊</button>
    </div>
    <div class="tr-body" id="trb"><div class="skeleton"></div><div class="skeleton short"></div></div>
    <div class="sheet-actions">
      <button class="btn" id="save" disabled>＋ ${t('save')}</button>
      ${context ? `<button class="btn ghost" id="sent">${t('sentence')}</button>` : ''}
    </div>`, { className: 'word-sheet' });
  $('#sp').onclick = () => speak(word);
  $('#sent') && ($('#sent').onclick = () => showPhrase(context.trim(), bookId));
  let result;
  try {
    result = await translate(word);
    const alts = (result.alts || []).filter((a) => a.terms?.length);
    $('#trb').innerHTML = `<div class="tr-text">${esc(result.text)}</div>
      ${alts.length ? `<div class="tr-alts"><div class="tr-label">${t('alts')}</div>${alts
        .map((a) => `<div><i>${esc(a.pos)}</i> ${a.terms.map(esc).join(', ')}</div>`).join('')}</div>` : ''}
      ${context ? `<blockquote class="tr-context">${highlight(context, word)}</blockquote>` : ''}`;
  } catch {
    $('#trb').innerHTML = `<div class="tr-error">${t('trError')}</div>`;
    return;
  }
  const btn = $('#save');
  if (!btn) return;
  if (hasWord(word)) { btn.textContent = t('saved'); return; }
  btn.disabled = false;
  btn.onclick = () => {
    addWord({ de: word, tr: result.text, alts: (result.alts || []).slice(0, 2), context: context.trim(), bookId });
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
export function teardownReader() {
  if (scrollHandler) removeEventListener('scroll', scrollHandler);
  scrollHandler = null;
}

export function renderReader(view, meta, book, ch) {
  currentMeta = meta;
  const total = book.chapters.length;
  ch = Math.min(Math.max(0, ch), total - 1);
  const chapter = book.chapters[ch];
  const prog = store.get('progress')[meta.id] || {};
  view.innerHTML = `
    <header class="reader-top">
      <button class="icon-btn" id="rb" aria-label="back">←</button>
      <div class="rt"><strong>${esc(meta.title)}</strong><small>${esc(meta.author)}${total > 1 ? ` · ${ch + 1}/${total}` : ''}</small></div>
      <button class="icon-btn" id="disp" aria-label="display">Aa</button>
      ${total > 1 ? '<button class="icon-btn" id="toc" aria-label="contents">☰</button>' : ''}
    </header>
    <div class="progress-line"><div id="pl"></div></div>
    <article class="reader-text font-${store.get('font')}" data-book="${esc(meta.id)}" lang="de">
      ${chapter.title ? `<h2>${esc(chapter.title)}</h2>` : ''}
      ${chapter.paragraphs.map((p) => `<p class="${p.includes('\n') ? 'verse' : ''}">${renderText(p)}</p>`).join('')}
    </article>
    <nav class="chapter-nav">
      ${ch > 0 ? `<a class="btn ghost" href="#/read/${meta.id}/${ch - 1}">${t('prevCh')}</a>` : '<span></span>'}
      ${ch < total - 1 ? `<a class="btn" href="#/read/${meta.id}/${ch + 1}">${t('nextCh')}</a>`
        : `<div class="the-end"><div class="end-sticker" data-sticker="party"></div>${t('theEnd')}</div>`}
    </nav>
    <p class="source-line">${esc(meta.source?.name || '')}${meta.translator ? ` · ${t('translationBy')}: ${esc(meta.translator)}` : ''}${meta.year ? ` · ${esc(meta.year)}` : ''}</p>`;

  $('#rb').onclick = () => (location.hash = '#/library');
  $('#disp').onclick = displaySheet;
  $('#toc') && ($('#toc').onclick = () => {
    openSheet(`<h2>${t('contents')}</h2><ol class="toc">${book.chapters
      .map((c, i) => `<li class="${i === ch ? 'on' : ''}"><a href="#/read/${meta.id}/${i}">${esc(c.title || `${t('chapter')} ${i + 1}`)}</a></li>`)
      .join('')}</ol>`);
  });

  $('.reader-text').addEventListener('click', (e) => {
    const w = e.target.closest('.w');
    if (!w) return;
    const sel = getSelection();
    if (sel && !sel.isCollapsed) return;
    $$('.w.active').forEach((x) => x.classList.remove('active'));
    w.classList.add('active');
    showWord(w.textContent, w.closest('.s')?.textContent.replace(/\s+/g, ' ').trim() || '', meta.id);
  });

  const isLast = ch === total - 1;
  requestAnimationFrame(() => {
    if (prog.ch === ch && prog.scroll) scrollTo(0, prog.scroll * (document.documentElement.scrollHeight - innerHeight));
  });
  let tmr;
  scrollHandler = () => {
    const max = Math.max(1, document.documentElement.scrollHeight - innerHeight);
    const r = Math.min(1, scrollY / max);
    const pl = $('#pl');
    if (pl) pl.style.width = ((ch + r) / total) * 100 + '%';
    clearTimeout(tmr);
    tmr = setTimeout(() => {
      const prev = store.get('progress')[meta.id] || {};
      const chDone = new Set(prev.chDone || []);
      const finishedNow = r > 0.95 && !chDone.has(ch);
      if (finishedNow) chDone.add(ch);
      const done = prev.done || (isLast && r > 0.95);
      store.update('progress', (p) => ({ ...p, [meta.id]: { ch, scroll: r, done, chDone: [...chDone], at: Date.now(), pct: Math.max(prev.pct || 0, (ch + r) / total) } }));
      if (finishedNow) addXP(XP.chapter + (done && !prev.done ? XP.bookDone : 0));
      if (done) checkAchievements();
    }, 400);
  };
  addEventListener('scroll', scrollHandler, { passive: true });
  scrollHandler();
}

function displaySheet() {
  const themes = ['light', 'sepia', 'grey', 'black'];
  openSheet(`<h2>Aa</h2>
    <div class="theme-row">${themes.map((th) => `<button class="theme-dot th-${th} ${store.get('theme') === th ? 'on' : ''}" data-th="${th}">${t('themes.' + th)}</button>`).join('')}</div>
    <div class="row-between"><span>${t('fontSize')}</span><div class="stepper"><button class="icon-btn" data-fs="-1">A−</button><b id="fsv">${store.get('fontSize')}</b><button class="icon-btn" data-fs="1">A+</button></div></div>
    <div class="seg">${['serif', 'sans'].map((f) => `<button class="${store.get('font') === f ? 'on' : ''}" data-font="${f}">${t(f === 'serif' ? 'fontSerif' : 'fontSans')}</button>`).join('')}</div>`);
  const s = $('#sheet');
  s.onclick = (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    if (b.dataset.th) { store.set('theme', b.dataset.th); $$('.theme-dot', s).forEach((x) => x.classList.toggle('on', x === b)); }
    if (b.dataset.fs) { store.set('fontSize', Math.min(32, Math.max(14, store.get('fontSize') + Number(b.dataset.fs)))); $('#fsv').textContent = store.get('fontSize'); }
    if (b.dataset.font) {
      store.set('font', b.dataset.font);
      $$('[data-font]', s).forEach((x) => x.classList.toggle('on', x === b));
      const art = $('.reader-text'); if (art) art.className = `reader-text font-${b.dataset.font}`;
    }
    applyTheme();
  };
}

export { toast };
