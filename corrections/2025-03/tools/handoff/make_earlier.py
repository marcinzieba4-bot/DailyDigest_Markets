"""make_earlier.py <date> <out.json> — retail selections of STRICTLY EARLIER March 2025 editions only.

Writes <out.json> (full retail sections) and <out-dir>/index.json (titles and openings only).
Prefers the chronologically edited version (editors/<date>) when it exists, else the writer draft (sandboxes/<date>).
Nothing dated on or after <date> is read or written.
"""
import datetime as dt, json, sys
from pathlib import Path

S = Path(__file__).resolve().parent
k, out = sys.argv[1], Path(sys.argv[2])
DATES = [dt.date(2025, 3, n).isoformat() for n in range(1, 32) if dt.date(2025, 3, n).weekday() < 5]
rows, index = [], []
for j in DATES:
    if j >= k:
        break
    base = S / 'editors' / j if (S / 'editors' / j / 'specs' / f'{j}.json').exists() else S / 'sandboxes' / j
    spec = json.loads((base / 'specs' / f'{j}.json').read_text(encoding='utf-8'))
    notes_path = base / 'notes' / f'{j}.json'
    notes = json.loads(notes_path.read_text(encoding='utf-8')) if notes_path.exists() else {}
    items = spec.get('retail', [])
    rows.append({'date': j, 'lead': notes.get('lead') or (items[0]['title'] if items else None),
                 'smaller': notes.get('smaller') or [x['title'] for x in items[1:4]],
                 'retail_intro': spec.get('retail_intro'), 'retail': items})
    index.append({'date': j, 'lead': items[0]['title'] if items else None,
                  'lead_opening': (items[0]['parts'][0][1][:240] if items and items[0].get('parts') else None),
                  'smaller': [x['title'] for x in items[1:4]]})
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({'strictly_earlier_editions': rows}, ensure_ascii=False, indent=2), encoding='utf-8')
(out.parent / 'index.json').write_text(json.dumps({'strictly_earlier_editions_index': index}, ensure_ascii=False, indent=2), encoding='utf-8')
print('wrote', out, 'and index; editions:', len(rows))
