// Головна: привітання сови, прогрес (рівень і XP), швидкі дії, серія днів, «продовжити читання».
import * as store from './store.js';
import { t } from './i18n.js';
import { esc, speak } from './ui.js';
import { levelInfo, week, todayXP } from './xp.js';
import { dueWords, masteredCount } from './srs.js';
import { loadIndex } from './library.js';
import { LOGO_MARK } from './stickers.js';

export function topStats(flag = true) {
  const { level } = levelInfo();
  return `<div class="top-stats">
    ${flag ? '<span class="flag-de" title="Deutsch"></span>' : ''}
    <span class="ts"><b>🔥</b>${store.streak()}</span>
    <span class="ts"><b>👑</b>${level}</span>
    <span class="ts"><b>🧠</b>${masteredCount()}</span>
  </div>`;
}

export async function renderHome(view) {
  const { level, inLevel, need } = levelInfo();
  const streak = store.streak();
  const due = dueWords().length;
  const goal = store.get('dailyGoal');
  const tx = todayXP();
  const books = await loadIndex();
  const recent = books.map((b) => ({ b, p: store.get('progress')[b.id] }))
    .filter((x) => x.p && !x.p.done && !(x.b.premium && !store.isPremium())).sort((a, b) => b.p.at - a.p.at)[0];
  const vocab = store.get('vocab');
  const wod = vocab.length ? vocab[(new Date().getDate() * 7) % vocab.length] : null;
  const days = week();
  const names = t('weekDays');

  view.innerHTML = `
    <header class="home-top">${topStats()}</header>
    <section class="hero">
      <div class="hero-owl" data-sticker="${tx >= goal ? 'party' : 'wave'}"></div>
      <h1>${t('ob1Title')}</h1>
      <p>${t('homeHello')}</p>
    </section>

    <section class="card progress-card">
      <div class="row-between tight"><b>${t('yourProgress')}</b><span class="lvl-text">${t('level')} ${level}</span></div>
      <div class="xpbar"><div style="width:${(inLevel / need) * 100}%"></div></div>
      <div class="row-between tight muted small"><span>${t('dailyGoal')}: ${Math.min(tx, goal)} / ${goal} XP</span><span>${inLevel} / ${need} XP</span></div>
      <div class="quick">
        <a href="#/library"><span class="qi qi-blue">📖</span>${t('qRead')}</a>
        <a href="#/learn"><span class="qi qi-red">🏋️</span>${t('qPractice')}</a>
        <a href="#/achievements"><span class="qi qi-gold">🏆</span>${t('qAchievements')}</a>
        <a href="#/learn/words"><span class="qi qi-green">🗂️</span>${t('qWords')}</a>
      </div>
    </section>

    <section class="card streak-card">
      <div class="streak-head"><span class="flame">🔥</span><div><b>${t('dayStreak')}</b>
        <div class="hot small">${streak ? t('daysInRow', { n: streak }) : t('startStreak')}</div></div></div>
      <div class="week">${days.map((d, i) => `<div class="wd ${d.done ? 'done' : ''} ${d.today ? 'today' : ''}">
        <small>${names[i]}</small><i>${d.done ? '✓' : ''}</i></div>`).join('')}</div>
    </section>

    ${recent ? `<button class="continue" data-book="${recent.b.id}">
      <img src="${recent.b.cover || `covers/${recent.b.id}.svg`}" alt=""><div><small>${t('continue')}</small><strong>${esc(recent.b.title)}</strong>
      <span class="muted">${esc(recent.b.author)}</span><div class="bar"><div style="width:${Math.round(recent.p.pct * 100)}%"></div></div></div>
      <span class="play">▶</span></button>` : ''}

    ${due ? `<a class="card due-card" href="#/study/cards"><div class="due-ic">🃏</div><div><b>${t('dueNow', { n: due })}</b>
      <small class="muted">${t('modeCardsSub')}</small></div><span class="btn small-btn">${t('practiceNow')}</span></a>` : ''}

    ${wod ? `<section class="card wod"><small class="muted">${t('wordOfDay')}</small>
      <div class="wod-row"><button class="say" data-say="${esc(wod.de)}">🔊</button><div><b class="wod-de">${esc(wod.de)}</b>
      <div class="wod-tr">${esc(wod.tr)}</div></div></div>
      ${wod.context ? `<p class="wod-ctx">${esc(wod.context)}</p>` : ''}</section>` : ''}
    <p class="about small"><i class="logo">${LOGO_MARK}</i>Lesefreund</p>`;
  view.onclick = (e) => {
    const s = e.target.closest('[data-say]');
    if (s) speak(s.dataset.say);
  };
}
