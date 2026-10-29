"""Freeze July feeds when all required query windows are fetched.

Screen selected high-priority Reuters headlines against canonical URL dates via
approved Google News metadata. Unknown same-day availability is conservatively
excluded. This is not article-body or original-vintage verification. Surviving
feed IDs are preserved; the unreviewed harvest remains in work/.
"""
from __future__ import annotations
import argparse, concurrent.futures as cf, datetime as dt, gzip, hashlib
import importlib.util, json, re, sys, time, urllib.parse
from pathlib import Path
from fetch_news import ROOT,CACHE,VERSION,WIN,make_jobs,url_for,build_feed,atomic_json
from digest import rank

DATES=[dt.date(2025,7,n) for n in range(1,32) if dt.date(2025,7,n).weekday()<5]
PRIORITY={date:i for i,date in enumerate(DATES)}
META=ROOT/'audit'/'canonical_reuters_urls.json'
RESOLVER=ROOT/'posthoc'/'resolve_news_url.py'
sp=importlib.util.spec_from_file_location('news_metadata_resolver',RESOLVER)
resolver=importlib.util.module_from_spec(sp);sp.loader.exec_module(resolver)
CAPS={'us_macro':35,'us_data':35,'europe':35,'china':55,'japan':30,'australia':30,'poland_en':30,'poland_pl':55,'sectors':65,'earnings':65,'crypto':35,'flows':35,'retail':60,'geo':30,'calendar':15}

# Reviewer-only release guards. A date here is the first 00:00 UTC report cutoff
# after the actual release, not a timestamp inferred from Google's RSS index.
# Pattern matches identify high-risk actuals and leave previews/background alone.
# Japanese early-local releases (Tankan, Tokyo CPI and industrial production) can
# precede UTC midnight and are deliberately not blocked as same-local-day data.
PREVIEW = re.compile(r'\b(?:preview|previews|ahead of|week ahead|what to expect|expected|expects?|forecast|forecasts|forecasting|will|would|may|might|could|likely|seen|set to|due|awaits?|waiting|on hold ahead|decision day|to (?:hold|cut|raise|leave|keep|release|report|meet))\b', re.I)
RELEASE_GUARDS = [
    ('China June Caixin manufacturing PMI', '2025-06-26', '2025-07-02', r'(?=.*(?:Caixin|private.sector|private survey|RatingDog|rebounds?|returns? to growth))(?=.*(?:China|Chinese|Caixin))(?=.*(?:manufactur|factory))'),
    ('US June ISM manufacturing', '2025-06-26', '2025-07-02', r'(?=.*(?:ISM|Institute for Supply Management))(?=.*(?:manufactur|factory))'),
    ('Eurozone June flash inflation', '2025-06-28', '2025-07-02', r'(?=.*(?:euro\s?zone|euro area))(?=.*(?:inflation|CPI|consumer prices))(?=.*(?:June|Jun\b))'),
    ('US June ADP employment', '2025-06-27', '2025-07-03', r'(?=.*ADP)(?=.*(?:jobs|employment|payroll|hiring))'),
    ('NBP July rate decision', '2025-06-27', '2025-07-03', r'(?=.*(?:NBP|RPP|Poland|Polish|Glapiński))(?=.*(?:cuts? rates|rate cut|cuts? interest|obniż|stóp|stopy procentowe|rate decision|interest rates))(?=.*(?:July|lipc|cuts?|obniż))'),
    ('US June payrolls', '2025-06-29', '2025-07-04', r'(?=.*(?:U\.?S\.?|American|nonfarm|payroll|jobs report))(?=.*(?:jobs|payroll|unemployment|hiring))(?=.*(?:June|Jun\b|147,000|147000))'),
    ('US June ISM services', '2025-06-29', '2025-07-04', r'(?=.*(?:ISM|Institute for Supply Management))(?=.*(?:services|non-manufactur))'),
    ('RBA July rate decision', '2025-07-02', '2025-07-09', r'(?=.*(?:RBA|Reserve Bank of Australia))(?=.*(?:holds?|cuts?|keeps?|leaves?|surprise|decision|rates))'),
    ('China June inflation', '2025-07-04', '2025-07-10', r'(?=.*China)(?=.*(?:CPI|PPI|inflation|deflation|consumer prices|producer prices))(?=.*(?:June|Jun\b))'),
    ('China June trade', '2025-07-09', '2025-07-15', r'(?=.*China)(?=.*(?:exports|imports|trade surplus|trade data))(?=.*(?:June|Jun\b))'),
    ('China second-quarter GDP', '2025-07-09', '2025-07-16', r'(?=.*China)(?=.*(?:GDP|gross domestic product|economy|growth))(?=.*(?:Q2|second.quarter|2nd.quarter))'),
    ('China June activity', '2025-07-10', '2025-07-16', r'(?=.*China)(?=.*(?:retail sales|industrial (?:output|production)|fixed.asset|home prices))(?=.*(?:June|Jun\b))'),
    ('US June CPI', '2025-07-10', '2025-07-16', r'(?=.*(?:U\.?S\.?|American|CPI))(?=.*(?:CPI|inflation|consumer prices))(?=.*(?:June|Jun\b))'),
    ('US June PPI', '2025-07-11', '2025-07-17', r'(?=.*(?:U\.?S\.?|American|PPI))(?=.*(?:PPI|producer prices|wholesale prices))(?=.*(?:June|Jun\b))'),
    ('Australia June employment', '2025-07-12', '2025-07-18', r'(?=.*Australia)(?=.*(?:jobs|employment|unemployment|hiring))(?=.*(?:June|Jun\b))'),
    ('US June retail sales', '2025-07-12', '2025-07-18', r'(?=.*(?:U\.?S\.?|American))(?=.*retail sales)(?=.*(?:June|Jun\b))'),
    ('China July LPR', '2025-07-16', '2025-07-22', r'(?=.*(?:China|PBOC))(?=.*(?:loan prime|benchmark lending|LPR))'),
    ('ECB July rate decision', '2025-07-19', '2025-07-25', r'(?=.*(?:ECB|European Central Bank))(?=.*(?:holds?|cuts?|keeps?|leaves?|decision|rates))'),
    ('July flash PMIs', '2025-07-19', '2025-07-25', r'(?=.*(?:PMI|purchasing managers|business activity))(?=.*(?:July|flash))(?=.*(?:euro\s?zone|Germany|German|France|French|Britain|British|UK|U\.?S\.?|S&P Global))'),
    ('US June JOLTS', '2025-07-24', '2025-07-30', r'(?=.*(?:JOLTS|U\.?S\.? job openings))(?=.*(?:June|Jun\b|job openings))'),
    ('Australia Q2 CPI', '2025-07-25', '2025-07-31', r'(?=.*Australia)(?=.*(?:CPI|inflation|consumer prices))(?=.*(?:Q2|second.quarter|June quarter|quarterly))'),
    ('US July ADP', '2025-07-25', '2025-07-31', r'(?=.*ADP)(?=.*(?:jobs|employment|payroll|hiring))'),
    ('US Q2 GDP advance', '2025-07-25', '2025-07-31', r'(?=.*(?:U\.?S\.?|American))(?=.*(?:GDP|gross domestic product|economy|growth))(?=.*(?:Q2|second.quarter|2nd.quarter))'),
    ('FOMC July rate decision', '2025-07-25', '2025-07-31', r'(?=.*(?:Fed|Federal Reserve|FOMC))(?=.*(?:holds? rates|keeps? rates|leaves? rates|rate decision|unchanged|dissents?|Waller.*Bowman|Bowman.*Waller))'),
    ('BOJ July rate decision', '2025-07-25', '2025-08-01', r'(?=.*(?:BOJ|Bank of Japan))(?=.*(?:holds?|keeps?|leaves?|decision|raises?|hikes?|rates))'),
    ('US June PCE', '2025-07-26', '2025-08-01', r'(?=.*(?:PCE|personal consumption expenditure))(?=.*(?:June|Jun\b|inflation|prices))'),
    ('US Q2 employment cost index', '2025-07-26', '2025-08-01', r'(?=.*(?:employment cost|ECI))(?=.*(?:Q2|second.quarter|June|wages|index))'),
    ('German July preliminary CPI', '2025-07-26', '2025-08-01', r'(?=.*(?:German|Germany))(?=.*(?:CPI|inflation|consumer prices))(?=.*(?:July|prelim))'),
]

def release_guard_reason(item, stamp):
    title=item['title']
    if PREVIEW.search(title): return None
    published=item['published_at'][:10]
    for label,start,eligible,pattern in RELEASE_GUARDS:
        if start<=published<eligible and stamp<eligible and re.search(pattern,title,re.I):
            return label+' actual may precede verified release; excluded until '+eligible+' report'
    return None

def is_reuters(item):
    return item['src'].casefold().strip() in ('reuters','reuters.com') or item['title'].casefold().endswith(' - reuters')

def selected(items):
    ids=set()
    for topic,cap in CAPS.items():
        rows=sorted([x for x in items if x['topics'][0]==topic],key=rank)
        ids.update(x['id'] for x in rows[:cap])
    return [x for x in items if x['id'] in ids and is_reuters(x)]

def metadata(url):
    error=''
    for attempt in range(4):
        try:
            canonical=resolver.resolve(url);match=re.search(r'(\d{4}-\d{2}-\d{2})/?$',urllib.parse.urlparse(canonical).path)
            return url,{'canonical_url':canonical,'canonical_date':match.group(1) if match else None,'observed_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'publisher_body_fetched':False}
        except Exception as exc:
            error=f'{type(exc).__name__}: {exc}'
            if attempt<3:time.sleep(min(2**attempt,8))
    return url,{'error':error,'observed_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'publisher_body_fetched':False}

def cached_harvest(jobs):
    records=[];missing=[]
    for job in jobs:
        topic,q,cat,loc,lo,hi=job;url,_=url_for(q,lo,hi,loc)
        sig=hashlib.sha256((VERSION+'\n'+url).encode()).hexdigest();path=CACHE/(sig+'.json.gz')
        if path.exists():
            record=json.loads(gzip.decompress(path.read_bytes()))
            if record.get('status')=='fetched':records.append(record);continue
        missing.append(job)
    return records,missing

def freeze(date,harvest,cache,workers,from_unreviewed=False,conservative_offline=False):
    stamp=date.isoformat()
    original=ROOT/'work'/'unreviewed_feeds'/(stamp+'.json.gz')
    if from_unreviewed:
        raw=original.read_bytes();feed=json.loads(gzip.decompress(raw))
        audit={'date':stamp,'items':len(feed['items']),'failed_query_windows':len(feed.get('fails',[])),'feed_sha256':hashlib.sha256(raw).hexdigest(),'input_mode':'existing_unreviewed_feed'}
    else:
        audit=build_feed(date,harvest)
        raw=original.read_bytes();feed=json.loads(gzip.decompress(raw))
    if feed.get('fails'):raise ValueError(stamp+' has failed source windows; not freezing')
    cutoff=dt.datetime.combine(date,dt.time(),dt.timezone.utc)
    if feed.get('date')!=stamp or dt.datetime.fromisoformat(feed['cutoff_utc'].replace('Z','+00:00'))!=cutoff:raise ValueError('Feed identity/cutoff mismatch')
    assert all(cutoff-dt.timedelta(days=WIN[x['cat']])<=dt.datetime.fromisoformat(x['published_at'])<cutoff for x in feed['items'])
    priority=selected(feed['items']);unresolved=sorted({x['url'] for x in priority if x['url'] not in cache or cache[x['url']].get('error')})
    need=[] if conservative_offline else unresolved
    print(stamp,'screening',len(priority),'priority Reuters records;',len(need),'new metadata lookups',flush=True)
    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        for n,(url,result) in enumerate(pool.map(metadata,need),1):
            cache[url]=result
            if n%20==0:atomic_json(META,cache)
    atomic_json(META,cache)
    failed=[x['id'] for x in priority if x['url'] not in cache or cache[x['url']].get('error')]
    if failed:
        print(stamp,'conservatively excluding',len(failed),'priority records with unresolved metadata',flush=True)
    prioritized={x['id'] for x in priority};ready=[];excluded=[]
    for item in feed['items']:
        result=cache.get(item['url'],{}) if is_reuters(item) else {}
        day=result.get('canonical_date')
        reason=release_guard_reason(item,stamp)
        if day and day>=stamp:reason='canonical_date_at_or_after_report; original pre-cutoff availability unverified; conservatively excluded'
        elif item['id'] in prioritized and (result.get('error') or not day):reason='priority canonical date could not be established; conservatively excluded'
        if reason:
            excluded.append({**item,'reason':reason,'metadata':result});continue
        if day:item={**item,'canonical_url':result['canonical_url'],'canonical_date':day}
        ready.append(item)
    feed['items']=ready;feed['canonical_screening']='Selected priority Reuters items checked via available news.google.com metadata; high-risk July actuals screened against reviewer release eligibility dates. Every unresolved priority canonical date, including transport failures and unavailable offline lookups, is excluded conservatively. Unverified same-day stories omitted. Surviving IDs unchanged. Other headlines require own-date editorial review.'
    target=ROOT/'feeds'/(stamp+'.json.gz');atomic_json(target,feed,True)
    receipt={**audit,'date':stamp,'unreviewed_items':audit['items'],'items':len(ready),'feed_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'unreviewed_sha256':hashlib.sha256(raw).hexdigest(),'ready_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'ready_items':len(ready),'priority_reuters_records':len(priority),'metadata_lookup_failures':len(failed),'unresolved_priority_ids':failed,'conservative_offline_mode':conservative_offline,'network_lookups_attempted':len(need),'excluded_items':excluded,'excluded_count':len(excluded),'surviving_ids_preserved':True,'freeze_policy':'Use successful canonical metadata; exclude every unresolved priority Reuters ID instead of treating transport readiness as factual verification.','release_guard_version':'July-2025-reviewed-calendar-v1','scope':'Selected Reuters canonical-date screening plus conservative July high-risk release calendar. Not exhaustive publication-time verification. Early-local releases without verified intraday timing may be conservatively omitted.'}
    atomic_json(ROOT/'audit'/('news_ready_'+stamp+'.json'),receipt)
    print(stamp,'READY',len(ready),'headlines;',len(excluded),'excluded IDs',','.join(x['id'] for x in excluded),flush=True)
    return receipt

def main():
    ap=argparse.ArgumentParser();ap.add_argument('dates',nargs='*');ap.add_argument('--watch',action='store_true');ap.add_argument('--from-unreviewed',action='store_true',help='screen already harvested work/unreviewed_feeds files; no query-window cache needed');ap.add_argument('--conservative-offline',action='store_true',help='use available canonical metadata without network retries; exclude every unresolved priority Reuters ID');ap.add_argument('--workers',type=int,default=4);a=ap.parse_args()
    dates=[dt.date.fromisoformat(d) for d in a.dates] if a.dates else DATES
    if any(d not in DATES for d in dates):raise ValueError('July 2025 weekdays only')
    jobs=make_jobs(DATES);cache=json.loads(META.read_text()) if META.exists() else {};pending=set(dates)
    while pending:
        harvest,missing=([],[]) if a.from_unreviewed else cached_harvest(jobs);progress=False
        for date in sorted(pending,key=lambda d:(PRIORITY.get(d,99),d)):
            needed=[j for j in missing if j[4]<date and j[5]>date-dt.timedelta(days=WIN[j[2]])]
            if needed:continue
            if a.from_unreviewed and not (ROOT/'work'/'unreviewed_feeds'/(date.isoformat()+'.json.gz')).exists():continue
            target=ROOT/'feeds'/(date.isoformat()+'.json.gz')
            if target.exists():print(date,'already frozen; not changed',flush=True)
            else:
                receipt=freeze(date,harvest,cache,a.workers,a.from_unreviewed,a.conservative_offline)
                if receipt is None:continue
            pending.remove(date);progress=True
        if not a.watch:break
        if pending:
            print('Waiting for',len(pending),'dates;',len(missing),'missing/failed windows',flush=True);time.sleep(10)
    print('Remaining dates',[d.isoformat() for d in sorted(pending)],flush=True)
if __name__=='__main__':main()
