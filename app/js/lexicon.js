// Словник Лесі: «бібліотека всіх слів» німецької (≈96 тис. слів, ≈465 тис. форм, з Wiktionary, CC BY-SA 4.0).
// Будь-яка форма з будь-якої книжки (spielte, Häuser, Kindern) → початкова форма з граматикою:
// рід і артикль, множина, родовий, форми дієслова, ступені порівняння, вимова (IPA), значення.
// Дані лежать в app/lexicon/<шард>.json і завантажуються лише тоді, коли потрібні.

const shards = new Map();
function shardKey(w) {
  const s = w.toLowerCase().normalize('NFKD').replace(/[^a-z]/g, '');
  return (s.slice(0, 2) || '_').padEnd(2, '_');
}
function loadShard(k) {
  if (!shards.has(k)) shards.set(k, fetch(`lexicon/${k}.json`).then((r) => (r.ok ? r.json() : { f: {}, l: {} })).catch(() => ({ f: {}, l: {} })));
  return shards.get(k);
}
async function lemma(key) {
  const w = key.slice(0, key.lastIndexOf('|'));
  return (await loadShard(shardKey(w))).l[key] || null;
}

const POS_RANK = { noun: 0, verb: 1, adj: 2, adv: 3, pron: 4, prep: 5, conj: 6, det: 7, article: 7, num: 8, particle: 9, intj: 10, name: 11 };

/** @returns {Promise<Array<object>>} записи словника, найімовірніша — перша */
export async function lookup(raw, { capitalized = null } = {}) {
  const word = raw.replace(/^[-'’]+|[-'’]+$/g, '');
  if (!word) return [];
  const lower = word.toLowerCase();
  const tryForms = [lower];
  // запасний варіант для старих/рідкісних форм: відкидаємо закінчення (ungeheueren → ungeheuer)
  for (const end of ['ern', 'en', 'em', 'er', 'es', 'est', 'e', 'n', 's', 'st', 't']) {
    if (lower.length > end.length + 3 && lower.endsWith(end)) tryForms.push(lower.slice(0, -end.length));
  }
  let keys = [];
  for (const f of tryForms) {
    keys = (await loadShard(shardKey(f))).f[f] || [];
    if (keys.length) break;
  }
  const entries = (await Promise.all(keys.slice(0, 8).map(lemma))).filter(Boolean);
  const isCap = capitalized ?? /^[A-ZÄÖÜ]/.test(word);
  entries.sort((a, b) => score(a) - score(b));
  function score(e) {
    let s = POS_RANK[e.p] ?? 12;
    if (e.w.toLowerCase() === lower) s -= 3;
    if (isCap && e.p === 'noun') s -= 4; // з великої літери посеред речення — майже завжди іменник
    if (!isCap && e.p === 'noun') s += 4;
    if (e.p === 'name') s += 6;
    if (/^[A-ZÄÖÜ]/.test(e.w) && e.p !== 'noun' && e.p !== 'name') s += 3; // «Sie», «Du» — гірше, ніж «sie», «du»
    if (/obsolete|archaic|alternative form/i.test(e.en?.[0] || '')) s += 5;
    return s;
  }
  return entries;
}

export const ARTICLE = { m: 'der', f: 'die', n: 'das' };
export const POS_NAME = {
  uk: { noun: 'іменник', verb: 'дієслово', adj: 'прикметник', adv: 'прислівник', pron: 'займенник', prep: 'прийменник', conj: 'сполучник', num: 'числівник', det: 'означник', article: 'артикль', particle: 'частка', intj: 'вигук', name: 'власна назва' },
  ru: { noun: 'существительное', verb: 'глагол', adj: 'прилагательное', adv: 'наречие', pron: 'местоимение', prep: 'предлог', conj: 'союз', num: 'числительное', det: 'определитель', article: 'артикль', particle: 'частица', intj: 'междометие', name: 'имя собственное' },
  en: { noun: 'noun', verb: 'verb', adj: 'adjective', adv: 'adverb', pron: 'pronoun', prep: 'preposition', conj: 'conjunction', num: 'numeral', det: 'determiner', article: 'article', particle: 'particle', intj: 'interjection', name: 'proper noun' },
};

// Приблизна вимова кирилицею з IPA — для тих, хто ще не читає транскрипцію.
const IPA_MAP = [
  [/t͡s|ts/g, 'ц'], [/t͡ʃ|tʃ/g, 'ч'], [/aɪ̯|aɪ/g, 'ай'], [/aʊ̯|aʊ/g, 'ау'], [/ɔʏ̯|ɔɪ̯|ɔʏ|ɔɪ/g, 'ой'],
  [/ʃ/g, 'ш'], [/ç/g, 'хь'], [/x|χ/g, 'х'], [/ʁ|ʀ|r/g, 'р'], [/ŋ/g, 'нг'], [/ʒ/g, 'ж'], [/j/g, 'й'],
  [/ɐ̯/g, 'а'], [/ɐ/g, 'а'], [/ə/g, 'е'], [/øː|ø|œ/g, 'ьо'], [/yː|y|ʏ/g, 'ю'],
  [/aː|a/g, 'а'], [/eː|e/g, 'е'], [/ɛː|ɛ/g, 'е'], [/iː|i|ɪ/g, 'і'], [/oː|o|ɔ/g, 'о'], [/uː|u|ʊ/g, 'у'],
  [/b/g, 'б'], [/d/g, 'д'], [/ɡ|g/g, 'г'], [/k/g, 'к'], [/l/g, 'л'], [/m/g, 'м'], [/n/g, 'н'], [/p/g, 'п'],
  [/t/g, 'т'], [/f/g, 'ф'], [/v/g, 'в'], [/z/g, 'з'], [/s/g, 'с'], [/h/g, 'х'], [/ʔ/g, ''],
];
export function ipaToCyr(ipa, lang = 'uk') {
  if (!ipa) return '';
  let s = ipa.replace(/[/[\]]/g, '').split(/\s*,\s*/)[0].replace(/[̯̩.ː]/g, (m) => (m === 'ː' ? 'ː' : ''));
  // наголос: ˈ перед складом → велика літера в голосній після нього
  const stressed = s.indexOf('ˈ');
  s = s.replace(/[ˈˌ]/g, '');
  let out = s;
  for (const [re, rep] of IPA_MAP) out = out.replace(re, rep);
  out = out.replace(/ː/g, '');
  if (lang === 'ru') out = out.replace(/і/g, 'и').replace(/^е/, 'э');
  if (stressed >= 0) {
    const vowels = /[аеіоуюиэьо]/i;
    // приблизно: позначаємо першу голосну після позиції наголосу
    const before = s.slice(0, stressed);
    let pre = before;
    for (const [re, rep] of IPA_MAP) pre = pre.replace(re, rep);
    pre = pre.replace(/ː/g, '');
    if (lang === 'ru') pre = pre.replace(/і/g, 'и');
    const idx = out.slice(pre.length).search(vowels);
    if (idx >= 0) { const i = pre.length + idx; out = out.slice(0, i) + out[i].toUpperCase() + out.slice(i + 1); }
  }
  return out;
}

// Готові рядки граматики для картки слова
export function grammarLines(e) {
  const L = [];
  if (e.p === 'noun') {
    const art = ARTICLE[e.g];
    L.push(['Nominativ', `${art ? art + ' ' : ''}${e.w}`]);
    if (e.gen) L.push(['Genitiv', `${e.g === 'f' ? 'der' : 'des'} ${e.gen}`]);
    if (e.pl) L.push(['Plural', `die ${e.pl}`]);
  } else if (e.p === 'verb') {
    L.push(['Infinitiv', e.w]);
    if (e.v?.[0]) L.push(['Präsens', `er/sie/es ${e.v[0]}`]);
    if (e.v?.[1]) L.push(['Präteritum', `er/sie/es ${e.v[1]}`]);
    if (e.v?.[2]) L.push(['Perfekt', `er/sie/es ${e.aux === 'sein' ? 'ist' : 'hat'} ${e.v[2]}`]);
  } else if (e.p === 'adj' && e.cmp) {
    L.push(['Positiv', e.w]);
    if (e.cmp[0]) L.push(['Komparativ', e.cmp[0]]);
    if (e.cmp[1]) L.push(['Superlativ', e.cmp[1]]);
  }
  return L;
}
export const headword = (e) => (e.p === 'noun' && ARTICLE[e.g] ? `${ARTICLE[e.g]} ${e.w}` : e.w);
