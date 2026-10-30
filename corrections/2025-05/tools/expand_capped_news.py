"""Versioned May coverage repair: daily children of capped shared RSS windows.

Never renumber or modify initial source objects, revive screened raw records,
fetch canonical metadata, edit prose, or overwrite original acquisition inputs.
Run harvest, stage, then apply only after root imports required public mappings.
"""
from __future__ import annotations
import argparse, concurrent.futures as cf, datetime as dt, gzip, hashlib, json
import re, shutil, sys
from collections import Counter, defaultdict
from pathlib import Path
from fetch_news import ROOT,CACHE,VERSION,WIN,UTC,fetch,make_jobs,cutoff_prefix_jobs,url_for,collect_feed,atomic_json
from ready_feeds import DATES,CAPS,selected,is_reuters,release_guard_reason

WORK=ROOT/'work/news_expansion'
PLAN=WORK/'plan.json'
VERSION2='may-daily-cap-expansion-v2'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):
    raw=path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix=='.gz' else raw)
def key(item): return (item['title'].casefold(),item['src'].casefold(),item['published_at'])
def sig(job):
    url,_=url_for(job[1],job[4],job[5],job[3])
    return hashlib.sha256((VERSION+'\n'+url).encode()).hexdigest(),url

def snapshot():
    receipt=ROOT/'audit/news_expansion_initial_snapshot.json'
    if receipt.exists():
        out=read(receipt)
        for row in out['files']:
            assert sha(ROOT/row['archive'])==row['sha256'],row
        return out
    WORK.mkdir(parents=True,exist_ok=True)
    files=[]
    groups=[(ROOT/'feeds',ROOT/'feeds_initial','*.json.gz'),
            (ROOT/'work/unreviewed_feeds',WORK/'unreviewed_initial','*.json.gz'),
            (ROOT/'specs',WORK/'drafts_at_start','*.json')]
    for source,dest,pattern in groups:
        dest.mkdir(parents=True,exist_ok=True)
        for p in sorted(source.glob(pattern)):
            target=dest/p.name;raw=p.read_bytes()
            if target.exists():assert target.read_bytes()==raw
            else:target.write_bytes(raw)
            files.append({'source':str(p.relative_to(ROOT)),'archive':str(target.relative_to(ROOT)),
                          'sha256':sha(target),'bytes':len(raw)})
    dest=ROOT/'audit/news_initial';dest.mkdir(parents=True,exist_ok=True)
    for p in sorted((ROOT/'audit').glob('news_ready*.json')):
        target=dest/p.name;shutil.copy2(p,target)
        files.append({'source':str(p.relative_to(ROOT)),'archive':str(target.relative_to(ROOT)),
                      'sha256':sha(target),'bytes':target.stat().st_size})
    out={'captured_at_utc':dt.datetime.now(UTC).isoformat(),'purpose':'Byte-exact initial author feeds, unreviewed harvest, ready receipts and available draft specifications before append-only coverage repair.',
         'initial_ready_records':sum(len(read(ROOT/'feeds_initial'/(d.isoformat()+'.json.gz'))['items'])for d in DATES),
         'initial_unreviewed_records':sum(len(read(WORK/'unreviewed_initial'/(d.isoformat()+'.json.gz'))['items'])for d in DATES),
         'initial_screened_exclusions':104,'initial_report_dates':22,'files':files,
         'draft_note':'Draft files present at this snapshot are archived byte-exact. A second snapshot before feed apply records drafts completed or edited meanwhile.'}
    assert out['initial_ready_records']==165575 and out['initial_unreviewed_records']==165679
    atomic_json(receipt,out)
    return out

def plan():
    snapshot()
    if PLAN.exists():return add_targeted_uncapped_window(read(PLAN))
    parents=[];children={};single=[]
    for job in make_jobs(DATES):
        signature,url=sig(job);path=CACHE/(signature+'.json.gz');batch=read(path)
        assert batch['status']=='fetched'
        if not batch.get('possibly_capped'):continue
        lo,hi=job[4:];row={'signature':signature,'request_url':url,'cache_sha256':sha(path),
            'raw_sha256':batch['raw_sha256'],'raw_count':batch['raw_count'],'topic':job[0],
            'query':job[1],'category':job[2],'locale':job[3],'lower_date':lo.isoformat(),'upper_date_exclusive':hi.isoformat()}
        parents.append(row)
        if (hi-lo).days==1:single.append(row);continue
        for offset in range((hi-lo).days):
            day=lo+dt.timedelta(days=offset);child=(*job[:4],day,day+dt.timedelta(days=1));cs,cu=sig(child)
            origin={k:row[k]for k in ['signature','topic','query','category','locale','lower_date','upper_date_exclusive']}
            if cu not in children:
                children[cu]={'signature':cs,'request_url':cu,'job':[child[0],child[1],child[2],list(child[3]),day.isoformat(),(day+dt.timedelta(days=1)).isoformat()],'origins':[]}
            if origin not in children[cu]['origins']:children[cu]['origins'].append(origin)
    assert len(parents)==150,(len(parents),'initial capped request-context windows')
    # Prioritize late-May and tariff children so the missing Sunday story resolves early.
    ordered=sorted(children.values(),key=lambda x:(x['job'][4]!='2025-05-25',x['job'][1]!='tariffs',x['job'][4],x['job'][1],x['request_url']))
    out={'version':VERSION2,'created_at_utc':dt.datetime.now(UTC).isoformat(),'initial_capped_windows':len(parents),
         'multi_day_parent_contexts':len(parents)-len(single),'already_daily_capped_contexts':len(single),
         'parents':parents,'already_daily_capped':single,'unique_daily_child_requests':len(ordered),'children':ordered,
         'rule':'Split every capped multi-day context into UTC date-bounded daily requests; physical requests deduplicated by full URL, retaining all topic/category/parent lineages. Existing successful URL cache reused.'}
    atomic_json(PLAN,out);return add_targeted_uncapped_window(out)

def add_targeted_uncapped_window(obj):
    """Repair the directly observed weekly omission even below the RSS ceiling."""
    if obj.get('targeted_uncapped_parents'):return obj
    job=('us_macro','tariffs','news',('en-US','US','US:en'),dt.date(2025,5,22),dt.date(2025,5,29))
    signature,url=sig(job);path=CACHE/(signature+'.json.gz');batch=read(path)
    assert batch['status']=='fetched' and not batch['possibly_capped']
    parent={'signature':signature,'request_url':url,'cache_sha256':sha(path),'raw_sha256':batch['raw_sha256'],
            'raw_count':batch['raw_count'],'topic':job[0],'query':job[1],'category':job[2],'locale':job[3],
            'lower_date':job[4].isoformat(),'upper_date_exclusive':job[5].isoformat(),
            'reason':'Direct comparison showed weekly query omitted May25 EU tariff extension found by exact-day query; raw count below ceiling does not establish coverage.'}
    by_url={x['request_url']:x for x in obj['children']}
    for offset in range(7):
        day=job[4]+dt.timedelta(days=offset);child=(*job[:4],day,day+dt.timedelta(days=1));cs,cu=sig(child)
        origin={k:parent[k]for k in ['signature','topic','query','category','locale','lower_date','upper_date_exclusive']}
        if cu not in by_url:
            row={'signature':cs,'request_url':cu,'job':[child[0],child[1],child[2],list(child[3]),day.isoformat(),(day+dt.timedelta(days=1)).isoformat()],'origins':[origin]}
            obj['children'].append(row);by_url[cu]=row
        elif origin not in by_url[cu]['origins']:by_url[cu]['origins'].append(origin)
    obj['targeted_uncapped_parents']=[parent];obj['unique_daily_child_requests']=len(obj['children'])
    obj['rule']+=' Also split the directly diagnosed uncapped May22–29 tariff query; weekly result count below100 does not imply completeness.'
    atomic_json(PLAN,obj)
    return obj

def child_job(row):
    t,q,c,loc,lo,hi=row['job'];return(t,q,c,tuple(loc),dt.date.fromisoformat(lo),dt.date.fromisoformat(hi))

def harvest(workers):
    obj=plan();started=dt.datetime.now(UTC).isoformat();rows=[]
    print('Daily children',len(obj['children']),'from',obj['multi_day_parent_contexts'],'capped multi-day contexts',flush=True)
    with cf.ThreadPoolExecutor(max_workers=workers)as pool:
        for n,(child,batch)in enumerate(zip(obj['children'],pool.map(fetch,[child_job(c)for c in obj['children']])),1):
            path=CACHE/(child['signature']+'.json.gz')
            rows.append({'signature':child['signature'],'request_url':child['request_url'],'status':batch['status'],
                         'cache_sha256':sha(path),'raw_sha256':batch.get('raw_sha256'),'raw_count':batch.get('raw_count'),
                         'eligible_items':len(batch['items']),'possibly_capped':batch.get('possibly_capped',False),
                         'lower_date':child['job'][4],'upper_date_exclusive':child['job'][5],'origins':child['origins']})
            if n%50==0 or batch['status']!='fetched':print(n,'/',len(obj['children']),batch['status'],flush=True)
    out={'version':VERSION2,'started_at_utc':started,'finished_at_utc':dt.datetime.now(UTC).isoformat(),
         'plan_sha256':sha(PLAN),'daily_requests':len(rows),'failed_requests':sum(r['status']!='fetched'for r in rows),
         'remaining_daily_capped_requests':sum(r['possibly_capped']for r in rows),'initial_already_daily_capped_contexts':obj['already_daily_capped_contexts'],'targeted_uncapped_parent_contexts':len(obj.get('targeted_uncapped_parents',[])),
         'rows':rows,'limits':'Daily splitting repairs known weekly crowding. Daily result ceilings and Google indexing remain incomplete; no exhaustive coverage claim.'}
    atomic_json(ROOT/'audit/news_daily_expansion_harvest.json',out)
    print('Harvest finished',out['daily_requests'],'requests;',out['failed_requests'],'failed;',out['remaining_daily_capped_requests'],'daily capped',flush=True)
    if out['failed_requests']:raise SystemExit('Required child requests failed; feeds not changed')

def prefix_plan():
    """Every catalog context cut at each report's own midnight, before retrieval."""
    target=WORK/'prefix_plan.json'
    if target.exists():return read(target)
    contexts=[];children={};all_jobs=make_jobs(DATES)
    for date in DATES:
        for job in all_jobs:
            if not job[4]<date<job[5]:continue
            signature,url=sig(job);parent_path=CACHE/(signature+'.json.gz');batch=read(parent_path)
            assert batch['status']=='fetched'
            child=(*job[:4],job[4],date);cs,cu=sig(child)
            origin={'signature':signature,'topic':job[0],'query':job[1],'category':job[2],'locale':job[3],
                    'lower_date':job[4].isoformat(),'upper_date_exclusive':job[5].isoformat(),
                    'report_cutoff':date.isoformat(),'parent_request_url':url,'parent_cache_sha256':sha(parent_path),
                    'parent_raw_sha256':batch['raw_sha256'],'parent_raw_count':batch['raw_count']}
            contexts.append(origin)
            if cu not in children:
                children[cu]={'signature':cs,'request_url':cu,'job':[child[0],child[1],child[2],list(child[3]),job[4].isoformat(),date.isoformat()],'origins':[]}
            if origin not in children[cu]['origins']:children[cu]['origins'].append(origin)
    rows=sorted(children.values(),key=lambda x:(x['job'][5],x['job'][0],x['job'][1],x['request_url']))
    existing=sum((CACHE/(x['signature']+'.json.gz')).exists()and read(CACHE/(x['signature']+'.json.gz')).get('status')=='fetched'for x in rows)
    out={'version':VERSION2,'created_at_utc':dt.datetime.now(UTC).isoformat(),'request_contexts':len(contexts),
         'unique_prefix_requests':len(rows),'successful_requests_already_cached':existing,'requests_to_fetch':len(rows)-existing,
         'children':rows,'rule':'For every original weekly catalog context straddling a report cutoff, request [parent_lo,report_cutoff). Reuse successful cache and completed earlier windows. Never merge a request with upper bound after the consuming report cutoff.',
         'limits':'An uncapped weekly result set can omit earlier-cutoff stories. Prefix requests remove later days from the query interval, but Google ranking, indexing and remaining response caps still prevent exhaustive coverage.'}
    atomic_json(target,out);print('Prefixplan',len(contexts),'contexts',len(rows),'unique requests',existing,'cached',len(rows)-existing,'to fetch',flush=True)
    return out

def harvest_prefix(workers):
    obj=prefix_plan();started=dt.datetime.now(UTC).isoformat();rows=[]
    print('As-of-cutoff prefix requests',len(obj['children']),'workers',workers,flush=True)
    with cf.ThreadPoolExecutor(max_workers=workers)as pool:
        for n,(child,batch)in enumerate(zip(obj['children'],pool.map(fetch,[child_job(c)for c in obj['children']])),1):
            path=CACHE/(child['signature']+'.json.gz')
            rows.append({'signature':child['signature'],'request_url':child['request_url'],'status':batch['status'],
                         'cache_sha256':sha(path),'raw_sha256':batch.get('raw_sha256'),'raw_count':batch.get('raw_count'),
                         'eligible_items':len(batch['items']),'possibly_capped':batch.get('possibly_capped',False),
                         'lower_date':child['job'][4],'upper_date_exclusive':child['job'][5],'origins':child['origins']})
            if n%100==0 or batch['status']!='fetched':print(n,'/',len(obj['children']),batch['status'],child['job'][5],flush=True)
    out={'version':VERSION2,'started_at_utc':started,'finished_at_utc':dt.datetime.now(UTC).isoformat(),
         'prefix_plan_sha256':sha(WORK/'prefix_plan.json'),'prefix_requests':len(rows),
         'failed_requests':sum(r['status']!='fetched'for r in rows),'possibly_capped_prefix_requests':sum(r['possibly_capped']for r in rows),
         'rows':rows,'limits':obj['limits']}
    atomic_json(ROOT/'audit/news_prefix_expansion_harvest.json',out)
    print('Prefixharvestfinished',out['prefix_requests'],'requests;',out['failed_requests'],'failed;',out['possibly_capped_prefix_requests'],'capped',flush=True)
    if out['failed_requests']:raise SystemExit('Prefix requests failed; feed expansion not allowed')

def refinement_plan():
    target=WORK/'refinement_plan.json'
    if target.exists():return read(target)
    prefix=read(ROOT/'audit/news_prefix_expansion_harvest.json');parents=[];children={}
    for row in prefix['rows']:
        if not row['possibly_capped'] or not any(x['parent_raw_count']<100 for x in row['origins']):continue
        parents.append(row)
        for origin in row['origins']:
            lo=dt.date.fromisoformat(row['lower_date']);hi=dt.date.fromisoformat(row['upper_date_exclusive'])
            for offset in range((hi-lo).days):
                day=lo+dt.timedelta(days=offset)
                job=(origin['topic'],origin['query'],origin['category'],tuple(origin['locale']),day,day+dt.timedelta(days=1));signature,url=sig(job)
                lineage={**origin,'capped_prefix_signature':row['signature'],'capped_prefix_request_url':row['request_url']}
                if url not in children:children[url]={'signature':signature,'request_url':url,'job':[job[0],job[1],job[2],list(job[3]),day.isoformat(),(day+dt.timedelta(days=1)).isoformat()],'origins':[]}
                if lineage not in children[url]['origins']:children[url]['origins'].append(lineage)
    rows=sorted(children.values(),key=lambda x:(x['job'][4],x['job'][0],x['job'][1],x['request_url']))
    cached=sum((CACHE/(x['signature']+'.json.gz')).exists()and read(CACHE/(x['signature']+'.json.gz')).get('status')=='fetched'for x in rows)
    out={'version':VERSION2,'created_at_utc':dt.datetime.now(UTC).isoformat(),'newly_capped_prefixes_from_uncapped_weekly_parents':len(parents),
         'unique_daily_refinement_requests':len(rows),'successful_requests_already_cached':cached,'requests_to_fetch':len(rows)-cached,'parents':parents,'children':rows,
         'rule':'Refine newly capped prefix queries whose weekly parent was below ceiling into daily child windows. Other capped prefixes are covered by the initial capped-weekly daily children. No sub-day query claims.'}
    atomic_json(target,out);print('Refinementplan',len(parents),'cappedprefixes',len(rows),'dailyURLs',cached,'cached',len(rows)-cached,'new',flush=True)
    return out

def harvest_refinement(workers):
    obj=refinement_plan();started=dt.datetime.now(UTC).isoformat();rows=[]
    with cf.ThreadPoolExecutor(max_workers=workers)as pool:
        for n,(child,batch)in enumerate(zip(obj['children'],pool.map(fetch,[child_job(c)for c in obj['children']])),1):
            path=CACHE/(child['signature']+'.json.gz')
            rows.append({'signature':child['signature'],'request_url':child['request_url'],'status':batch['status'],'cache_sha256':sha(path),
                         'raw_sha256':batch.get('raw_sha256'),'raw_count':batch.get('raw_count'),'eligible_items':len(batch['items']),
                         'possibly_capped':batch.get('possibly_capped',False),'lower_date':child['job'][4],'upper_date_exclusive':child['job'][5],'origins':child['origins']})
            if n%50==0 or batch['status']!='fetched':print(n,'/',len(obj['children']),batch['status'],flush=True)
    out={'version':VERSION2,'started_at_utc':started,'finished_at_utc':dt.datetime.now(UTC).isoformat(),'refinement_plan_sha256':sha(WORK/'refinement_plan.json'),
         'refinement_daily_requests':len(rows),'new_requests':obj['requests_to_fetch'],'failed_requests':sum(x['status']!='fetched'for x in rows),
         'remaining_daily_capped_requests':sum(x['possibly_capped']for x in rows),'rows':rows,'limits':'Daily caps remain an explicit unsolved coverage ceiling; Google indexing and original publisher-body vintages remain incomplete.'}
    atomic_json(ROOT/'audit/news_refinement_expansion_harvest.json',out)
    print('Refinementfinished',len(rows),'requests;',out['failed_requests'],'failed;',out['remaining_daily_capped_requests'],'dailycapped',flush=True)
    if out['failed_requests']:raise SystemExit('Refinement requests failed; no final feed apply')

def batches_from_plan(obj):
    batches=[];windows=defaultdict(set)
    for child in obj['children']:
        path=CACHE/(child['signature']+'.json.gz')
        if not path.exists():raise ValueError('Child request not harvested '+child['signature'])
        batch=read(path);assert batch['status']=='fetched'
        contexts=set()
        for origin in child['origins']:
            context=(origin['topic'],origin['query'],origin['category'],tuple(origin['locale']))
            if context in contexts:continue
            contexts.add(context)
            batches.append({**batch,'topic':origin['topic'],'query':origin['query'],'category':origin['category'],'locale':origin['locale']})
        for item in batch['items']:windows[key(item)].add(child['signature'])
    return batches,windows

def metadata_cache():
    cache={}
    for path in [ROOT/'audit/canonical_reuters_urls.json',ROOT/'audit/canonical_all_cited_urls.json']:
        if path.exists():
            for url,row in read(path).items():
                if row.get('canonical_url')and not row.get('error'):
                    if url in cache:assert cache[url]['canonical_url']==row['canonical_url'],'Canonical cache conflict '+url
                    cache[url]=row
    return cache

def stage(partial=False):
    obj=plan();harvest_receipt=read(ROOT/'audit/news_daily_expansion_harvest.json')
    assert harvest_receipt['failed_requests']==0
    batches,windows=batches_from_plan(obj);cache=metadata_cache();pending_urls=set();rows=[]
    prefix_path=WORK/'prefix_plan.json';prefix_receipt=ROOT/'audit/news_prefix_expansion_harvest.json'
    prefixes=None;prefix_windows={};prefix_upper={};complete_dates=set(DATES);prefix_obj=None
    if prefix_path.exists():
        prefix_obj=read(prefix_path)
        if partial:
            complete_rows=[];missing_rows=[]
            for child in prefix_obj['children']:
                path=CACHE/(child['signature']+'.json.gz')
                if path.exists() and read(path).get('status')=='fetched':complete_rows.append(child)
                else:missing_rows.append(child)
            complete_dates={d for d in DATES if not any(c['job'][5]<=d.isoformat()for c in missing_rows)}
            prefix_obj={**prefix_obj,'children':complete_rows}
        elif not prefix_receipt.exists() or read(prefix_receipt)['failed_requests']:
            raise ValueError('Prefix harvest incomplete; staging remains unchanged')
        prefixes,prefix_windows=batches_from_plan(prefix_obj)
        prefix_upper={x['signature']:x['job'][5]for x in prefix_obj['children']}
    refinement=None;refine_windows={};refine_upper={};refine_path=WORK/'refinement_plan.json'
    if refine_path.exists():
        refine_receipt=ROOT/'audit/news_refinement_expansion_harvest.json'
        if not refine_receipt.exists() or read(refine_receipt)['failed_requests']:raise ValueError('Refinement incomplete; staged prefix seeds unchanged')
        refine_obj=read(refine_path);refinement,refine_windows=batches_from_plan(refine_obj)
        refine_upper={x['signature']:x['job'][5]for x in refine_obj['children']}
    for date in DATES:
        if date not in complete_dates:continue
        stamp=date.isoformat();original=read(WORK/'unreviewed_initial'/(stamp+'.json.gz'));initial=read(ROOT/'feeds_initial'/(stamp+'.json.gz'))
        original_keys={key(x)for x in original['items']};maxid=max(int(x['id'][1:])for x in original['items'])
        if prefixes is None:
            merged,discarded,failed=collect_feed(date,batches,asof_queries=True);assert not failed
            added=[x for x in merged if key(x)not in original_keys]
            for index,item in enumerate(added,maxid+1):
                item['id']=f'n{index:04d}';item['coverage_source_signatures']=sorted(windows[key(item)])
            priority={x['id']for x in selected(added)}
        else:
            seed=read(WORK/'daily_candidates'/(stamp+'.json.gz'));added=seed['items']
            daily_keys={key(x)for x in added};daily_max=max([maxid]+[int(x['id'][1:])for x in added])
            merged,discarded,failed=collect_feed(date,prefixes,asof_queries=True);assert not failed
            extra=[x for x in merged if key(x)not in original_keys and key(x)not in daily_keys]
            for index,item in enumerate(extra,daily_max+1):
                item['id']=f'n{index:04d}';item['coverage_source_signatures']=sorted(x for x in prefix_windows[key(item)]if prefix_upper[x]<=stamp)
                assert item['coverage_source_signatures']
                item['coverage_expansion_origin']='as_of_cutoff_prefix'
            priority=set(seed['priority_ids'])|{x['id']for x in selected(extra)}
            added=added+extra
        if refinement is not None:
            seed=read(WORK/'prefix_complete_seed'/(stamp+'.json.gz'));assert {x['id']:key(x)for x in seed['items']}=={x['id']:key(x)for x in added},'Prefix ID seed changed'
            existing_keys={key(x)for x in added};prefix_max=max([maxid]+[int(x['id'][1:])for x in added])
            merged,_,failed=collect_feed(date,refinement,asof_queries=True);assert not failed
            extra=[x for x in merged if key(x)not in original_keys and key(x)not in existing_keys]
            for index,item in enumerate(extra,prefix_max+1):
                item['id']=f'n{index:04d}';item['coverage_source_signatures']=sorted(x for x in refine_windows[key(item)]if refine_upper[x]<=stamp)
                item['coverage_expansion_origin']='capped_prefix_daily_refinement';assert item['coverage_source_signatures']
            priority|={x['id']for x in selected(extra)};added+=extra
        accepted=[];excluded=[];pending=[]
        for item in added:
            row=cache.get(item['url'],{}) if is_reuters(item)else{};day=row.get('canonical_date')
            reason=release_guard_reason(item,stamp)
            if day and day>=stamp:reason='canonical date at/after report; original pre-cutoff availability not proved'
            if reason:excluded.append({'id':item['id'],'reason':reason,'metadata':row});continue
            if item['id']in priority and row.get('canonical_url')and not day:
                excluded.append({'id':item['id'],'reason':'Resolved canonical URL has no publication date; original pre-cutoff availability unverified; conservatively excluded','metadata':row});continue
            if item['id']in priority and not row.get('canonical_url'):
                pending.append(item['id']);pending_urls.add(item['url']);continue
            if day:item.update(canonical_url=row['canonical_url'],canonical_date=day)
            accepted.append(item['id'])
        payload={'version':VERSION2,'date':stamp,'cutoff_utc':initial['cutoff_utc'],'initial_feed_sha256':sha(ROOT/'feeds_initial'/(stamp+'.json.gz')),
                 'initial_raw_max_id':maxid,'items':added,'accepted_ids':accepted,'excluded':excluded,'pending_ids':pending,
                 'priority_ids':sorted(priority),'original_raw_key_overlap':0}
        target=WORK/('prefix_candidates'if partial else'candidates')/(stamp+'.json.gz');atomic_json(target,payload,True)
        rows.append({'date':stamp,'initial_items':len(initial['items']),'new_candidates':len(added),'accepted':len(accepted),
                     'excluded':len(excluded),'publication_date_unverified_exclusions':sum('has no publication date'in x['reason']for x in excluded),'pending':len(pending),'candidate_path':str(target.relative_to(ROOT)),'candidate_sha256':sha(target)})
        print(stamp,'new',len(added),'accepted',len(accepted),'excluded',len(excluded),'pending',len(pending),flush=True)
        if stamp=='2025-05-26':
            for item in added:
                if re.search(r'\b(?:EU|European|tariffs?)\b',item['title'],re.I)and re.search(r'(?:delay|July 9|extension|extend|postpon)',item['title'],re.I):
                    print('MAY26_EXTENSION',item['id'],item['src'],item['published_at'],item['title'],'PENDING'if item['id']in pending else('EXCLUDED'if any(x['id']==item['id']for x in excluded)else'ACCEPTED'),flush=True)
    atomic_json(WORK/('prefix_priority_metadata_requests.json'if partial else'priority_metadata_requests.json'),{'urls':sorted(pending_urls)})
    out={'version':VERSION2,'staged_at_utc':dt.datetime.now(UTC).isoformat(),'status':'awaiting_priority_metadata'if pending_urls else'ready_to_apply',
         'feeds_changed':False,'missing_priority_urls':len(pending_urls),'new_candidates':sum(x['new_candidates']for x in rows),
         'accepted':sum(x['accepted']for x in rows),'excluded':sum(x['excluded']for x in rows),'publication_date_unverified_exclusions':sum(x['publication_date_unverified_exclusions']for x in rows),'pending':sum(x['pending']for x in rows),'rows':rows,
         'plan_sha256':sha(PLAN),'harvest_receipt_sha256':sha(ROOT/'audit/news_daily_expansion_harvest.json'),
         'prefix_plan_sha256':sha(prefix_path)if prefixes is not None else None,'prefix_harvest_sha256':sha(prefix_receipt)if prefixes is not None and prefix_receipt.exists() else None,
         'refinement_plan_sha256':sha(refine_path)if refinement is not None else None,'refinement_harvest_sha256':sha(ROOT/'audit/news_refinement_expansion_harvest.json')if refinement is not None else None,
         'staging_tool_sha256':sha(Path(__file__)),'release_guard_tool_sha256':sha(ROOT/'tools/ready_feeds.py'),
         'metadata_transport':'No native metadata requests or cache writes. Root-only public CI/cache owner receives URL-only pending payload.',
         'selection_rule':'Only title/source/publication keys absent from original unreviewed input; original exclusions cannot be resurrected. IDs above original raw maximum.'}
    out['complete_dates']=[d.isoformat()for d in sorted(complete_dates)];out['complete_month']=len(complete_dates)==len(DATES)
    atomic_json(ROOT/'audit'/('news_prefix_expansion_staging_partial.json'if partial else'news_expansion_staging.json'),out)
    print('Staged candidates',out['new_candidates'],'priority missing URLs',len(pending_urls),flush=True)
    return out

def apply():
    receipt_path=ROOT/'audit/news_feed_expansion.json'
    if receipt_path.exists():
        previous=read(receipt_path)
        assert previous['complete_month'] and previous['status']=='expanded_verified'
        for stamp,digest in previous['final_feed_sha256'].items():assert sha(ROOT/'feeds'/(stamp+'.json.gz'))==digest
        from ready_feeds import readiness_audit
        readiness_audit();print('Existing complete expansion verified; feed and expansion receipt bytes preserved',flush=True);return
    staged=stage();assert staged['status']=='ready_to_apply','Resolve all pending priority metadata before feed mutation'
    assert staged['complete_month'] and len(staged['rows'])==len(DATES)
    prefix=read(ROOT/'audit/news_prefix_expansion_harvest.json');assert prefix['failed_requests']==0
    refinement=read(ROOT/'audit/news_refinement_expansion_harvest.json');assert refinement['failed_requests']==0
    plan_archive=ROOT/'audit/news_expansion_plan.json';plan_archive.write_bytes(PLAN.read_bytes())
    prefix_plan_archive=ROOT/'audit/news_prefix_expansion_plan.json';prefix_plan_archive.write_bytes((WORK/'prefix_plan.json').read_bytes())
    refine_plan_archive=ROOT/'audit/news_refinement_expansion_plan.json';refine_plan_archive.write_bytes((WORK/'refinement_plan.json').read_bytes())
    draftdir=WORK/'drafts_before_apply';draftdir.mkdir(exist_ok=True);drafts=[]
    for path in sorted((ROOT/'specs').glob('*.json')):
        target=draftdir/path.name;target.write_bytes(path.read_bytes());drafts.append({'path':str(target.relative_to(ROOT)),'sha256':sha(target)})
    rows=[];targets=[]
    all_request_rows=read(ROOT/'audit/news_daily_expansion_harvest.json')['rows']+prefix['rows']+refinement['rows']
    all_request_urls={x['request_url']for x in all_request_rows}
    source_upper={x['signature']:x['upper_date_exclusive']for x in all_request_rows}
    original_urls={url_for(j[1],j[4],j[5],j[3])[0]for j in make_jobs(DATES)}
    daily_caps={x['signature']for x in all_request_rows if x['possibly_capped'] and (dt.date.fromisoformat(x['upper_date_exclusive'])-dt.date.fromisoformat(x['lower_date'])).days==1}
    daily_caps.update(x['signature']for x in read(PLAN)['already_daily_capped'])
    for row in staged['rows']:
        stamp=row['date'];initial_path=ROOT/'feeds_initial'/(stamp+'.json.gz');current=ROOT/'feeds'/(stamp+'.json.gz')
        initial=read(initial_path)
        payload=read(ROOT/row['candidate_path']);accepted=set(payload['accepted_ids']);added=[x for x in payload['items']if x['id']in accepted]
        ids={x['id']for x in initial['items']};assert not(ids&{x['id']for x in added})
        assert all(item['coverage_source_signatures']and all(signature in source_upper and source_upper[signature]<=stamp for signature in item['coverage_source_signatures'])for item in added)
        cutoff=dt.datetime.fromisoformat(initial['cutoff_utc']);final={**initial,'items':initial['items']+added,
          'coverage_expansion':{'version':VERSION2,'initial_feed_sha256':sha(initial_path),'added_items':len(added),'initial_author_snapshot':str(initial_path.relative_to(ROOT)),
                                'initial_objects_unchanged':True,'source_window_plan':'audit/news_daily_expansion_harvest.json'}}
        assert final['items'][:len(initial['items'])]==initial['items']
        for item in final['items']:
            pub=dt.datetime.fromisoformat(item['published_at']);assert cutoff-dt.timedelta(days=WIN[item['cat']])<=pub<cutoff
        assert {t for x in final['items']for t in x['topics']}==set(CAPS)
        target=WORK/'final_feeds'/(stamp+'.json.gz');atomic_json(target,final,True)
        assert current.read_bytes()in(initial_path.read_bytes(),target.read_bytes()),'Foreign feed change since initial snapshot '+stamp
        targets.append((target,current))
        candidate_archive=ROOT/'audit/news_expansion_candidates'/(stamp+'.json.gz')
        candidate_archive.parent.mkdir(parents=True,exist_ok=True);candidate_archive.write_bytes((ROOT/row['candidate_path']).read_bytes())
        rows.append({'date':stamp,'initial_feed_sha256':sha(initial_path),'final_feed_sha256':sha(target),'initial_items':len(initial['items']),
                     'added_items':len(added),'final_items':len(final['items']),'added_ids':[x['id']for x in added],
                     'candidate_sha256':row['candidate_sha256'],'candidate_archive':str(candidate_archive.relative_to(ROOT)),'new_exclusions':payload['excluded'],'all_initial_objects_unchanged':True,
                     'initial_raw_max_id':payload['initial_raw_max_id'],'all_added_ids_above_initial_raw_max':all(int(x['id'][1:])>payload['initial_raw_max_id']for x in added),
                     'cutoff_age_unique_ids_15_topics_passed':True,'final_staged_path':str(target.relative_to(ROOT))})
    # Every candidate and every initial boundary passed before any feed is replaced.
    atomic_json(ROOT/'audit/news_feed_expansion_prepared.json',{'version':VERSION2,'date_rows':rows,'status':'prepared_all_22_before_replacement'})
    for source,target in targets:
        temporary=target.with_suffix('.json.gz.tmp');temporary.write_bytes(source.read_bytes());temporary.replace(target)
    out={'status':'expanded_verified','version':VERSION2,'applied_at_utc':dt.datetime.now(UTC).isoformat(),'dates':len(rows),
         'initial_ready_records':sum(x['initial_items']for x in rows),'added_records':sum(x['added_items']for x in rows),
         'final_ready_records':sum(x['final_items']for x in rows),'new_excluded_records':staged['excluded'],
         'publication_date_unverified_exclusions':staged['publication_date_unverified_exclusions'],'original_objects_unchanged':True,'original_exclusions_not_resurrected':True,
         'missing_priority_mappings':0,'prefix_requests':prefix['prefix_requests'],'possibly_capped_prefix_requests':prefix['possibly_capped_prefix_requests'],
         'prefix_plan_sha256':sha(prefix_plan_archive),'prefix_harvest_receipt_sha256':sha(ROOT/'audit/news_prefix_expansion_harvest.json'),
         'plan_archive':'audit/news_expansion_plan.json','prefix_plan_archive':'audit/news_prefix_expansion_plan.json','failed_prefix_windows':[],
         'refinement_plan_archive':'audit/news_refinement_expansion_plan.json','refinement_plan_sha256':sha(refine_plan_archive),
         'refinement_harvest_receipt_sha256':sha(ROOT/'audit/news_refinement_expansion_harvest.json'),'failed_refinement_windows':[],
         'refinement_daily_requests':refinement['refinement_daily_requests'],'remaining_distinct_daily_caps':len(daily_caps),
         'unique_additional_request_urls':len(all_request_urls-original_urls),'unique_total_request_urls':len(all_request_urls|original_urls),
         'initial_snapshot_receipt_sha256':sha(ROOT/'audit/news_expansion_initial_snapshot.json'),
         'plan_sha256':sha(PLAN),'harvest_receipt_sha256':sha(ROOT/'audit/news_daily_expansion_harvest.json'),
         'staging_receipt_sha256':sha(ROOT/'audit/news_expansion_staging.json'),'draft_snapshots_before_apply':drafts,'date_rows':rows,
         'limits':'Initial author feeds archived byte-exact; final version appends screened own-date evidence. Daily capped requests and unarchived publisher-body vintages still limit coverage.'}
    out.update({'complete_month':True,'final_feed_sha256':{x['date']:x['final_feed_sha256']for x in rows},'initial_feed_sha256':{x['date']:x['initial_feed_sha256']for x in rows},'as_of_cutoff_prefix_windows':prefix['prefix_requests'],'original_item_objects_unchanged':True,'failed_daily_windows':[],'unresolved_priority_metadata':0})
    atomic_json(ROOT/'audit/news_feed_expansion.json',out)
    print('APPLIED',out['dates'],'feeds;',out['added_records'],'additions;',out['final_ready_records'],'total records',flush=True)
    from ready_feeds import readiness_audit
    readiness_audit()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['harvest','prefix-harvest','refine-harvest','stage','stage-partial','apply']);ap.add_argument('--workers',type=int,default=12);a=ap.parse_args()
    if a.phase=='harvest':harvest(a.workers)
    elif a.phase=='prefix-harvest':harvest_prefix(a.workers)
    elif a.phase=='refine-harvest':harvest_refinement(a.workers)
    elif a.phase=='stage-partial':stage(partial=True)
    elif a.phase=='stage':stage()
    else:apply()
if __name__=='__main__':main()
