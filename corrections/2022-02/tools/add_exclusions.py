"""add_exclusions.py DATE ID:reason [ID:reason ...] — record editorial exclusions for an own-date feed.
The frozen feed is never mutated; exclusions/DATE.json lists ids writers/reviewers must not cite."""
import hashlib, json, sys, gzip
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
d = sys.argv[1]
feed_path = ROOT/'feeds'/f'{d}.json.gz'; feed = json.loads(gzip.decompress(feed_path.read_bytes()))
items = {x['id']: x for x in feed['items']}
p = ROOT/'exclusions'/f'{d}.json'; rec = json.loads(p.read_text())
assert rec['feed_sha256'] == hashlib.sha256(feed_path.read_bytes()).hexdigest()
have = {x['id'] for x in rec['exclusions']}
for arg in sys.argv[2:]:
    i, reason = arg.split(':', 1)
    if i in have: continue
    x = items[i]
    rec['exclusions'].append({'id': i, 'title': x['title'], 'published_at': x['published_at'], 'src': x['src'], 'date': d,
        'feed_sha256': rec['feed_sha256'], 'screen_kind': 'editorial_vintage', 'reason': reason,
        'disposition': 'exclude_from_report_claims_no_frozen_feed_mutation', 'reviewer': 'root (writer-flagged)'})
    print(d, 'excluded', i, x['title'][:90])
rec['exclusions'].sort(key=lambda x: x['id'])
p.write_text(json.dumps(rec, indent=1, ensure_ascii=False))
