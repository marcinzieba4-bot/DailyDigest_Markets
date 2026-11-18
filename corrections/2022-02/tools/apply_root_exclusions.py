"""apply_root_exclusions.py DATE [DATE ...] — root editorial exclusions after independent review.

Sources: (1) audit_work/feb2022_pending_editorial_exclusions.json — uncited records that writers or
independent reviewers identified as misdated, after the cutoff, rolling or later-vintage; (2) a narrow
later-vintage screen (source labels naming the 2025 "Department of War", "(Published 2023+)" tags,
Super Bowl LVII or later, dated listicles/market reports from sites that re-date evergreen pages).
A record cited by either reviewed component is never excluded here (it is reported instead). The frozen
feed is not mutated. Afterwards tools/rebind_exclusions.py re-verifies both components and rebinds
both independent receipts to the new exclusions hash."""
import gzip, hashlib, json, re, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
PENDING = json.loads((ROOT / 'audit_work/feb2022_pending_editorial_exclusions.json').read_text())
LATER = re.compile(r'\(Published 202[3-9]\)|Super Bowl L(?:VII|VIII|IX|X)\b|Department of War', re.I)
LISTICLE = re.compile(r'\b(?:stocks?|ETFs?|cryptos?|coins?|picks|statistics|stats|predictions?)\b[^|]{0,50}\b(?:in|for) 20(?:2[3-9]|3\d)\b|'
                      r'\b(?:market (?:size|report)|industry report|global report)\b[^|]{0,80}\b20(?:2[6-9]|3\d)\b', re.I)
EVERGREEN = ('theimpactinvestor', 'fortune business insights', 'national today', 'fortunly')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def later_vintage(x):
    t, s = x['title'], x['src']
    if LATER.search(t) or LATER.search(s): return 'Later-vintage record: title or source label carries a name or date from after February 2022'
    if LISTICLE.search(t): return 'Later-vintage dated listicle or market report re-dated after February 2022'
    if any(e in s.lower() for e in EVERGREEN) and re.search(r'\b20(?:2[3-9]|3\d)\b', t): return 'Evergreen page re-dated after February 2022'
    return None


def apply(d):
    feed_path = ROOT / 'feeds' / f'{d}.json.gz'
    items = {x['id']: x for x in json.loads(gzip.decompress(feed_path.read_bytes()))['items']}
    ex_path = ROOT / 'exclusions' / f'{d}.json'; rec = json.loads(ex_path.read_text())
    assert rec['feed_sha256'] == sha(feed_path)
    cited = set()
    for folder in ('nonretail_drafts', 'retail_drafts'):
        cited |= set(re.findall(r'\[\[(n\d{4,6})\]\]', (ROOT / folder / f'{d}.json').read_text()))
    have = {x['id'] for x in rec['exclusions']}
    wanted = dict(PENDING.get(d, {}))
    for i, x in items.items():
        r = later_vintage(x)
        if r and i not in wanted: wanted[i] = r
    added, skipped = [], []
    for i, reason in sorted(wanted.items()):
        if i in have: continue
        if i in cited: skipped.append(i); continue
        x = items[i]
        rec['exclusions'].append({'id': i, 'title': x['title'], 'published_at': x['published_at'], 'src': x['src'], 'date': d,
            'feed_sha256': rec['feed_sha256'], 'screen_kind': 'editorial_vintage', 'reason': reason,
            'disposition': 'exclude_from_report_claims_no_frozen_feed_mutation', 'reviewer': 'root (independent review recommendation)' if i in PENDING.get(d, {}) else 'root (later-vintage screen)'})
        added.append(i)
    rec['exclusions'].sort(key=lambda x: x['id'])
    ex_path.write_text(json.dumps(rec, indent=1, ensure_ascii=False))
    print(d, 'added', len(added), 'skipped (cited)', skipped)
    subprocess.run([sys.executable, str(ROOT / 'tools/rebind_exclusions.py'), d], check=True, cwd=ROOT / 'tools')


if __name__ == '__main__':
    for d in sys.argv[1:]: apply(d)
