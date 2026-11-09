"""Read one own-date draft/evidence set for manual independent claim review."""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import re
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'tools'))
import verify
parser=argparse.ArgumentParser();parser.add_argument('date');args=parser.parse_args()
date=args.date;verify.validate_date(date)
paths={'draft':ROOT/'retail_drafts'/f'{date}.json','feed':ROOT/'feeds'/f'{date}.json.gz','card':ROOT/'cards'/f'{date}.json'}
draft=json.loads(paths['draft'].read_text())
feed={x['id']:x for x in json.loads(gzip.decompress(paths['feed'].read_bytes()))['items']}
card=json.loads(paths['card'].read_text())
body=json.dumps(draft,ensure_ascii=False)
ids=list(dict.fromkeys(re.findall(r'\[\[(n\d+)\]\]',body)))
symbols=set()
for symbol in card['markets']:
    if re.search(r'(?<![A-Z0-9])'+re.escape(symbol)+r'(?![A-Z0-9])',body):symbols.add(symbol)
symbols|={k for k in ('^GSPC','^VIX','QQQ','DX-Y.NYB','BTC-USD','ETH-USD') if k in card['markets']}
fields=('name','session','close','currency','level_unit','chg_1s_pct','chg_5s_pct','chg_20s_pct',
        'ref_20s_session','ref_20s_close','reference_share_units_differ','reference_level_note')
packet={'date':date,'draft':draft,'sources':[{key:feed[i].get(key) for key in ('id','src','published_at','cat','semantic_window_days','title')}for i in ids],
    'metrics':{k:{field:card['markets'][k].get(field)for field in fields}for k in sorted(symbols)},
    'treasury':card['treasury'],'notes':json.loads((ROOT/'notes'/f'retail_{date}.json').read_text()),
    'input_sha256':{key:hashlib.sha256(path.read_bytes()).hexdigest()for key,path in paths.items()},
    'review_status':'Unreviewed extraction only; this script never approves claims.'}
out=ROOT/'work/review_packets';out.mkdir(exist_ok=True)
(out/f'retail_{date}.json').write_text(json.dumps(packet,indent=2,ensure_ascii=False))
print(json.dumps(packet,indent=2,ensure_ascii=False))
