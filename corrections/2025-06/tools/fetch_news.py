"""Date-bounded June 2025 evidence, shared weekly harvest and own-date feeds.

Each query is cached by its complete URL, then merged independently for each
report at 00:00 UTC. News / results / monthly releases have 7 / 14 / 35 day
windows. Retrieval time never substitutes for publication time. RSS dates and
headlines require editorial review; they do not prove original article vintages.
No model, report generation, credentials or publishing is involved.
"""
from __future__ import annotations
import argparse, concurrent.futures as cf, datetime as dt, email.utils
import gzip, hashlib, json, os, re, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from topics import TOPICS, EN

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT/'cache'/'news'
WIN = {'news':7, 'result':14, 'monthly':35}
UTC = dt.timezone.utc
HEADERS = {'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
VERSION = 'june-shared-weekly-v1'
PREVIEW = re.compile(r'\b(?:preview|previews|ahead of|week ahead|to report|will report|set to report|what to expect|earnings calendar)\b', re.I)
ROLLING = re.compile(r'\b(?:live updates|live blog|as it happened|stock market today|markets today)\b', re.I)

def atomic_json(path, data, compress=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(data, ensure_ascii=False, separators=(',',':')).encode()
    if compress: raw = gzip.compress(raw, mtime=0)
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_bytes(raw); temp.replace(path)

def url_for(q, lo, hi, loc):
    # Google after: is exclusive; local timestamp filtering below is authoritative.
    query = f'{q} after:{(lo-dt.timedelta(days=1)).isoformat()} before:{hi.isoformat()}'
    hl, gl, ceid = loc
    return 'https://news.google.com/rss/search?'+urllib.parse.urlencode({'q':query,'hl':hl,'gl':gl,'ceid':ceid}), query

def fetch(job, attempts=6, backoff_cap=15):
    topic, query, category, loc, lo, hi = job
    url, q = url_for(query,lo,hi,loc)
    sig = hashlib.sha256((VERSION+'\n'+url).encode()).hexdigest()
    path = CACHE/(sig+'.json.gz')
    if path.exists():
        old = json.loads(gzip.decompress(path.read_bytes()))
        if old.get('status')=='fetched': return old
    out = {'topic':topic,'query':query,'category':category,'locale':loc,
           'lower_date':lo.isoformat(),'upper_date_exclusive':hi.isoformat(),
           'request_url':url,'request_query':q,'signature':sig,'version':VERSION,
           'fetched_at_utc':dt.datetime.now(UTC).isoformat(),'status':'failed','items':[]}
    for attempt in range(attempts):
        try:
            req=urllib.request.Request(url,headers=HEADERS)
            with urllib.request.urlopen(req,timeout=25) as response: raw=response.read()
            root=ET.fromstring(raw); nodes=root.findall('.//item')
            dropped=Counter(); items=[]
            for node in nodes:
                try: published=email.utils.parsedate_to_datetime(node.findtext('pubDate')).astimezone(UTC)
                except Exception: dropped['malformed_timestamp']+=1; continue
                if not lo<=published.date()<hi: dropped['outside_query_window']+=1; continue
                title=(node.findtext('title') or '').strip()
                link=(node.findtext('link') or '').strip()
                src=node.find('source')
                if not title or not link.startswith('https://'): dropped['missing_title_or_https_url']+=1; continue
                if ROLLING.search(title): dropped['rolling_headline']+=1; continue
                items.append({'published_at':published.isoformat(),'src':(src.text or '') if src is not None else '',
                              'source_url':src.get('url','') if src is not None else '', 'title':title,'url':link})
            out.update(status='fetched',items=items,raw_count=len(nodes),raw_sha256=hashlib.sha256(raw).hexdigest(),
                       discarded=dict(dropped),possibly_capped=len(nodes)>=100)
            break
        except Exception as exc:
            out.update(error_type=type(exc).__name__,error=str(exc)[:180])
            if attempt<attempts-1: time.sleep(min(2**attempt,backoff_cap))
    atomic_json(path,out,True)
    return out

def make_jobs(dates):
    earliest=min(dates); latest=max(dates)
    jobs=[]
    for topic, queries in TOPICS.items():
        for entry in queries:
            query,category=entry[:2];loc=entry[2] if len(entry)>2 else EN
            lo=earliest-dt.timedelta(days=WIN[category]);end=latest
            while lo<end:
                hi=min(lo+dt.timedelta(days=7),end)
                jobs.append((topic,query,category,loc,lo,hi));lo=hi
    # Earliest intervals first so early reports become available first.
    return sorted(jobs,key=lambda j:(j[4],j[5],j[0],j[1]))

def build_feed(date, harvest):
    cutoff=dt.datetime.combine(date,dt.time(),UTC)
    merged={}; excluded=Counter(); failed=[]
    for batch in harvest:
        category=batch['category']; topic=batch['topic']
        needed_lo=date-dt.timedelta(days=WIN[category])
        if batch['upper_date_exclusive']<=needed_lo.isoformat() or batch['lower_date']>=date.isoformat(): continue
        if batch['status']!='fetched': failed.append(batch['signature']);continue
        for item in batch['items']:
            published=dt.datetime.fromisoformat(item['published_at'])
            cat='news' if PREVIEW.search(item['title']) else category
            if not cutoff-dt.timedelta(days=WIN[cat])<=published<cutoff:
                excluded['outside_own_date_window']+=1;continue
            # Same title at different times is retained: rolling-date ambiguity is
            # not resolved by arbitrarily choosing an earlier publication time.
            key=(item['title'].casefold(),item['src'].casefold(),item['published_at'])
            if key in merged:
                existing=merged[key]
                if topic not in existing['topics']: existing['topics'].append(topic)
                if batch['query'] not in existing['queries']: existing['queries'].append(batch['query'])
                if WIN[cat]<WIN[existing['cat']]: existing['cat']=cat
                excluded['duplicate_query_matches']+=1
                continue
            merged[key]={**item,'cat':cat,'topics':[topic],'q':batch['query'],'queries':[batch['query']],
                         'lang':batch['locale'][0]}
    # Deduplication can tighten category age; apply the final category window again.
    ready=[x for x in merged.values() if cutoff-dt.timedelta(days=WIN[x['cat']]) <= dt.datetime.fromisoformat(x['published_at']) < cutoff]
    excluded['post_dedup_age_mismatch'] += len(merged)-len(ready)
    items=sorted(ready,key=lambda x:(x['topics'][0],x['published_at'],x['title'],x['src'],x['url']))
    for i,item in enumerate(items,1): item['id']=f'n{i:04d}'
    assert all(dt.datetime.fromisoformat(x['published_at'])<cutoff for x in items)
    assert all(cutoff-dt.timedelta(days=WIN[x['cat']])<=dt.datetime.fromisoformat(x['published_at']) for x in items)
    payload={'date':date.isoformat(),'cutoff_utc':cutoff.isoformat(),'pipeline':VERSION,
             'rule':'RSS pubDate strictly before report-date 00:00 UTC; news7d, results14d, monthly35d. Headlines only; source timestamps require editorial review.',
             'fails':sorted(set(failed)),'items':items}
    path=ROOT/'work'/'unreviewed_feeds'/(date.isoformat()+'.json.gz');atomic_json(path,payload,True)
    counts=Counter(t for x in items for t in x['topics'])
    return {'date':date.isoformat(),'items':len(items),'failed_query_windows':len(set(failed)),
            'by_topic':dict(sorted(counts.items())),'by_category':dict(Counter(x['cat'] for x in items)),
            'earliest_published_at':min((x['published_at'] for x in items),default=None),
            'latest_published_at':max((x['published_at'] for x in items),default=None),
            'future_items':0,'outside_category_window':0,'excluded':dict(excluded),
            'feed_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('dates',nargs='*');ap.add_argument('--workers',type=int,default=10)
    args=ap.parse_args()
    dates=[dt.date.fromisoformat(d) for d in args.dates] if args.dates else [dt.date(2025,6,d) for d in range(1,31) if dt.date(2025,6,d).weekday()<5]
    if any(d.year!=2025 or d.month!=6 for d in dates): raise SystemExit('Only June2025 report dates')
    jobs=make_jobs(dates);harvest=[];started=dt.datetime.now(UTC).isoformat()
    print(f'{len(jobs)} shared query windows; {len(dates)} own-date feeds; workers={args.workers}',flush=True)
    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for n,batch in enumerate(pool.map(fetch,jobs),1):
            harvest.append(batch)
            if n%100==0 or batch['status']!='fetched': print(f'{n}/{len(jobs)} {batch["status"]} {batch["lower_date"]} {batch["topic"]}',flush=True)
    audits=[]
    for date in sorted(dates):
        audit=build_feed(date,harvest);audits.append(audit)
        print(f'{date}: {audit["items"]} items, {audit["failed_query_windows"]} failed windows',flush=True)
    audit={'version':VERSION,'started_at_utc':started,'finished_at_utc':dt.datetime.now(UTC).isoformat(),
           'query_count':sum(len(qs) for qs in TOPICS.values()),'shared_query_windows':len(jobs),
           'failed_windows':[b for b in harvest if b['status']!='fetched'],
           'possibly_capped_windows':sum(bool(b.get('possibly_capped')) for b in harvest),
           'dates':audits,'publication_timestamp_limitation':'RSS timestamps do not independently verify original article vintage or same-day early-UTC releases.'}
    atomic_json(ROOT/'audit'/'news_fetch_audit.json',audit)
    if audit['failed_windows']: raise SystemExit(1)
if __name__=='__main__':main()
