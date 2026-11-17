"""rebind_exclusions.py DATE — after root adds editorial exclusions to an already-reviewed date, prove that no
cited id is excluded and both components still verify, then rebind exclusions_sha256 in both independent
receipts, recording the prior hash and the newly excluded ids. Component content is not changed."""
import hashlib, json, re, sys
from pathlib import Path
import verify
ROOT = Path(__file__).resolve().parent.parent
d = sys.argv[1]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
ex_path = ROOT/'exclusions'/f'{d}.json'; ex = json.loads(ex_path.read_text()); ids = {x['id'] for x in ex['exclusions']}
cited = set()
for folder in ('nonretail_drafts', 'retail_drafts'):
    cited |= set(re.findall(r'\[\[(n\d{4,6})\]\]', (ROOT/folder/f'{d}.json').read_text()))
assert not cited & ids, sorted(cited & ids)
for mode in ({'nonretail': True}, {'retail_only': True}):
    f, w, n, words = verify.verify(d, **mode); assert not f, f
new = sha(ex_path)
for kind in ('nonretail', 'retail'):
    p = ROOT/'audit'/f'independent_{kind}_{d}.json'; r = json.loads(p.read_text())
    if r['exclusions_sha256'] == new: continue
    r.setdefault('exclusion_rebinds', []).append({'previous_exclusions_sha256': r['exclusions_sha256'], 'new_exclusions_sha256': new,
        'excluded_ids_now': sorted(ids), 'cited_ids_excluded': [], 'components_reverified': True, 'by': 'root',
        'reason': 'Root added editorial exclusions for uncited records after review; reviewed component content unchanged.'})
    r['exclusions_sha256'] = new; p.write_text(json.dumps(r, indent=1, ensure_ascii=False))
    print(d, kind, 'receipt rebound to', new[:12])
