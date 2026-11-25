// Розділ «Вчити»: статистика, режими тренування (картки / тест / письмо), стікери, словник.
import * as store from './store.js';
import { t, langName } from './i18n.js';
import { $, $$, esc, speak, haptic, openSheet, closeSheet } from './ui.js';
import { dueWords, grade, masteredCount, removeWord, shuffle, sameWord, MASTERED_BOX } from './srs.js';
import { ACHIEVEMENTS, sticker, badge } from './stickers.js';
import { addXP, XP, levelInfo } from './xp.js';
import { topStats } from './home.js';
import { checkAchievements } from './achievements.js';
import { FREE_CARD_LIMIT } from './config.js';

const SESSION_SIZE = 12;
let wordFilter = '';

export function renderLearn(view, focus) {
  const vocab = store.get('vocab');
  const due = dueWords().length;
  const got = new Set(store.get('achievements'));
  view.innerHTML = `
    <header class="top"><h1>${t('tabLearn')}</h1>${topStats(false)}</header>
    <div class="stats">
      <div><b>${vocab.length}</b><span>${t('statWords')}</span></div>
      <div class="hl"><b>${due}</b><span>${t('statDue')}</span></div>
      <div><b>${masteredCount()}</b><span>${t('statMastered')}</span></div>
    </div>
    <div class="modes">
      ${mode('cards', '🃏', t('modeCards'), t('modeCardsSub'))}
      ${mode('quiz', '✅', t('modeQuiz'), t('modeQuizSub'))}
      ${mode('match', '🔗', t('modeMatch'), t('modeMatchSub'))}
      ${mode('write', '✍️', t('modeWrite'), t('modeWriteSub'))}
      ${mode('speak', '🎤', t('modeSpeak'), t('modeSpeakSub'))}
    </div>
    <h3 class="section-title">${t('badges')} <a href="#/achievements" class="small">${got.size}/${ACHIEVEMENTS.length} ›</a></h3>
    <div class="badge-strip">${ACHIEVEMENTS.slice(0, 6).map((a) => `<div class="bd ${got.has(a.id) ? 'got' : ''}">${badge(a, got.has(a.id))}</div>`).join('')}</div>
    <h3 class="section-title" id="words">${t('myWords')} <small>${vocab.length}</small></h3>
    ${vocab.length ? `<input class="search" id="wq" placeholder="${t('searchWords')}" value="${esc(wordFilter)}">` : ''}
    <ul class="vocab" id="vl"></ul>
    ${vocab.length ? '' : `<div class="empty"><div class="empty-sticker" data-sticker="think"></div><p>${t('noWords')}</p></div>`}`;
  const list = () => {
    const q = wordFilter.toLowerCase();
    $('#vl').innerHTML = store.get('vocab')
      .filter((v) => !q || v.de.toLowerCase().includes(q) || (v.tr || '').toLowerCase().includes(q))
      .map((v) => `<li>
        <button class="say" data-say="${esc(v.de)}" aria-label="speak">🔊</button>
        <div class="vw"><b>${esc(v.de)}</b><span>${esc(v.tr)}</span>${v.context ? `<small>${esc(v.context)}</small>` : ''}</div>
        <div class="box-meter" title="${v.box}/5">${Array.from({ length: 5 }, (_, k) => `<i class="${k < v.box ? 'on' : ''}"></i>`).join('')}</div>
        <button class="icon-btn del" data-del="${v.id}" aria-label="${t('remove')}">✕</button></li>`).join('');
  };
  list();
  if (focus === 'words') requestAnimationFrame(() => $('#words')?.scrollIntoView());
  $('#wq') && ($('#wq').oninput = (e) => { wordFilter = e.target.value; list(); });
  view.onclick = (e) => {
    const m = e.target.closest('[data-mode]');
    if (m) return (location.hash = `#/study/${m.dataset.mode}`);
    const s = e.target.closest('[data-say]');
    if (s) return speak(s.dataset.say);
    const d = e.target.closest('[data-del]');
    if (d) { removeWord(d.dataset.del); renderLearn(view); }
  };
}
const mode = (id, ic, title, sub) =>
  `<button class="mode" data-mode="${id}"><span class="mode-ic">${ic}</span><span><b>${title}</b><small>${sub}</small></span><span class="chev">›</span></button>`;

// ---------- тренування ----------
export function renderStudy(view, kind, all = false) {
  let pool = store.get('vocab');
  if (!store.isPremium() && pool.length > FREE_CARD_LIMIT) pool = pool.slice(-FREE_CARD_LIMIT); // найстаріші N слів
  const ids = new Set(pool.map((w) => w.id));
  let deck = all ? shuffle(pool).slice(0, SESSION_SIZE) : dueWords().filter((w) => ids.has(w.id)).slice(0, SESSION_SIZE);
  const limited = !store.isPremium() && store.get('vocab').length > FREE_CARD_LIMIT;

  if (!store.get('vocab').length) return empty(view, 'think', t('noWords'), [['#/library', t('tabLibrary')]]);
  if ((kind === 'quiz' || kind === 'match') && store.get('vocab').length < 4) return empty(view, 'think', t('needMoreWords'), [['#/learn', t('toLearn')]]);
  if (!deck.length) return empty(view, 'sleep', t('allCaught'), [[`#/study/${kind}/all`, t('repeatAll')], ['#/learn', t('toLearn')]]);

  let i = 0, ok = 0, earned = 0;
  const session = (view._session = {}); // таймери старої вправи не мають перемальовувати новий екран
  const alive = () => view._session === session && location.hash.startsWith('#/study');
  if (kind === 'match') return renderMatch(view, shuffle(all ? pool : (deck.length >= 4 ? deck : pool)).slice(0, 5));
  const results = [];
  const total = deck.length;
  const head = () => `<header class="study-top"><a class="icon-btn" href="#/learn">✕</a>
    <div class="study-bar"><div style="width:${(i / total) * 100}%"></div></div><span>${i}/${total}</span></header>
    ${limited && i === 0 ? `<p class="limit-note">${t('freeLimit', { n: FREE_CARD_LIMIT })} <a href="#/premium">${t('goPremium')} →</a></p>` : ''}`;

  const next = (correct) => {
    if (!alive()) return;
    grade(deck[i].id, correct);
    results.push(correct);
    if (correct) { ok++; earned += XP.answer; }
    haptic();
    i++;
    if (i < total) show();
    else finish();
  };

  const show = () => {
    const w = deck[i];
    if (kind === 'cards') {
      view.innerHTML = `${head()}
        <div class="card-stage"><div class="flip" id="fc" tabindex="0">
          <div class="face front"><small>Deutsch</small><div class="big">${esc(w.de)}</div>
            ${w.context ? `<p class="ctx">${esc(w.context)}</p>` : ''}<span class="hint">${t('tapToFlip')}</span></div>
          <div class="face back"><small>${esc(langName(store.get('targetLang')))}</small><div class="big tr">${esc(w.tr)}</div>
            ${(w.alts || []).map((a) => `<p class="ctx"><i>${esc(a.pos)}</i> ${a.terms.slice(0, 4).map(esc).join(', ')}</p>`).join('')}</div>
        </div></div>
        <div class="study-actions"><button class="btn no" id="no">✗ ${t('dontKnow')}</button><button class="btn yes" id="yes">✓ ${t('know')}</button></div>`;
      const fc = $('#fc');
      fc.onclick = () => { fc.classList.toggle('flipped'); if (fc.classList.contains('flipped')) speak(w.de); };
      swipe(fc, (dir) => next(dir > 0));
      $('#no').onclick = () => next(false);
      $('#yes').onclick = () => next(true);
    } else if (kind === 'quiz') {
      const others = shuffle(store.get('vocab').filter((x) => x.id !== w.id && x.tr && x.tr !== w.tr)).slice(0, 3);
      const options = shuffle([w, ...others]);
      view.innerHTML = `${head()}
        <div class="quiz-q"><button class="say big-say" data-say="${esc(w.de)}">🔊</button><div class="big">${esc(w.de)}</div>
          ${w.context ? `<p class="ctx">${esc(w.context)}</p>` : ''}</div>
        <div class="options">${options.map((o) => `<button class="opt" data-id="${o.id}">${esc(o.tr)}</button>`).join('')}</div>`;
      $('[data-say]').onclick = () => speak(w.de);
      $$('.opt').forEach((b) => (b.onclick = () => {
        const right = b.dataset.id === w.id;
        $$('.opt').forEach((x) => { x.disabled = true; if (x.dataset.id === w.id) x.classList.add('right'); });
        if (!right) b.classList.add('wrong');
        setTimeout(() => next(right), right ? 650 : 1400);
      }));
    } else if (kind === 'speak') {
      view.innerHTML = `${head()}
        <h2 class="ex-title">${t('modeSpeak')}</h2><p class="ex-sub">${t('tapMic')}</p>
        <div class="say-card"><button class="say-play" data-say="${esc(w.de)}">🔊</button><div><b>${esc(w.de)}</b><small>${esc(w.tr)}</small></div></div>
        <div class="speak-zone"><div class="speak-owl" data-sticker="mic"></div>
          <button class="mic" id="mic" aria-label="mic"><svg viewBox="0 0 24 24" width="34" height="34"><rect x="8" y="2" width="8" height="13" rx="4" fill="currentColor"/><path d="M5 11a7 7 0 0 0 14 0M12 18v4" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/></svg></button></div>
        <div id="sres" class="wres"></div>
        <div class="study-actions"><button class="btn no" id="sk">${t('skip')}</button></div>`;
      $('[data-say]').onclick = () => speak(w.de);
      $('#sk').onclick = () => next(false);
      $('#mic').onclick = async () => {
        const mic = $('#mic');
        mic.classList.add('on');
        $('#sres').textContent = t('listening');
        try {
          const heard = await listen();
          mic.classList.toggle('on', false);
          const right = heard.some((h) => sameWord(h, w.de) || h.split(/\s+/).some((x) => sameWord(x, w.de)));
          $('#sres').innerHTML = right ? `<div class="right-msg">✓ ${t('correct')}</div>` : `<div class="wrong-msg">${esc(t('heard', { w: heard[0] || '…' }))}</div>`;
          if (right) { store.update('spoken', (n) => n + 1); earned += XP.speak; setTimeout(() => next(true), 900); }
        } catch {
          mic.classList.toggle('on', false);
          $('#sres').innerHTML = `<div class="wrong-msg">${t('noMic')}</div>`;
        }
      };
    } else {
      view.innerHTML = `${head()}
        <div class="quiz-q"><small>${t('modeWriteSub')}</small><div class="big tr">${esc(w.tr)}</div></div>
        <form class="write" id="wf" autocomplete="off">
          <input id="wa" autocapitalize="off" autocorrect="off" spellcheck="false" lang="de" placeholder="Deutsch…">
          <div class="umlauts">${['ä', 'ö', 'ü', 'ß', 'Ä', 'Ö', 'Ü'].map((c) => `<button type="button" data-ch="${c}">${c}</button>`).join('')}</div>
          <div class="study-actions"><button type="button" class="btn no" id="sk">${t('skip')}</button><button class="btn yes">${t('check')}</button></div>
        </form><div id="wres" class="wres"></div>`;
      const inp = $('#wa');
      setTimeout(() => inp.focus(), 50);
      $$('[data-ch]').forEach((b) => (b.onclick = () => { inp.value += b.dataset.ch; inp.focus(); }));
      const answer = (given) => {
        const right = given != null && sameWord(given, w.de);
        $('#wres').innerHTML = right ? `<div class="right-msg">✓ ${t('correct')} <b>${esc(w.de)}</b></div>` : `<div class="wrong-msg">${t('wrong')} <b>${esc(w.de)}</b></div>`;
        speak(w.de);
        $$('#wf button, #wf input').forEach((x) => (x.disabled = true));
        setTimeout(() => next(right), right ? 900 : 1800);
      };
      $('#wf').onsubmit = (e) => { e.preventDefault(); if (inp.value.trim()) answer(inp.value); };
      $('#sk').onclick = () => answer(null);
    }
  };

  const finish = () => finishScreen(view, { ok, total, results, earned, again: () => renderStudy(view, kind, true) });
  show();
}

// ---------- розпізнавання мовлення (німецька) ----------
function listen() {
  const plugin = window.Capacitor?.Plugins?.SpeechRecognition;
  if (plugin) {
    return plugin.requestPermissions()
      .then(() => plugin.start({ language: 'de-DE', maxResults: 5, partialResults: false, popup: false }))
      .then((r) => r.matches || []);
  }
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return Promise.reject(new Error('no speech'));
  return new Promise((resolve, reject) => {
    const r = new SR();
    r.lang = 'de-DE';
    r.maxAlternatives = 5;
    r.interimResults = false;
    r.onresult = (e) => resolve([...e.results[0]].map((x) => x.transcript));
    r.onerror = (e) => reject(e.error);
    r.onend = () => resolve([]);
    r.start();
  });
}

// ---------- «З'єднай слова» ----------
function renderMatch(view, words) {
  const session = (view._session = {});
  const alive = () => view._session === session && location.hash.startsWith('#/study');
  const left = shuffle(words), right = shuffle(words);
  let sel = null, done = 0, mistakes = 0, earned = 0;
  const results = [];
  view.innerHTML = `<header class="study-top"><a class="icon-btn" href="#/learn">✕</a>
      <div class="study-bar"><div id="mb" style="width:0"></div></div><span id="mc">0/${words.length}</span></header>
    <h2 class="ex-title">${t('modeMatch')}</h2><p class="ex-sub">${t('modeMatchSub')}</p>
    <div class="match"><div class="mcol">${left.map((w) => `<button class="mt" data-side="de" data-id="${w.id}">${esc(w.de)}</button>`).join('')}</div>
      <div class="mcol">${right.map((w) => `<button class="mt" data-side="tr" data-id="${w.id}">${esc(w.tr)}</button>`).join('')}</div></div>
    <div class="match-owl" data-sticker="wink"></div>`;
  view.onclick = (e) => {
    const b = e.target.closest('.mt');
    if (!b || b.disabled) return;
    if (b.dataset.side === 'de') speak(b.textContent);
    if (!sel || sel.dataset.side === b.dataset.side) {
      $$('.mt.sel').forEach((x) => x.classList.toggle('sel', false));
      b.classList.add('sel');
      sel = b;
      return;
    }
    if (sel.dataset.id === b.dataset.id) {
      for (const x of [sel, b]) { x.classList.toggle('sel', false); x.classList.add('paired'); x.disabled = true; }
      grade(b.dataset.id, true);
      results.push(true);
      earned += XP.answer;
      done++;
      haptic();
      $('#mb').style.width = (done / words.length) * 100 + '%';
      $('#mc').textContent = `${done}/${words.length}`;
      if (done === words.length) {
        setTimeout(() => alive() && finishScreen(view, {
          ok: Math.max(0, words.length - mistakes), total: words.length, results, earned, again: () => renderStudy(view, 'match', true),
        }), 500);
      }
    } else {
      mistakes++;
      results.push(false);
      for (const x of [sel, b]) { x.classList.add('miss'); setTimeout(() => { x.classList.toggle('miss', false); x.classList.toggle('sel', false); }, 450); }
    }
    sel = null;
  };
}

// ---------- екран «Урок завершено» ----------
function finishScreen(view, { ok, total, results, earned, again }) {
  view.onclick = null;
  const perfect = ok === total && total > 0;
  if (perfect) { earned += XP.perfectBonus; store.update('perfect', (n) => n + 1); }
  store.update('sessions', (n) => n + 1);
  const lvlUp = addXP(earned);
  const { level } = levelInfo();
  const colors = ['#ee6c4d', '#f4a261', '#7fb3e6', '#2a9d8f', '#e9c46a', '#c77dff'];
  view.innerHTML = `<div class="finish">
    <div class="finish-sticker">${sticker(perfect ? 'party' : ok >= total / 2 ? 'wave' : 'heart')}</div>
    <h1>${lvlUp ? t('levelUp') : t('lessonDone')}</h1>
    <p class="muted">${t('amazing')}</p>
    <div class="rewards">
      <div><span>🔥</span><b>${store.streak()}</b><small>${t('streakLabel')}</small></div>
      <div><span>⭐</span><b>+${earned}</b><small>${t('xpEarned')}</small></div>
      <div><span>👑</span><b>${level}</b><small>${t('levelLabel')}</small></div>
    </div>
    <p class="score">${t('sessionStats', { ok, n: total })}</p>
    <div class="dots-res">${results.map((r) => `<i class="${r ? 'ok' : 'bad'}"></i>`).join('')}</div>
    <div class="study-actions"><button class="btn ghost" id="again">${t('again')}</button><a class="btn" href="#/learn">${t('continueBtn2')}</a></div>
  </div>
  <div class="confetti">${Array.from({ length: 24 }, (_, i) => `<i style="--x:${(i * 41) % 100}vw;--d:${(i % 6) * 0.15}s;--c:${colors[i % 6]}"></i>`).join('')}</div>`;
  $('#again').onclick = again;
  checkAchievements();
}

// ---------- усі досягнення ----------
export function renderAchievements(view) {
  const got = new Set(store.get('achievements'));
  view.innerHTML = `<header class="top"><a class="icon-btn" href="#/learn">←</a><h1 class="h-coll">${t('qAchievements')}</h1><span></span></header>
    <div class="card rewards flat">
      <div><span>🔥</span><b>${store.streak()}</b><small>${t('streakLabel')}</small></div>
      <div><span>👑</span><b>${levelInfo().level}</b><small>${t('levelLabel')}</small></div>
      <div><span>🧠</span><b>${masteredCount()}</b><small>${t('learnedLabel')}</small></div>
    </div>
    <h3 class="section-title">${t('badges')} <small>${got.size}/${ACHIEVEMENTS.length}</small></h3>
    <div class="badge-grid">${ACHIEVEMENTS.map((a) => `<div class="bcell ${got.has(a.id) ? 'got' : ''}">${badge(a, got.has(a.id))}<small>${t('ach.' + a.id)}</small></div>`).join('')}</div>`;
}

function empty(view, pose, text, links) {
  view.innerHTML = `<header class="study-top"><a class="icon-btn" href="#/learn">✕</a></header>
    <div class="finish"><div class="finish-sticker">${sticker(pose)}</div><p>${text}</p>
    <div class="study-actions">${links.map(([href, label], i) => `<a class="btn ${i ? 'ghost' : ''}" href="${href}">${label}</a>`).join('')}</div></div>`;
}

// Свайп картки: вправо — «знаю», вліво — «не знаю».
function swipe(el, cb) {
  let x0 = null, dx = 0;
  el.addEventListener('pointerdown', (e) => { x0 = e.clientX; dx = 0; el.style.transition = 'none'; });
  el.addEventListener('pointermove', (e) => {
    if (x0 == null) return;
    dx = e.clientX - x0;
    if (Math.abs(dx) > 8) el.style.transform = `translateX(${dx}px) rotate(${dx / 20}deg)`;
    el.parentElement.dataset.swipe = dx > 40 ? 'yes' : dx < -40 ? 'no' : '';
  });
  const end = () => {
    if (x0 == null) return;
    el.style.transition = '';
    el.parentElement.dataset.swipe = '';
    if (Math.abs(dx) > 90) {
      el.style.transform = `translateX(${Math.sign(dx) * 600}px) rotate(${Math.sign(dx) * 25}deg)`;
      el.onclick = null;
      setTimeout(() => cb(Math.sign(dx)), 180);
    } else {
      el.style.transform = '';
      if (Math.abs(dx) > 8) { el.addEventListener('click', (e) => e.stopImmediatePropagation(), { capture: true, once: true }); }
    }
    x0 = null;
  };
  el.addEventListener('pointerup', end);
  el.addEventListener('pointercancel', end);
}

export { MASTERED_BOX, closeSheet, openSheet };
