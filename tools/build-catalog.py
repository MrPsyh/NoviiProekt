#!/usr/bin/env python3
"""Великий каталог: усі німецькі книжки Project Gutenberg, що вільні в ЄС (автор і перекладач померли
понад 70 років тому), лише художня література / поезія / драма / філософія / дитячі книжки.
Джерело: pg_catalog.csv з офіційного дзеркала (aleph.pglaf.org) + популярність з Gutendex (якщо є).
Результат: app/books/catalog.json — компактні записи; тексти застосунок завантажує сам, коли книжку відкривають.
  python3 tools/build-catalog.py
"""
import csv, json, glob, os, re, datetime

ROOT = os.path.join(os.path.dirname(__file__), '..')
CACHE = os.path.join(os.path.dirname(__file__), '.cache')
PD_YEAR = datetime.date.today().year - 71
csv.field_size_limit(10**8)

pop = {}
for f in glob.glob(os.path.join(CACHE, 'gx-*.json')):
    try:
        for b in json.load(open(f))['results']:
            pop[b['id']] = b['download_count']
    except Exception:
        pass

def people(s):
    out = []
    for part in [p.strip() for p in s.split(';') if p.strip()]:
        role = re.search(r'\[([^\]]+)\]', part)
        role = role.group(1) if role else 'Author'
        years = re.search(r'(\d{3,4})\??\s*(?:BCE)?-(\d{3,4})?', part)
        bce = 'BCE' in part
        died = int(years.group(2)) if years and years.group(2) else None
        if bce: died = -1
        name = re.sub(r'\[.*?\]', '', part)
        name = re.sub(r',?\s*\d.*$', '', name).strip()
        bits = [b.strip() for b in name.split(',') if b.strip()]
        nice = f'{bits[1]} {bits[0]}' if len(bits) > 1 else (bits[0] if bits else '')
        nice = re.sub(r'\s*\(.*?\)', '', nice)
        out.append({'role': role, 'name': nice, 'died': died, 'years': years.group(0) if years else ''})
    return out

LIT = re.compile(r'^(P|B|GR|D)')  # література, філософія, фольклор, історія (мемуари)
BAD = re.compile(r'erotic|sexual|pornograph|sadomaso|homosexual|German language|Readers \(|Textbooks|Dictionaries|Conversation and phrase', re.I)
KIDS = re.compile(r'juvenile|children|kinder|fairy tales|märchen|nursery', re.I)
POETRY = re.compile(r'poetry|poems|gedichte|ballad', re.I)
DRAMA = re.compile(r'drama|plays|traged|comed', re.I)
SLAVIC = re.compile(r'\b(russia|russian|ukrain\w*|tolsto\w*|dostoyevsk\w*|pushkin|gogol|chekhov|turgenev|gorky|lermontov|leskov)\b', re.I)
JAPAN = re.compile(r'japan', re.I)

books = []
with open(os.path.join(CACHE, 'pg_catalog.csv'), encoding='utf-8') as fh:
    for r in csv.DictReader(fh):
        if r['Type'] != 'Text' or r['Language'].strip() != 'de':
            continue
        subj = r['Subjects'] + ' ' + r['Bookshelves']
        if BAD.search(subj) or not LIT.search(r['LoCC'] or '') or (r['LoCC'] or '').startswith('PF'):  # PF — підручники німецької
            continue
        ps = people(r['Authors'])
        creators = [p for p in ps if p['role'] in ('Author', 'Translator')]
        if not creators or any(p['died'] is None or p['died'] > PD_YEAR for p in creators):
            continue
        a = next((p for p in ps if p['role'] == 'Author'), None)
        tr = [p['name'] for p in ps if p['role'] == 'Translator']
        gid = int(r['Text#'])
        title = re.sub(r'\s+', ' ', r['Title']).strip()
        title, _, sub = title.partition('\n')
        title = re.split(r'\s*[:;]\s*(?=[A-ZÄÖÜa-z])', title, maxsplit=1)
        main, subtitle = title[0].strip(), (title[1].strip() if len(title) > 1 else '')
        coll = []
        if KIDS.search(subj): coll.append('kids')
        if SLAVIC.search(subj + ' ' + r['Authors']) or (r['LoCC'] or '').startswith('PG'): coll.append('slavic')
        if JAPAN.search(subj): coll.append('japan')
        if POETRY.search(subj): coll.append('poetry')
        if DRAMA.search(subj): coll.append('drama')
        if (r['LoCC'] or '').startswith('B'): coll.append('philosophy')
        if not coll: coll.append('world')
        books.append({
            'g': gid, 't': main[:120], 'st': subtitle[:120], 'a': a['name'] if a else 'Anonym', 'ay': a['years'] if a else '',
            'tr': ', '.join(tr) or None, 'y': r['Issued'][:4], 'c': coll, 'd': pop.get(gid, 0),
            'lv': 'B1' if 'kids' in coll else 'C1' if (r['LoCC'] or '').startswith('B') else 'B2',
            's': [x.strip() for x in r['Subjects'].split(';') if x.strip()][:3],
        })

# книжки, що вже вбудовані в застосунок, не дублюємо
bundled = json.load(open(os.path.join(ROOT, 'app', 'books', 'index.json')))
bg = {b.get('gutenberg') for b in bundled if b.get('gutenberg')}
norm = lambda x: re.sub(r'[^a-zäöüß]', '', x.lower())
bt = {}
for b in bundled:
    bt.setdefault((norm(b['title'])[:12], norm(b['author'].split()[-1])), b['id'])
match = {}  # вбудована книжка → номер Gutenberg (для справжньої обкладинки)
kept = []
for b in books:
    k = (norm(b['t'])[:12], norm(b['a'].split()[-1]) if b['a'] else '')
    if b['g'] in bg: continue
    if k in bt:
        match.setdefault(bt[k], b['g']); continue
    kept.append(b)
books = kept
json.dump(match, open(os.path.join(CACHE, 'bundled-pg.json'), 'w'), indent=1)
print('збіги з вбудованими:', match)
books.sort(key=lambda b: -b['d'])
out = os.path.join(ROOT, 'app', 'books', 'catalog.json')
json.dump(books, open(out, 'w'), ensure_ascii=False, separators=(',', ':'))
print(f'книжок у каталозі: {len(books)}, з популярністю: {sum(1 for b in books if b["d"])}, {os.path.getsize(out)/1e6:.1f} МБ')
from collections import Counter
print(Counter(c for b in books for c in b['c']))
