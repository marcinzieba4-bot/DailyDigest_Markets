"""Date-bounded April 2025 evidence, shared weekly harvest and own-date feeds.

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
VERSION = 'apr-cutoff-prefix-v1'
PARSER_SCHEMA = 'rss-root-channel-aware-timestamp-v1'
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
        if old.get('status')=='fetched' and old.get('parser_schema')==PARSER_SCHEMA: return old
    out = {'topic':topic,'query':query,'category':category,'locale':loc,
           'lower_date':lo.isoformat(),'upper_date_exclusive':hi.isoformat(),
           'request_url':url,'request_query':q,'signature':sig,'version':VERSION,'parser_schema':PARSER_SCHEMA,
           'fetched_at_utc':dt.datetime.now(UTC).isoformat(),'status':'failed','items':[]}
    for attempt in range(attempts):
        try:
            req=urllib.request.Request(url,headers=HEADERS)
            with urllib.request.urlopen(req,timeout=25) as response: raw=response.read()
            root=ET.fromstring(raw)
            if root.tag!='rss' or root.find('channel')is None:raise ValueError('Expected RSS root/channel; HTML or challenge response rejected')
            nodes=root.findall('.//item')
            dropped=Counter(); items=[]
            for node in nodes:
                try:
                    parsed=email.utils.parsedate_to_datetime(node.findtext('pubDate'))
                    if parsed.tzinfo is None:raise ValueError('RSS publication timestamp has no timezone')
                    published=parsed.astimezone(UTC)
                except Exception: dropped['malformed_timestamp']+=1; continue
                if not lo<=published.date()<hi: dropped['outside_query_window']+=1; continue
                title=(node.findtext('title') or '').strip()
                link=(node.findtext('link') or '').strip()
                src=node.find('source')
                if not title or not link.startswith('https://'): dropped['missing_title_or_https_url']+=1; continue
                if ROLLING.search(title): dropped['rolling_headline']+=1; continue
                items.append({'published_at':published.isoformat(),'src':(src.text or '') if src is not None else '',
                              'source_url':src.get('url','') if src is not None else '', 'title':title,'url':link})
            out.update(status='fetched',response_format_verified=True,items=items,raw_count=len(nodes),raw_sha256=hashlib.sha256(raw).hexdigest(),
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

def cutoff_prefix_jobs(dates):
    """General cutoff-safe request pairs for every straddling catalog window."""
    parents=make_jobs(dates)
    return [(parent,(*parent[:4],parent[4],date))
            for date in sorted(dates)for parent in parents if parent[4]<date<parent[5]]


def collect_feed(date, harvest, *, asof_queries=True, provenance=None):
    """Pure own-date merge; final acquisition always excludes later query-window days.

    The optional provenance dictionary receives actual qualifying request signatures
    for every publication key; it is serialized separately to keep author feeds small.
    """
    cutoff=dt.datetime.combine(date,dt.time(),UTC)
    merged={}; excluded=Counter(); failed=[]
    for batch in harvest:
        if asof_queries and batch['upper_date_exclusive']>date.isoformat():
            excluded['request_window_extends_beyond_report_cutoff']+=1;continue
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
            if provenance is not None: provenance.setdefault(key,set()).add(batch['signature'])
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
    assert all(dt.datetime.fromisoformat(x['published_at'])<cutoff for x in items)
    assert all(cutoff-dt.timedelta(days=WIN[x['cat']])<=dt.datetime.fromisoformat(x['published_at']) for x in items)
    return items, excluded, failed


def build_feed(date, harvest):
    cutoff=dt.datetime.combine(date,dt.time(),UTC)
    provenance={}
    items,excluded,failed=collect_feed(date,harvest,asof_queries=True,provenance=provenance)
    for i,item in enumerate(items,1): item['id']=f'n{i:04d}'
    ledger={x['id']:sorted(provenance[(x['title'].casefold(),x['src'].casefold(),x['published_at'])])for x in items}
    ledger_path=ROOT/'audit/news_provenance'/(date.isoformat()+'.json.gz')
    atomic_json(ledger_path,{'date':date.isoformat(),'cutoff_utc':cutoff.isoformat(),'records':ledger,'scope':'Actual qualifying physical request signatures for every raw publication object; contexts/windows/hashes in news_query_plan.json.'},True)
    payload={'date':date.isoformat(),'cutoff_utc':cutoff.isoformat(),'pipeline':VERSION,'query_upper_bound_enforced':True,
             'rule':'RSS pubDate strictly before report-date 00:00 UTC; news7d, results14d, monthly35d. Headlines only; source timestamps require editorial review.',
             'fails':sorted(set(failed)),'items':items}
    path=ROOT/'work'/'unreviewed_feeds'/(date.isoformat()+'.json.gz');atomic_json(path,payload,True)
    counts=Counter(t for x in items for t in x['topics'])
    return {'date':date.isoformat(),'items':len(items),'failed_query_windows':len(set(failed)),
            'by_topic':dict(sorted(counts.items())),'by_category':dict(Counter(x['cat'] for x in items)),
            'earliest_published_at':min((x['published_at'] for x in items),default=None),
            'latest_published_at':max((x['published_at'] for x in items),default=None),
            'future_items':0,'outside_category_window':0,'excluded':dict(excluded),
            'feed_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'provenance_path':str(ledger_path.relative_to(ROOT)),'provenance_sha256':hashlib.sha256(ledger_path.read_bytes()).hexdigest()}

def main():
    # The accepted April path always performs complete prefix/daily acquisition.
    # Keep no executable weekly-only shortcut that could create partial final feeds.
    from expand_capped_news import main as acquire
    acquire()
if __name__=='__main__':main()
