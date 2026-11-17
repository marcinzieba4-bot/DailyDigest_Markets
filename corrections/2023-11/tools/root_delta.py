"""root_delta.py DATE nonretail|retail OLD NEW REASON — root correction after independent review: replace one exact
string in the reviewed component, re-verify, and rebind the receipt with a recorded delta (finding + resolution)."""
import hashlib, json, sys
from pathlib import Path
import verify
ROOT = Path(__file__).resolve().parent.parent
d, kind, old, new, reason = sys.argv[1:6]
path = ROOT/('nonretail_drafts' if kind == 'nonretail' else 'retail_drafts')/f'{d}.json'
text = path.read_text(); assert text.count(old) == 1, ('old string count', text.count(old))
path.write_text(text.replace(old, new))
f, w, n, words = verify.verify(d, **({'nonretail': True} if kind == 'nonretail' else {'retail_only': True}))
if f: path.write_text(text); raise SystemExit('reverted: ' + repr(f[:3]))
rp = ROOT/'audit'/f'independent_{kind}_{d}.json'; r = json.loads(rp.read_text())
comp = json.loads(path.read_text())
if kind == 'nonretail':
    prev = r['nonretail_content_sha256']; r['nonretail_content_sha256'] = hashlib.sha256(json.dumps(comp, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest(); cur = r['nonretail_content_sha256']
else:
    prev = r['retail_draft_sha256']; r['retail_draft_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest(); cur = r['retail_draft_sha256']
r['exclusions_sha256'] = hashlib.sha256((ROOT/'exclusions'/f'{d}.json').read_bytes()).hexdigest()
r.setdefault('root_deltas', []).append({'previous_sha256': prev, 'new_sha256': cur, 'removed': old, 'inserted': new, 'reason': reason,
    'severity': 'major', 'by': 'root', 'reverified': f'{n} sources, {words} words, 0 fail'})
rp.write_text(json.dumps(r, indent=1, ensure_ascii=False)); print(d, kind, 'root delta applied;', n, 'sources', words, 'words')
