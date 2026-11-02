"""make_earlier.py <date> <out.json> — retail selections of STRICTLY EARLIER March 2025 editions only.

Prefers the chronologically edited version (editors/<date>) when it exists, else the writer draft (sandboxes/<date>).
Nothing dated on or after <date> is read or written.
"""
import datetime as dt, json, sys
from pathlib import Path

S = Path(__file__).resolve().parent
k, out = sys.argv[1], Path(sys.argv[2])
DATES = [dt.date(2025, 3, n).isoformat() for n in range(1, 32) if dt.date(2025, 3, n).weekday() < 5]
rows = []
for j in DATES:
    if j >= k:
        break
    base = S / 'editors' / j if (S / 'editors' / j / 'specs' / f'{j}.json').exists() else S / 'sandboxes' / j
    spec = json.loads((base / 'specs' / f'{j}.json').read_text(encoding='utf-8'))
    notes = json.loads((base / 'notes' / f'{j}.json').read_text(encoding='utf-8'))
    rows.append({'date': j, 'lead': notes.get('lead'), 'smaller': notes.get('smaller'),
                 'retail_intro': spec.get('retail_intro'), 'retail': spec.get('retail')})
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({'strictly_earlier_editions': rows}, ensure_ascii=False, indent=2), encoding='utf-8')
print('wrote', out, 'editions:', len(rows))
