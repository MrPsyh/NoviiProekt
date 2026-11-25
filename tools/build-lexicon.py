#!/usr/bin/env python3
"""Словник Лесі — «бібліотека всіх слів» німецької мови.

Джерело: Wiktionary (англійська редакція, німецькі статті) у вигляді kaikki.org JSONL, ліцензія CC BY-SA 4.0
(вказуємо в застосунку). Для кожного слова зберігаємо:
  початкову форму (інфінітив / називний відмінок), частину мови, рід (der/die/das), множину, родовий,
  основні форми дієслова (er spielt, spielte, hat gespielt), ступені порівняння, IPA-вимову, значення.
А також карту «будь-яка форма → початкова форма», щоб у новій книжці «spielte» чи «Häuser»
одразу розпізнавались як «spielen» і «das Haus».

Результат: app/lexicon/<шард>.json (шард — перші дві літери), приложение вантажить потрібний шард за запитом.
  python3 tools/build-lexicon.py tools/.cache/kaikki-de.jsonl
"""
import json, os, re, sys, unicodedata
from collections import defaultdict

SRC = sys.argv[1] if len(sys.argv) > 1 else 'tools/.cache/kaikki-de.jsonl'
OUT = os.path.join(os.path.dirname(__file__), '..', 'app', 'lexicon')
POS_KEEP = {'noun', 'verb', 'adj', 'adv', 'pron', 'prep', 'conj', 'num', 'det', 'article', 'particle', 'intj', 'name', 'phrase', 'prep_phrase', 'contraction'}
SKIP_FORM_TAGS = {'table-tags', 'inflection-template', 'class', 'auxiliary', 'romanization'}
GENDER = {'m': 'm', 'f': 'f', 'n': 'n'}

def shard(w):
    s = unicodedata.normalize('NFKD', w.lower())
    s = ''.join(c for c in s if c.isalpha() and ord(c) < 128)
    return (s[:2] or '_').ljust(2, '_')

lemmas = {}               # key -> entry
forms = defaultdict(set)  # form_lower -> {key}

def add_form(form, key):
    f = form.strip().lower()
    if f and len(f) < 40 and ' ' not in f:
        forms[f].add(key)

n = 0
with open(SRC, encoding='utf-8') as fh:
    for line in fh:
        n += 1
        d = json.loads(line)
        if d.get('lang_code') != 'de':
            continue
        word, pos = d.get('word', ''), d.get('pos', '')
        if pos not in POS_KEEP or not word or ' ' in word.strip():
            continue  # фразеологізми не беремо: вони перехоплювали звичайні форми (spielte → «die erste Geige spielen»)
        senses = d.get('senses', [])
        # статті-«форми» (spielte → spielen)
        form_of = [fo['word'] for s in senses for fo in (s.get('form_of') or []) if fo.get('word')]
        if form_of and all(('form-of' in (s.get('tags') or [])) or s.get('form_of') for s in senses):
            for lemma in form_of:
                if ' ' not in lemma:
                    add_form(word, f'{lemma}|{pos}')
            continue
        key = f'{word}|{pos}'
        glosses = []
        for s in senses:
            for g in s.get('glosses', [])[:1]:
                g = re.sub(r'\s+', ' ', g).strip()
                if g and g not in glosses and len(glosses) < 4:
                    glosses.append(g[:120])
        if not glosses:
            continue
        e = lemmas.get(key) or {'w': word, 'p': pos}
        head = ' '.join(h.get('expansion', '') for h in d.get('head_templates', []))
        if pos == 'noun':
            m = re.match(r'^\S+(?:\s+\S+)?\s+([mfn])\b', head)
            if m: e['g'] = m.group(1)
        ipa = next((s['ipa'] for s in d.get('sounds', []) if 'ipa' in s), None)
        if ipa and 'ipa' not in e: e['ipa'] = ipa
        fl = d.get('forms', [])
        def first(*tags, exclude=()):
            for f in fl:
                t = set(f.get('tags') or [])
                if set(tags) <= t and not (t & set(exclude)) and f['form'] not in ('-', '—'):
                    return f['form']
        if pos == 'noun':
            pl = first('plural', exclude=('error-unknown-tag', 'diminutive')); gen = first('genitive', exclude=('plural',))
            if pl: e['pl'] = pl
            if gen: e['gen'] = gen
        elif pos == 'verb':
            v = [first('present', 'singular', 'third-person'), first('past', exclude=('participle', 'subjunctive-ii')), first('participle', 'past')]
            aux = first('auxiliary')
            if any(v): e['v'] = [x or '' for x in v]
            if aux: e['aux'] = aux
        elif pos == 'adj':
            c, s = first('comparative'), first('superlative')
            if c or s: e['cmp'] = [c or '', s or '']
        e['en'] = (e.get('en', []) + [g for g in glosses if g not in e.get('en', [])])[:4]
        lemmas[key] = e
        add_form(word, key)
        for f in fl:
            if set(f.get('tags') or []) & SKIP_FORM_TAGS or f.get('source') == 'declension' and f['form'].startswith('de-'):
                continue
            add_form(f['form'].split(' ')[-1], key)  # «am schönsten» → «schönsten», «hat gespielt» → «gespielt»
        if n % 200000 == 0:
            print(n, len(lemmas), len(forms), flush=True)

# посилання форма → лема лише на існуючі леми
by_shard = defaultdict(lambda: {'f': {}, 'l': {}})
for key, e in lemmas.items():
    by_shard[shard(e['w'])]['l'][key] = e
for f, keys in forms.items():
    ks = sorted(k for k in keys if k in lemmas)
    if ks:
        by_shard[shard(f)]['f'][f] = ks
os.makedirs(OUT, exist_ok=True)
total = 0
for s, data in by_shard.items():
    path = os.path.join(OUT, s + '.json')
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(',', ':'))
    total += os.path.getsize(path)
with open(os.path.join(OUT, 'LICENSE.txt'), 'w') as fh:
    fh.write('Lexicon data derived from Wiktionary (https://en.wiktionary.org), via kaikki.org. License: CC BY-SA 4.0.\n')
print(f'лем: {len(lemmas)}, форм: {len(forms)}, шардів: {len(by_shard)}, {total / 1e6:.1f} МБ')
