// Вежливый клиент API немецкой Wikisource: по одному запросу, пауза между запросами,
// соблюдение Retry-After при 429. Используется импортёром книг.
'use strict';
const API = 'https://de.wikisource.org/w/api.php';
const UA = 'LesefreundImporter/0.2 (educational German reading app; book import script)';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let last = 0;
const GAP = Number(process.env.WS_GAP_MS || 1500);

async function api(params, tries = 8) {
  const url = API + '?' + new URLSearchParams({ format: 'json', formatversion: '2', maxlag: '5', ...params });
  for (let i = 0; i < tries; i++) {
    const wait = last + GAP - Date.now();
    if (wait > 0) await sleep(wait);
    last = Date.now();
    let res;
    try {
      res = await fetch(url, { headers: { 'User-Agent': UA, 'Api-User-Agent': UA } });
    } catch (e) {
      await sleep(5000 * (i + 1));
      continue;
    }
    if (res.status === 429 || res.status >= 500) {
      const ra = Number(res.headers.get('retry-after')) || 20;
      process.stderr.write(`  …${res.status}, жду ${ra}s\n`);
      await sleep((ra + 1) * 1000);
      continue;
    }
    const data = await res.json();
    if (data.error?.code === 'maxlag') { await sleep(6000); continue; }
    if (data.error) throw new Error(data.error.info || data.error.code);
    return data;
  }
  throw new Error('Wikisource недоступна: ' + url);
}

async function search(q, limit = 8) {
  const d = await api({ action: 'query', list: 'search', srsearch: q, srlimit: String(limit), srnamespace: '0' });
  return d.query.search.map((s) => ({ title: s.title, words: s.wordcount }));
}
async function parse(title) {
  const d = await api({ action: 'parse', page: title, prop: 'text|links|categories', redirects: '1', disablelimitreport: '1' });
  return d.parse;
}
module.exports = { api, search, parse, sleep };
