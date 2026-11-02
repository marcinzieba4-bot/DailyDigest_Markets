"""merge_final.py — final spec = audited non-retail sections + chronologically edited retail sections.

Retail source: editors/<d>/specs (if the chronology editor has run) else sandboxes/<d>/specs (writer draft).
Non-retail source: audits/<d>/specs (auditor copy; auditors were told not to touch retail keys).
Notes source: editors/<d>/notes else sandboxes/<d>/notes else the repo copy.
"""
import datetime as dt, json, pathlib, sys
S = pathlib.Path(sys.argv[1]); R = pathlib.Path(sys.argv[2])
DATES = [dt.date(2025, 3, n).isoformat() for n in range(1, 32) if dt.date(2025, 3, n).weekday() < 5]
report = []
for d in DATES:
    ed = S / 'editors' / d / 'specs' / f'{d}.json'
    sb = S / 'sandboxes' / d / 'specs' / f'{d}.json'
    au = S / 'audits' / d / 'specs' / f'{d}.json'
    retail_src = json.loads((ed if ed.exists() else sb).read_text(encoding='utf-8'))
    audited = json.loads(au.read_text(encoding='utf-8'))
    draft = json.loads(sb.read_text(encoding='utf-8'))
    assert audited.get('retail') == draft.get('retail') and audited.get('retail_intro') == draft.get('retail_intro'), d + ': auditor changed retail keys'
    final = dict(audited)
    final['retail'] = retail_src['retail']
    final['retail_intro'] = retail_src['retail_intro']
    (R / 'specs' / f'{d}.json').write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding='utf-8')
    nt_ed = S / 'editors' / d / 'notes' / f'{d}.json'; nt_sb = S / 'sandboxes' / d / 'notes' / f'{d}.json'
    nt = nt_ed if nt_ed.exists() else nt_sb
    if nt.exists():
        (R / 'notes' / f'{d}.json').write_text(nt.read_text(encoding='utf-8'), encoding='utf-8')
    report.append(f"{d} retail_from={'editor' if ed.exists() else 'draft'}")
print('; '.join(report))
