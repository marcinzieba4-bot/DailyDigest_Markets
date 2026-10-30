"""Freeze May feeds when all required query windows are fetched.

Screen selected high-priority Reuters headlines against canonical URL dates via
approved Google News metadata. Unknown same-day availability is conservatively
excluded. This is not article-body or original-vintage verification. Surviving
feed IDs are preserved; the unreviewed harvest remains in work/.
"""
from __future__ import annotations
import argparse, concurrent.futures as cf, datetime as dt, gzip, hashlib
import importlib.util, json, re, sys, time, urllib.parse
from pathlib import Path
from collections import Counter
from fetch_news import ROOT,CACHE,VERSION,WIN,make_jobs,url_for,build_feed,atomic_json
from digest import rank

DATES=[dt.date(2025,5,n) for n in range(1,31) if dt.date(2025,5,n).weekday()<5]
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
PREVIEW = re.compile(r'\b(?:preview|previews|ahead of|week ahead|what to expect|expected|expects?|forecast|forecasts|forecasting|will|would|might|could|likely|seen|set to|due|awaits?|waiting|on hold ahead|decision day|to (?:hold|cut|raise|leave|keep|release|report|meet))\b', re.I)
RELEASE_GUARDS = [
    ('PBOC May7 easing package', '2025-05-01', '2025-05-08', r'(?=.*(?:China|Chinese|PBOC|People.s Bank))(?=.*(?:cuts?|cutting|lower|reduces?|easing|stimulus))(?=.*(?:interest rates|policy rate|reserve requirement|RRR|bank reserves|benchmark rate))'),
    ('Poland Q1 GDP flash', '2025-05-09', '2025-05-16', r'(?=.*(?:Poland|Polish|Polsk|PKB|GUS))(?=.*(?:GDP|PKB))(?=.*(?:Q1|first.quarter|pierwsz|1 kwart))'),
    ('Poland April final CPI', '2025-05-09', '2025-05-16', r'(?=.*(?:Poland|Polish|Polsk|GUS|inflacj))(?=.*(?:CPI|inflation|inflacj|cen))(?=.*(?:April|kwiet))(?=.*(?:final|ostatecz|4[.,]3|skorygow))'),
    ('Poland April wages and employment', '2025-05-15', '2025-05-22', r'(?=.*(?:Poland|Polish|Polsk|GUS|wynagrodz|zatrudn))(?=.*(?:wages|salary|employment|wynagrodz|zatrudn))(?=.*(?:April|kwiet))'),
    ('Poland April industry', '2025-05-15', '2025-05-22', r'(?=.*(?:Poland|Polish|Polsk|GUS|przemysł))(?=.*(?:industrial|industry|produkcj.*przemysł|przemysł.*produkcj))(?=.*(?:April|kwiet))'),
    ('Poland April construction', '2025-05-16', '2025-05-23', r'(?=.*(?:Poland|Polish|Polsk|GUS|budowlan))(?=.*(?:construction|budowlan))(?=.*(?:April|kwiet))'),
    ('Poland April retail sales', '2025-05-20', '2025-05-27', r'(?=.*(?:Poland|Polish|Polsk|GUS|sprzedaż|sprzedaz))(?=.*(?:retail sales|sprzedaż detal|sprzedaz detal))(?=.*(?:April|kwiet))'),
    ('Australia April retail sales', '2025-05-24', '2025-06-02', r'(?=.*Australia)(?=.*retail)(?=.*(?:April|Apr\b))'),
    ('BOJ May decision', '2025-04-25', '2025-05-02', r'(?=.*(?:BOJ|Bank of Japan))(?=.*(?:holds?|keeps?|leaves?|decision|raises?|hikes?|rates))(?=.*(?:May|unchanged|hold|cuts? growth))'),
    ('US April ISM manufacturing', '2025-04-25', '2025-05-02', r'(?=.*(?:ISM|Institute for Supply Management))(?=.*(?:manufactur|factory))(?=.*(?:April|Apr\b))'),
    ('US April payrolls', '2025-04-26', '2025-05-05', r'(?=.*(?:U\.?S\.?|American|nonfarm|payroll|jobs report))(?=.*(?:jobs|payroll|unemployment|hiring))(?=.*(?:April|Apr\b|177,000|177000))'),
    ('US April ISM services', '2025-04-29', '2025-05-06', r'(?=.*(?:ISM|Institute for Supply Management))(?=.*(?:services|non.manufactur))(?=.*(?:April|Apr\b))'),
    ('China April Caixin services PMI', '2025-04-29', '2025-05-07', r'(?=.*(?:Caixin|private.sector|private survey))(?=.*(?:China|Chinese|Caixin))(?=.*services)(?=.*(?:April|Apr\b))'),
    ('FOMC May decision', '2025-05-01', '2025-05-08', r'(?=.*(?:Fed|Federal Reserve|FOMC))(?=.*(?:holds? rates|keeps? rates|leaves? rates|rate decision|unchanged|interest rates steady))'),
    ('NBP May decision', '2025-05-01', '2025-05-08', r'(?=.*(?:NBP|RPP|Poland|Polish|Glapiński))(?=.*(?:cuts? rates|rate cut|cuts? interest|stóp|stopy procentowe|rate decision|interest rates))(?=.*(?:May|maj|cuts?|obni|decision))'),
    ('BoE May decision', '2025-05-02', '2025-05-09', r'(?=.*(?:BoE|Bank of England))(?=.*(?:cuts?|holds?|keeps?|leaves?|decision|rates))'),
    ('China April trade', '2025-05-03', '2025-05-12', r'(?=.*China)(?=.*(?:exports|imports|trade surplus|trade data))(?=.*(?:April|Apr\b))'),
    ('China April inflation', '2025-05-04', '2025-05-12', r'(?=.*China)(?=.*(?:CPI|PPI|inflation|deflation|consumer prices|producer prices))(?=.*(?:April|Apr\b))'),
    ('US April CPI', '2025-05-07', '2025-05-14', r'(?=.*(?:U\.?S\.?|American|Fed))(?=.*(?:CPI|inflation|consumer prices))(?=.*(?:April|Apr\b))'),
    ('US April PPI', '2025-05-09', '2025-05-16', r'(?=.*(?:U\.?S\.?|American|PPI))(?=.*(?:PPI|producer prices|wholesale prices))(?=.*(?:April|Apr\b))'),
    ('US April retail sales', '2025-05-09', '2025-05-16', r'(?=.*(?:U\.?S\.?|American))(?=.*retail sales)(?=.*(?:April|Apr\b))'),
    ('Australia April employment', '2025-05-09', '2025-05-16', r'(?=.*Australia)(?=.*(?:jobs|employment|unemployment|hiring))(?=.*(?:April|Apr\b))'),
    ('China April activity', '2025-05-13', '2025-05-20', r'(?=.*China)(?=.*(?:retail sales|industrial (?:output|production)|fixed.asset|home prices))(?=.*(?:April|Apr\b))'),
    ('RBA May decision', '2025-05-14', '2025-05-21', r'(?=.*(?:RBA|Reserve Bank of Australia))(?=.*(?:cuts?|holds?|keeps?|leaves?|decision|rates))'),
    ('China May LPR', '2025-05-14', '2025-05-21', r'(?=.*(?:China|PBOC))(?=.*(?:loan prime|benchmark lending|LPR))(?=.*(?:May|cuts?|lowers?|record low))'),
    ('UK April CPI', '2025-05-15', '2025-05-22', r'(?=.*(?:UK|U\.?K\.?|Britain|British))(?=.*(?:CPI|inflation|consumer prices))(?=.*(?:April|Apr\b))'),
    ('May flash PMIs', '2025-05-16', '2025-05-23', r'(?=.*(?:PMI|purchasing managers|business activity))(?=.*(?:May|flash))(?=.*(?:euro\s?zone|Germany|German|France|French|Britain|British|UK|U\.?S\.?|S&P Global))'),
    ('Australia April monthly CPI', '2025-05-22', '2025-05-29', r'(?=.*Australia)(?=.*(?:CPI|inflation|consumer prices))(?=.*(?:April|Apr\b|monthly))'),
    ('FOMC May minutes', '2025-05-22', '2025-05-29', r'(?=.*(?:Fed|Federal Reserve|FOMC))(?=.*minutes)(?=.*(?:May|tariff|inflation|uncertainty))'),
    ('US Q1 GDP second estimate', '2025-05-23', '2025-05-30', r'(?=.*(?:U\.?S\.?|American))(?=.*(?:GDP|gross domestic product|economy|growth))(?=.*(?:Q1|first.quarter|1st.quarter))(?=.*(?:second|revised|revision))'),
    ('US April PCE', '2025-05-24', '2025-06-02', r'(?=.*(?:PCE|personal consumption expenditure))(?=.*(?:April|Apr\b))'),
    ('Polish May flash CPI', '2025-05-24', '2025-06-02', r'(?=.*(?:Poland|Polish|Polsce|Polski|inflacja|inflacji))(?=.*(?:CPI|inflation|consumer prices|inflacja|inflacji))(?=.*(?:May|maj))'),
]

def release_guard_reason(item, stamp):
    title=item['title']
    if PREVIEW.search(title) or re.search(r'\b(?:prognoz|oczekuj|oczekiw|może|moze|prawdopodob|zapowied|szacuj)',title,re.I): return None
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
    failed=[x['id'] for x in priority if x['url'] not in cache or cache[x['url']].get('error') or not cache[x['url']].get('canonical_date')]
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
    feed['items']=ready;feed['canonical_screening']='Selected priority Reuters items checked via available news.google.com metadata; high-risk May actuals screened against reviewer release eligibility dates. Every unresolved priority canonical date, including transport failures and unavailable offline lookups, is excluded conservatively. Unverified same-day stories omitted. Surviving IDs unchanged. Other headlines require own-date editorial review.'
    target=ROOT/'feeds'/(stamp+'.json.gz');atomic_json(target,feed,True)
    receipt={**audit,'date':stamp,'unreviewed_items':audit['items'],'items':len(ready),'feed_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'unreviewed_sha256':hashlib.sha256(raw).hexdigest(),'ready_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'ready_items':len(ready),'priority_reuters_records':len(priority),'metadata_lookup_failures':len(failed),'unresolved_priority_ids':failed,'conservative_offline_mode':conservative_offline,'network_lookups_attempted':len(need),'excluded_items':excluded,'excluded_count':len(excluded),'surviving_ids_preserved':True,'freeze_policy':'Use successful canonical metadata; exclude every unresolved priority Reuters ID instead of treating transport readiness as factual verification.','release_guard_version':'May-2025-reviewed-calendar-v1','scope':'Selected Reuters canonical-date screening plus conservative May high-risk release calendar. Not exhaustive publication-time verification. Early-local releases without verified intraday timing may be conservatively omitted.'}
    atomic_json(ROOT/'audit'/('news_ready_'+stamp+'.json'),receipt)
    print(stamp,'READY',len(ready),'headlines;',len(excluded),'excluded IDs',','.join(x['id'] for x in excluded),flush=True)
    return receipt

def expanded_readiness_audit():
    """Validate append-only expanded evidence while retaining initial receipts."""
    expansion=json.loads((ROOT/'audit/news_feed_expansion.json').read_text())
    harvest=json.loads((ROOT/'audit/news_fetch_audit.json').read_text())
    daily=json.loads((ROOT/'audit/news_daily_expansion_harvest.json').read_text())
    prefix=json.loads((ROOT/'audit/news_prefix_expansion_harvest.json').read_text())
    refinement=json.loads((ROOT/'audit/news_refinement_expansion_harvest.json').read_text());assert refinement['failed_requests']==0
    assert prefix['failed_requests']==0 and expansion['prefix_requests']==prefix['prefix_requests']
    assert hashlib.sha256((ROOT/expansion['plan_archive']).read_bytes()).hexdigest()==expansion['plan_sha256']
    assert hashlib.sha256((ROOT/expansion['prefix_plan_archive']).read_bytes()).hexdigest()==expansion['prefix_plan_sha256']
    assert hashlib.sha256((ROOT/expansion['refinement_plan_archive']).read_bytes()).hexdigest()==expansion['refinement_plan_sha256']
    remaining_caps={x['signature']for x in daily['rows']+prefix['rows']+refinement['rows']if x['possibly_capped']}
    plan=json.loads((ROOT/expansion['plan_archive']).read_text())
    remaining_caps.update(x['signature']for x in plan['already_daily_capped'])
    assert expansion['status']=='expanded_verified' and daily['failed_requests']==0
    rows=[]
    for row in expansion['date_rows']:
        stamp=row['date'];path=ROOT/'feeds'/(stamp+'.json.gz');initial_path=ROOT/'feeds_initial'/path.name
        raw=path.read_bytes();feed=json.loads(gzip.decompress(raw));initial=json.loads(gzip.decompress(initial_path.read_bytes()))
        original=json.loads(gzip.decompress((ROOT/'work/news_expansion/unreviewed_initial'/path.name).read_bytes()))
        candidate_path=ROOT/row['candidate_archive'];candidates=json.loads(gzip.decompress(candidate_path.read_bytes()))
        assert hashlib.sha256(raw).hexdigest()==row['final_feed_sha256']
        assert hashlib.sha256(initial_path.read_bytes()).hexdigest()==row['initial_feed_sha256']
        assert hashlib.sha256(candidate_path.read_bytes()).hexdigest()==row['candidate_sha256']
        assert feed['items'][:len(initial['items'])]==initial['items']
        additions=feed['items'][len(initial['items']):];ids=[x['id']for x in feed['items']]
        assert [x['id']for x in additions]==row['added_ids'] and len(ids)==len(set(ids))
        oldkeys={(x['title'].casefold(),x['src'].casefold(),x['published_at'])for x in original['items']}
        assert all((x['title'].casefold(),x['src'].casefold(),x['published_at'])not in oldkeys for x in additions)
        assert all(int(x['id'][1:])>row['initial_raw_max_id']for x in additions)
        assert set(candidates['accepted_ids'])==set(row['added_ids']) and not candidates['pending_ids']
        assert additions==[x for x in candidates['items']if x['id']in set(candidates['accepted_ids'])]
        cutoff=dt.datetime.combine(dt.date.fromisoformat(stamp),dt.time(),dt.timezone.utc)
        assert feed['date']==stamp and dt.datetime.fromisoformat(feed['cutoff_utc'])==cutoff
        for item in feed['items']:
            pub=dt.datetime.fromisoformat(item['published_at'])
            assert pub.tzinfo is not None and cutoff-dt.timedelta(days=WIN[item['cat']])<=pub<cutoff
        by_topic=Counter(t for x in feed['items']for t in x['topics']);assert set(by_topic)==set(CAPS)
        before=json.loads((ROOT/'audit/news_initial'/('news_ready_'+stamp+'.json')).read_text())
        initial_excluded={x['id']for x in before['excluded_items']};assert not initial_excluded&set(ids)
        additions_by_id={x['id']:x for x in candidates['items']}
        exclusions=before['excluded_items']+[{**additions_by_id[x['id']],'reason':x['reason'],'metadata':x.get('metadata',{})}for x in candidates['excluded']]
        receipt={**before,'version':expansion['version'],'initial_receipt':'audit/news_initial/news_ready_'+stamp+'.json',
                 'initial_feed_sha256':row['initial_feed_sha256'],'initial_items':len(initial['items']),
                 'items':len(ids),'ready_items':len(ids),'feed_sha256':row['final_feed_sha256'],'ready_sha256':row['final_feed_sha256'],
                 'added_items':len(additions),'added_ids':row['added_ids'],'excluded_items':exclusions,'excluded_count':len(exclusions),
                 'unreviewed_items':before['unreviewed_items']+len(candidates['items']),
                 'initial_unreviewed_sha256':before['unreviewed_sha256'],'expansion_candidate_sha256':row['candidate_sha256'],
                 'unreviewed_input_mode':'Archived initial raw feed plus separately hash-bound expansion candidate archive',
                 'priority_reuters_records':before['priority_reuters_records']+len(candidates['priority_ids']),
                 'release_guard_version':'May2025expanded-calendar-v2-new-candidates-only',
                 'scope':'Initial objects retained exactly for traceability; new candidates screened by current release guards and priority canonical metadata. Every cited claim still requires editorial timing review.',
                 'metadata_lookup_failures':0,'unresolved_priority_ids':[],
                 'publication_date_unverified_exclusions':sum('has no publication date'in x['reason']for x in candidates['excluded']),
                 'original_objects_unchanged':True,'original_exclusions_not_resurrected':True,
                 'versioned_expansion_receipt':'audit/news_feed_expansion.json','immutable_after_final_expansion':True,
                 'source_windows':'audit/news_daily_expansion_harvest.json'}
        atomic_json(ROOT/'audit'/('news_ready_'+stamp+'.json'),receipt)
        rows.append({'date':stamp,'ready_items':len(ids),'feed_sha256':row['final_feed_sha256'],'initial_feed_sha256':row['initial_feed_sha256'],
                     'initial_items':len(initial['items']),'added_items':len(additions),'excluded_count':len(exclusions),
                     'priority_reuters_records':before['priority_reuters_records']+len(candidates['priority_ids']),
                     'unresolved_priority_records':0,'by_topic':dict(sorted(by_topic.items()))})
    out={'status':'passed','version':expansion['version'],'observed_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
         'month':'2025-05','report_dates':len(rows),'missing_dates':[],
         'shared_query_windows':harvest['shared_query_windows'],'query_count':harvest['query_count'],
         'failed_query_windows':len(harvest['failed_windows'])+daily['failed_requests'],
         'initial_possibly_capped_RSS_windows':harvest['possibly_capped_windows'],
         'daily_child_query_windows':daily['daily_requests'],
         'as_of_cutoff_prefix_windows':prefix['prefix_requests'],'possibly_capped_prefix_requests':prefix['possibly_capped_prefix_requests'],
         'failed_prefix_windows':prefix['failed_requests'],'failed_refinement_windows':refinement['failed_requests'],
         'refinement_daily_windows':refinement['refinement_daily_requests'],'remaining_distinct_daily_caps':expansion['remaining_distinct_daily_caps'],
         'unique_total_request_urls':expansion['unique_total_request_urls'],'possibly_capped_RSS_windows':len(remaining_caps),
         'initial_unreviewed_own_date_records':165679,'initial_ready_own_date_records':165575,
         'unreviewed_own_date_records':165679+sum(len(json.loads(gzip.decompress((ROOT/x['candidate_archive']).read_bytes()))['items'])for x in expansion['date_rows']),
         'ready_own_date_records':sum(x['ready_items']for x in rows),'added_ready_records':sum(x['added_items']for x in rows),
         'excluded_records':sum(x['excluded_count']for x in rows),'priority_reuters_records':sum(x['priority_reuters_records']for x in rows),
         'unresolved_priority_records':0,'immutable_after_handoff':False,'versioned_initial_snapshot_preserved':True,
         'immutable_after_final_expansion':True,'date_rows':rows,
         'rules_verified':['22weekday own-date exclusive UTC cutoffs','7/14/35day category ages','15topics each date','Exact archived initial feed hashes',
                           'Every initial item object unchanged','New keys absent original unreviewed snapshots','Initial exclusions never resurrected',
                           'Appended unique identifiers above initial raw maximum','All child requests fetched and priority mappings resolved'],
         'limits':['Daily splitting repairs known capped-weekly crowding but remaining daily ceilings and Google indexing prevent exhaustive coverage claims.',
                   'Original publisher-body vintages are not independently archived; selected canonical dates and release guards require editorial timing review.']}
    assert out['report_dates']==22 and out['ready_own_date_records']==expansion['final_ready_records']
    output=ROOT/'audit/news_ready_audit.json'
    if output.exists():
        existing=json.loads(output.read_text())
        semantic=lambda r:{k:v for k,v in r.items()if k!='observed_at_utc'}
        if semantic(existing)==semantic(out):return existing
    atomic_json(output,out)
    return out


def readiness_audit():
    """Bind the active version to its own date and archived initial snapshot."""
    if (ROOT/'audit/news_feed_expansion.json').exists():
        return expanded_readiness_audit()
    rows=[];missing=[]
    for date in DATES:
        stamp=date.isoformat();fp=ROOT/'feeds'/(stamp+'.json.gz');rp=ROOT/'audit'/('news_ready_'+stamp+'.json')
        if not fp.exists() or not rp.exists():missing.append(stamp);continue
        raw=fp.read_bytes();feed=json.loads(gzip.decompress(raw));receipt=json.loads(rp.read_text())
        cutoff=dt.datetime.combine(date,dt.time(),dt.timezone.utc);items=feed['items'];ids=[x['id'] for x in items]
        if feed.get('date')!=stamp or dt.datetime.fromisoformat(feed['cutoff_utc'])!=cutoff:raise ValueError('Ready feed identity/cutoff changed '+stamp)
        if feed.get('fails') or receipt.get('failed_query_windows'):raise ValueError('Failed source query window in '+stamp)
        if len(ids)!=len(set(ids)) or not ids:raise ValueError('Missing/duplicate source IDs in '+stamp)
        for item in items:
            pub=dt.datetime.fromisoformat(item['published_at'])
            if pub.tzinfo is None or not cutoff-dt.timedelta(days=WIN[item['cat']])<=pub<cutoff:raise ValueError('Source age/timing failure '+stamp+' '+item['id'])
        digest=hashlib.sha256(raw).hexdigest()
        if digest!=receipt['ready_sha256'] or digest!=receipt['feed_sha256'] or len(items)!=receipt['ready_items']:raise ValueError('Ready hash/count mismatch '+stamp)
        original=json.loads(gzip.decompress((ROOT/'work/unreviewed_feeds'/(stamp+'.json.gz')).read_bytes()))
        original_ids={x['id'] for x in original['items']};excluded={x['id'] for x in receipt['excluded_items']}
        if set(ids)&excluded or set(ids)|excluded!=original_ids:raise ValueError('Source ID survival/exclusion mismatch '+stamp)
        by_topic=Counter(t for x in items for t in x['topics'])
        if set(by_topic)!=set(CAPS):raise ValueError('Incomplete topic groups in '+stamp)
        rows.append({'date':stamp,'ready_items':len(items),'feed_sha256':digest,'excluded_count':receipt['excluded_count'],'priority_reuters_records':receipt['priority_reuters_records'],'unresolved_priority_records':receipt['metadata_lookup_failures'],'conservative_offline_mode':receipt['conservative_offline_mode'],'network_lookups_attempted':receipt['network_lookups_attempted'],'by_topic':dict(sorted(by_topic.items()))})
    harvest=json.loads((ROOT/'audit/news_fetch_audit.json').read_text())
    out={'status':'passed' if not missing else 'partial','observed_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'month':'2025-05','report_dates':len(rows),'missing_dates':missing,'shared_query_windows':harvest['shared_query_windows'],'query_count':harvest['query_count'],'failed_query_windows':len(harvest['failed_windows']),'possibly_capped_RSS_windows':harvest['possibly_capped_windows'],'unreviewed_own_date_records':sum(json.loads((ROOT/'audit'/('news_ready_'+x['date']+'.json')).read_text())['unreviewed_items'] for x in rows),'ready_own_date_records':sum(x['ready_items'] for x in rows),'excluded_records':sum(x['excluded_count'] for x in rows),'priority_reuters_records':sum(x['priority_reuters_records'] for x in rows),'unresolved_priority_records':sum(x['unresolved_priority_records'] for x in rows),'rules_verified':['22 May Monday-Friday dates including exchange holidays','Exact own-date midnight UTC cutoff','Strictly earlier timezone-aware publication timestamps','7/14/35-day final category age bounds','No failed required query windows','15 topic groups in every ready feed','Unique IDs and ready audit SHA256/count equality','Original IDs preserved for every surviving source row'],'immutable_after_handoff':True,'date_rows':rows,'limits':['Google RSS query-window result ceilings make coverage broad, not exhaustive.','Selected priority Reuters canonical dates and conservative release-calendar guards do not prove original article-body vintages.','Every unresolved priority canonical date is excluded; other cited source metadata and release claims need independent date/timing review.']}
    atomic_json(ROOT/'audit/news_ready_audit.json',out)
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('dates',nargs='*');ap.add_argument('--watch',action='store_true');ap.add_argument('--from-unreviewed',action='store_true',help='screen already harvested work/unreviewed_feeds files; no query-window cache needed');ap.add_argument('--conservative-offline',action='store_true',help='use available canonical metadata without network retries; exclude every unresolved priority Reuters ID');ap.add_argument('--workers',type=int,default=4);a=ap.parse_args()
    dates=[dt.date.fromisoformat(d) for d in a.dates] if a.dates else DATES
    if any(d not in DATES for d in dates):raise ValueError('May 2025 weekdays only')
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
    if (ROOT/'audit/news_fetch_audit.json').exists():
        audit=readiness_audit();print('Readiness audit',audit['status'],audit['report_dates'],'dates',audit['ready_own_date_records'],'records',flush=True)
if __name__=='__main__':main()
