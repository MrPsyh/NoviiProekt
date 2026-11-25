// Маскот Lesefreund — сова Лесі. Векторна (SVG): об'ємне тіло, лицьовий диск, бурштинові очі,
// пір'я на грудях і крилах, кігті. Різні пози-стікери: sticker('read'), sticker('wave')…
// Працює офлайн і чітка на будь-якому екрані.

const DEFS = `<defs>
  <radialGradient id="owlBody" cx="38%" cy="28%" r="80%"><stop offset="0" stop-color="#5b7fae"/><stop offset=".55" stop-color="#3a5a85"/><stop offset="1" stop-color="#233a59"/></radialGradient>
  <radialGradient id="owlDisc" cx="50%" cy="40%" r="65%"><stop offset="0" stop-color="#7d9cc4"/><stop offset="1" stop-color="#4c6d98"/></radialGradient>
  <linearGradient id="owlBelly" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f6f9fc"/><stop offset="1" stop-color="#cfdceb"/></linearGradient>
  <linearGradient id="owlWing" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2f4b72"/><stop offset="1" stop-color="#1b2d47"/></linearGradient>
  <radialGradient id="owlIris" cx="50%" cy="45%" r="55%"><stop offset="0" stop-color="#ffd27a"/><stop offset=".7" stop-color="#f4a03a"/><stop offset="1" stop-color="#c96a16"/></radialGradient>
  <linearGradient id="owlBeak" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffc06b"/><stop offset="1" stop-color="#e07a2c"/></linearGradient>
  <linearGradient id="owlFoot" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffb35c"/><stop offset="1" stop-color="#e2832f"/></linearGradient>
</defs>`;

function eye(cx, mode, look = [0, 0]) {
  const [dx, dy] = look;
  if (mode === 'happy') return `<path d="M${cx - 13} ${96}q13-15 26 0" stroke="#14213a" stroke-width="5" fill="none" stroke-linecap="round"/>`;
  if (mode === 'closed') return `<path d="M${cx - 13} ${92}q13 13 26 0" stroke="#14213a" stroke-width="4.5" fill="none" stroke-linecap="round"/>
    <path d="M${cx - 10} ${98}l-3 4M${cx} ${100}v5M${cx + 10} ${98}l3 4" stroke="#14213a" stroke-width="2" stroke-linecap="round"/>`;
  return `<circle cx="${cx}" cy="93" r="18" fill="#fdfdfb"/>
    <circle cx="${cx}" cy="93" r="18" fill="none" stroke="#2b4466" stroke-width="2.5" opacity=".5"/>
    <circle cx="${cx + dx}" cy="${94 + dy}" r="12" fill="url(#owlIris)"/>
    <circle cx="${cx + dx}" cy="${94 + dy}" r="6.8" fill="#0d1526"/>
    <circle cx="${cx + dx + 4}" cy="${90 + dy}" r="3.4" fill="#fff"/>
    <circle cx="${cx + dx - 3.5}" cy="${98 + dy}" r="1.6" fill="#fff" opacity=".8"/>
    <path d="M${cx - 17} ${84}q17-10 34 0q-17-5-34 0z" fill="#3a5a85" opacity=".35"/>`;
}

function wing(side, up) {
  // ліве крило; праве — дзеркальне. Підняте крило — окремий контур (махає)
  const down = `<path d="M54 106c-18 14-22 50-2 74c4-10 7-20 10-30c3-14 2-30-8-44z" fill="url(#owlWing)"/>
    <path d="M52 132c-4 10-4 24 0 36M58 128c-2 12-2 26 1 38" stroke="#5b7fae" stroke-width="2" fill="none" opacity=".55" stroke-linecap="round"/>
    <path d="M44 168q4 8 8 12q2-8 6-10" fill="#16263d"/>`;
  const raised = `<path d="M56 116c-14-6-26-22-32-46c-2-8 4-10 8-4c3 5 6 8 9 9c-2-6-1-12 4-10c3 1 4 6 5 10c0-6 3-9 6-7c4 2 4 10 4 16c2 10 2 22-4 32z" fill="url(#owlWing)"/>
    <path d="M40 76c4 10 8 18 14 24M48 74c2 10 4 18 8 24" stroke="#5b7fae" stroke-width="2" fill="none" opacity=".55" stroke-linecap="round"/>`;
  const w = up ? raised : down;
  return side === 'R' ? `<g transform="translate(200 0) scale(-1 1)">${w}</g>` : w;
}

function owl({ eyes = 'open', look = [0, 0], left = 'down', right = 'down', brows = 'calm', back = '', front = '', blush = true } = {}) {
  const [le, re] = Array.isArray(eyes) ? eyes : [eyes, eyes];
  const browPath = brows === 'raised'
    ? 'M62 72q14-10 30-2M138 72q-14-10-30-2'
    : brows === 'focus' ? 'M62 76q16-2 30 6M138 76q-16-2-30 6' : 'M63 74q14-6 29 2M137 74q-14-6-29 2';
  const chest = [];
  for (let r = 0; r < 4; r++) for (let c = 0; c < 4 - (r % 2); c++) {
    const x = 80 + c * 13 + (r % 2) * 6.5, y = 134 + r * 11;
    chest.push(`<path d="M${x - 4} ${y}l4 4 4-4" stroke="#9fb3cb" stroke-width="2" fill="none" stroke-linecap="round"/>`);
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" class="sticker" aria-hidden="true">${DEFS}
  ${back}
  <ellipse cx="100" cy="192" rx="50" ry="6" fill="#0b1626" opacity=".12"/>
  ${left === 'down' ? wing('L', false) : ''}${right === 'down' ? wing('R', false) : ''}
  <path d="M64 70c-7-14-12-28-20-44c16 6 30 16 40 28zM136 70c7-14 12-28 20-44c-16 6-30 16-40 28z" fill="#2c4770"/>
  <path d="M60 60c-3-8-6-15-10-23c8 4 15 9 21 15zM140 60c3-8 6-15 10-23c-8 4-15 9-21 15z" fill="#6d8fbb" opacity=".7"/>
  <path d="M100 44c40 0 58 38 56 78c-2 40-24 66-56 66s-54-26-56-66c-2-40 16-78 56-78z" fill="url(#owlBody)"/>
  <path d="M60 64c10-12 24-18 40-18" stroke="#8eaad0" stroke-width="3" fill="none" opacity=".35" stroke-linecap="round"/>
  <ellipse cx="100" cy="150" rx="35" ry="36" fill="url(#owlBelly)"/>
  ${chest.join('')}
  <path d="M100 70c-16-14-50-8-48 22c2 26 32 32 48 20c16 12 46 6 48-20c2-30-32-36-48-22z" fill="url(#owlDisc)"/>
  <path d="M100 72v34" stroke="#3a5a85" stroke-width="2" opacity=".35"/>
  <path d="${browPath}" stroke="#1d3150" stroke-width="4" fill="none" stroke-linecap="round"/>
  ${eye(81, le, look)}${eye(119, re, look)}
  ${blush ? '<ellipse cx="62" cy="110" rx="7" ry="4.5" fill="#ff8a7a" opacity=".45"/><ellipse cx="138" cy="110" rx="7" ry="4.5" fill="#ff8a7a" opacity=".45"/>' : ''}
  <path d="M93 104q7-5 14 0l-5 15q-2 4-4 0z" fill="url(#owlBeak)"/>
  <path d="M95 105q5-3 10 0" stroke="#fff3df" stroke-width="1.6" fill="none" opacity=".8" stroke-linecap="round"/>
  ${left === 'up' ? wing('L', true) : ''}${right === 'up' ? wing('R', true) : ''}
  <g fill="url(#owlFoot)"><path d="M80 182q-6 6-8 10h6q2-4 4-6q1 5 1 8h6q0-5-2-10q4 3 6 8h6q-4-8-11-12z"/>
    <path d="M120 182q6 6 8 10h-6q-2-4-4-6q-1 5-1 8h-6q0-5 2-10q-4 3-6 8h-6q4-8 11-12z"/></g>
  <path d="M72 192l-1 3M79 192v3M90 192l1 3M128 192l1 3M121 192v3M110 192l-1 3" stroke="#5a3311" stroke-width="2" stroke-linecap="round"/>
  ${front}
</svg>`;
}

const book = `<g transform="translate(56 138)">
  <path d="M2 6q20-10 42-1v38q-22-9-42 1z" fill="#ef6f4a"/><path d="M44 5q22-9 42 1v38q-20-10-42-1z" fill="#f7a44c"/>
  <path d="M44 5v38" stroke="#b9472c" stroke-width="2.5"/>
  <path d="M9 14q15-6 29 0M9 22q15-6 29 0M9 30q15-6 29 0M50 14q15-6 29 0M50 22q15-6 29 0M50 30q15-6 29 0" stroke="#fff" stroke-width="2" opacity=".75" fill="none" stroke-linecap="round"/>
  <path d="M-4 30q8-6 12 6M92 30q-8-6-12 6" fill="#233a59"/></g>`;
const sparkle = (x, y, s = 1, c = '#f4a261') =>
  `<path transform="translate(${x} ${y}) scale(${s})" d="M0-11l3 8 8 3-8 3-3 8-3-8-8-3 8-3z" fill="${c}"/>`;
const heart = (x, y, s = 1) => `<path transform="translate(${x} ${y}) scale(${s})" d="M0 4c-6-8-16-2-12 6c3 5 12 10 12 10s9-5 12-10c4-8-6-14-12-6z" fill="#ff6b6b"/>`;
const confetti = ['#ee6c4d', '#f4a261', '#7fb3e6', '#2a9d8f', '#e9c46a', '#c77dff']
  .map((c, i) => `<rect x="${16 + i * 31}" y="${10 + (i % 2) * 24}" width="8" height="15" rx="2" fill="${c}" transform="rotate(${i * 41 - 50} ${20 + i * 31} ${18 + (i % 2) * 24})"/>`).join('');

const POSES = {
  read: () => owl({ look: [2, 4], brows: 'focus', front: book }),
  wave: () => owl({ eyes: 'happy', right: 'up', brows: 'raised', back: sparkle(30, 56, 0.8, '#7fb3e6') + heart(170, 44, 0.8) }),
  think: () => owl({ look: [-4, -5], brows: 'raised', back: `<text x="146" y="54" font-size="46" font-weight="900" fill="#ee6c4d" font-family="system-ui,sans-serif">?</text>` }),
  party: () => owl({ eyes: 'happy', left: 'up', right: 'up', brows: 'raised', back: confetti + sparkle(170, 70) + sparkle(28, 80, 0.7, '#7fb3e6') }),
  sleep: () => owl({ eyes: 'closed', blush: true, back: `<text x="140" y="58" font-size="24" font-weight="900" fill="#7fb3e6" font-family="system-ui">z</text><text x="158" y="36" font-size="32" font-weight="900" fill="#7fb3e6" font-family="system-ui">Z</text>` }),
  star: () => owl({ eyes: 'happy', brows: 'raised', back: `<path d="M100 2l8 17 19 3-14 13 4 19-17-9-17 9 4-19-14-13 19-3z" fill="#ffc93c" stroke="#e9a100" stroke-width="2"/>` + sparkle(36, 52) + sparkle(166, 66, 0.8) }),
  globe: () => owl({ look: [5, 3], front: `<g transform="translate(140 140)"><circle r="22" fill="#7fb3e6"/><path d="M-12-8q8 4 6 12q-6 2-8 10M6-18q2 8 10 8q2 8-4 14" fill="#2a9d8f" opacity=".85"/><circle r="22" fill="none" stroke="#233a59" stroke-width="3"/></g>`, right: 'up' }),
  heart: () => owl({ eyes: 'happy', back: heart(164, 40, 1.3) + heart(34, 64, 0.8) }),
  fire: () => owl({ eyes: 'happy', brows: 'raised', back: `<path d="M100 0q34 26 12 56q4-16-12-24q2 18-16 24q-16-30 16-56z" fill="#ff7a45"/><path d="M100 28q14 12 3 28q-14-4-9-16z" fill="#ffd166"/>` }),
  wink: () => owl({ eyes: ['happy', 'open'], look: [0, 1], right: 'up', brows: 'raised' }),
  mic: () => owl({ look: [3, 2], front: `<g transform="translate(138 120)"><rect x="-8" y="-20" width="16" height="28" rx="8" fill="#1d3557"/><path d="M-13 0q0 14 13 14t13-14M0 14v10" stroke="#1d3557" stroke-width="3.5" fill="none" stroke-linecap="round"/></g>`, right: 'up' }),
};

export function sticker(name = 'wave') {
  return (POSES[name] || POSES.wave)();
}

// Логотип / водяний знак: силует сови.
export const LOGO_MARK = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" aria-hidden="true">
  <path d="M18 20l-5-13 12 8zM46 20l5-13-12 8z" fill="currentColor"/>
  <ellipse cx="32" cy="38" rx="20" ry="23" fill="currentColor"/>
  <circle cx="25" cy="32" r="7" fill="var(--wm-bg, #fff)"/><circle cx="39" cy="32" r="7" fill="var(--wm-bg, #fff)"/>
  <circle cx="26" cy="33" r="3" fill="currentColor"/><circle cx="40" cy="33" r="3" fill="currentColor"/>
  <path d="M30 40l2 4 2-4z" fill="var(--wm-bg, #fff)"/></svg>`;

// Досягнення: значки-шестикутники; відкриваються за прогрес.
export const ACHIEVEMENTS = [
  { id: 'first-word', icon: '🔤', color: ['#4f8ff7', '#2f5fcf'], pose: 'globe', test: (s) => s.words >= 1 },
  { id: 'ten-words', icon: '📘', color: ['#55b3f0', '#2b7fc0'], pose: 'read', test: (s) => s.words >= 10 },
  { id: 'fifty-words', icon: '📚', color: ['#7b6cf6', '#5141c9'], pose: 'star', test: (s) => s.words >= 50 },
  { id: 'first-session', icon: '⭐', color: ['#2f4b72', '#1b2d47'], pose: 'party', test: (s) => s.sessions >= 1 },
  { id: 'perfect', icon: '🏅', color: ['#ffb547', '#f0851b'], pose: 'star', test: (s) => s.perfect >= 1 },
  { id: 'streak-3', icon: '🔥', color: ['#ff8a5b', '#e5532f'], pose: 'fire', test: (s) => s.streak >= 3 },
  { id: 'streak-7', icon: '❤️', color: ['#ff6b8b', '#d43d63'], pose: 'heart', test: (s) => s.streak >= 7 },
  { id: 'mastered-10', icon: '🧠', color: ['#3cc0a0', '#1f8f73'], pose: 'wave', test: (s) => s.mastered >= 10 },
  { id: 'book-done', icon: '📖', color: ['#46b37a', '#2a8656'], pose: 'sleep', test: (s) => s.booksDone >= 1 },
  { id: 'speaker', icon: '🎤', color: ['#5bc0eb', '#2e8fbf'], pose: 'mic', test: (s) => s.spoken >= 5 },
  { id: 'level-5', icon: '👑', color: ['#ffd166', '#e9a100'], pose: 'star', test: (s) => s.level >= 5 },
  { id: 'polyglot', icon: '🌍', color: ['#9aa5b1', '#6b7785'], pose: 'globe', test: (s) => s.words >= 200 },
];

export function badge(a, got = true) {
  const [c1, c2] = got ? a.color : ['#d5d9df', '#aeb5bf'];
  const gid = 'bg' + a.id.replace(/\W/g, '');
  return `<svg viewBox="0 0 100 110" class="badge-svg" aria-hidden="true">
    <defs><linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${c1}"/><stop offset="1" stop-color="${c2}"/></linearGradient></defs>
    <path d="M50 4l42 24v52L50 104 8 80V28z" fill="url(#${gid})" stroke="#fff" stroke-width="5" stroke-linejoin="round"/>
    <path d="M50 14l33 19v12Q50 30 17 45V33z" fill="#fff" opacity=".18"/>
    <text x="50" y="68" text-anchor="middle" font-size="36" ${got ? '' : 'opacity=".55"'}>${got ? a.icon : '🔒'}</text></svg>`;
}

// Заповнює всі елементи з data-sticker="поза" відповідним SVG.
export function hydrateStickers(root = document) {
  root.querySelectorAll('[data-sticker]:not([data-done])').forEach((el) => {
    el.innerHTML = sticker(el.dataset.sticker);
    el.dataset.done = '1';
  });
}
