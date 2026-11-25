#!/usr/bin/env python3
"""Прибирає «згенеровані» обкладинки Project Gutenberg (яскраві геометричні візерунки з підписом
«Project Gutenberg»): це не справжні обкладинки книжок. Лишаються лише скани справжніх видань.
Без обкладинки застосунок показує стриману «тканинну» палітурку з назвою.
  python3 tools/filter-covers.py
"""
import glob, json, os
from PIL import Image

ROOT = os.path.join(os.path.dirname(__file__), '..', 'app', 'covers')

def generated(path):
    try:
        im = Image.open(path).convert('RGB').resize((60, 90))
    except Exception:
        return True
    px = list(im.crop((0, 30, 60, 90)).get_flattened_data() if hasattr(im, 'get_flattened_data') else im.crop((0, 30, 60, 90)).getdata())
    vivid = sum(1 for r, g, b in px if max(r, g, b) - min(r, g, b) > 140) / len(px)
    return vivid > 0.5

removed = 0
credits_file = os.path.join(ROOT, 'credits.json')
credits = json.load(open(credits_file)) if os.path.exists(credits_file) else {}
for f in glob.glob(os.path.join(ROOT, 'art', '*.jpg')):
    bid = os.path.basename(f)[:-4]
    if credits.get(bid, {}).get('original') and generated(f):
        os.remove(f); credits.pop(bid, None); removed += 1
        for done in (os.path.join(ROOT, bid + '.jpg'),):
            if os.path.exists(done): os.remove(done)
json.dump(credits, open(credits_file, 'w'), indent=1, ensure_ascii=False)
pg = glob.glob(os.path.join(ROOT, 'pg', '*.jpg'))
for f in pg:
    if generated(f):
        os.remove(f); removed += 1
print(f'прибрано згенерованих: {removed}; справжніх у каталозі: {len(glob.glob(os.path.join(ROOT, "pg", "*.jpg")))}')
