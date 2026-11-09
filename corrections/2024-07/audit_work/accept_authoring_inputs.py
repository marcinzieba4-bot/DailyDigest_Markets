"""Bind current independent source/market acceptance before isolated authoring."""
from pathlib import Path
import datetime as dt
import gzip
import hashlib
import json

ROOT=Path(__file__).resolve().parent.parent
DATES=[dt.date(2024,7,n).isoformat() for n in range(1,32) if dt.date(2024,7,n).weekday()<5]
WIN={'news':7,'result':14,'monthly':35}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(gzip.decompress(path.read_bytes()) if path.suffix=='.gz' else path.read_bytes())


freeze_path=ROOT/'audit/source_freeze.json'
source_path=ROOT/'audit/independent_source_review.json'
market_path=ROOT/'audit/independent_market_review.json'
freeze,source,market=map(load,(freeze_path,source_path,market_path))
assert freeze['status']=='all_23_ready'
assert source['passed'] is True and source['status']=='accepted_for_authoring_with_semantic_exclusions'
assert source['infrastructure_status']=='accepted' and not source.get('errors') and not source.get('pending_dates')
assert market['passed'] is True and market['status']=='accepted' and not market.get('errors')
assert market['dates']==DATES and [x['date'] for x in source['dates']]==DATES
assert source['source_freeze_sha256']==market['source_freeze_sha256']==sha(freeze_path)
source_rows={x['date']:x for x in source['dates']}
rows=[]
for date in DATES:
    fp=ROOT/'feeds'/f'{date}.json.gz';cp=ROOT/'cards'/f'{date}.json';ep=ROOT/'exclusions'/f'{date}.json'
    feed,card,ex=map(load,(fp,cp,ep))
    cutoff=dt.datetime.fromisoformat(date).replace(tzinfo=dt.timezone.utc)
    assert feed['date']==card['report_date']==ex['date']==date
    assert dt.datetime.fromisoformat(feed['cutoff_utc'].replace('Z','+00:00'))==cutoff
    assert card['cutoff_utc']==date+'T00:00:00Z'
    assert source_rows[date]['feed_sha256']==sha(fp)
    assert source['card_sha256'][date]==market['card_sha256'][date]==sha(cp)
    assert ex['feed_sha256']==sha(fp)
    ids={x['id'] for x in feed['items']}
    assert len(ids)==len(feed['items']) and len(ids)>=50
    assert {x['id'] for x in ex['exclusions']}<=ids
    for item in feed['items']:
        stamp=dt.datetime.fromisoformat(item['published_at'].replace('Z','+00:00'))
        days=min(WIN[item['cat']],item.get('semantic_window_days',WIN[item['cat']]))
        assert cutoff-dt.timedelta(days=days)<=stamp<cutoff
    for symbol,values in card['markets'].items():
        assert not symbol.endswith('=X')
        assert values['session']<date
        assert all(values.get(key) is None or values[key]<date
                   for key in ('ref_1s_session','ref_5s_session','ref_20s_session'))
    assert card['treasury']['prior_close_date']<date
    rows.append({'date':date,'feed_sha256':sha(fp),'card_sha256':sha(cp),
                 'exclusions_sha256':sha(ep),'headlines':len(ids),'market_instruments':len(card['markets'])})
receipt={'passed':True,'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
    'dates':DATES,'source_freeze_sha256':sha(freeze_path),'source_review_sha256':sha(source_path),
    'market_review_sha256':sha(market_path),'inputs':rows,
    'scope':'Authoring may begin from each own-date frozen feed/card/exclusion set. This binding is not approval of unwritten report claims; every authored claim and chronology still requires independent review.'}
(ROOT/'audit/authoring_inputs_acceptance.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps({'passed':True,'dates':len(rows),'headlines':sum(x['headlines'] for x in rows),
                  'receipt_sha256':sha(ROOT/'audit/authoring_inputs_acceptance.json')}))
