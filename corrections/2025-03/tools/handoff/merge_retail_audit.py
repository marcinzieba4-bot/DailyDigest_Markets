"""merge_retail_audit.py — final spec = repo spec with retail keys taken from the retail-audited copies.

Asserts that the auditors changed nothing outside retail_intro/retail. Refreshes the lead and smaller titles in each
notes file so they match the final section.
"""
import datetime as dt, json, pathlib, sys
S = pathlib.Path(sys.argv[1]); R = pathlib.Path(sys.argv[2])
DATES = [dt.date(2025, 3, n).isoformat() for n in range(1, 32) if dt.date(2025, 3, n).weekday() < 5]
changed = []
for d in DATES:
    base = json.loads((R / 'specs' / f'{d}.json').read_text(encoding='utf-8'))
    aud = json.loads((S / 'retail_audits' / d / 'specs' / f'{d}.json').read_text(encoding='utf-8'))
    for k in set(base) | set(aud):
        if k in ('retail', 'retail_intro'):
            continue
        assert base.get(k) == aud.get(k), f'{d}: auditor changed non-retail key {k}'
    if base.get('retail') != aud.get('retail') or base.get('retail_intro') != aud.get('retail_intro'):
        changed.append(d)
    final = dict(base)
    final['retail'] = aud['retail']
    final['retail_intro'] = aud['retail_intro']
    (R / 'specs' / f'{d}.json').write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding='utf-8')
    np = R / 'notes' / f'{d}.json'
    if np.exists():
        note = json.loads(np.read_text(encoding='utf-8'))
        items = final['retail']
        note['lead'] = items[0]['title']
        note['smaller'] = [x['title'] for x in items[1:4]]
        np.write_text(json.dumps(note, ensure_ascii=False, indent=2), encoding='utf-8')
print('retail text changed by audit on:', ' '.join(d[5:] for d in changed) or 'none')
