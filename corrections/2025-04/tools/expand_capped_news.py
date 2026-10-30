"""Acquire every as-of-cutoff prefix before writing; refine all capped multi-day windows.

No append-only repair is needed: authors receive only the final screened feeds.
Each physical URL is fetched once; topic/category/locale contexts remain explicit.
Run harvest, then ready_feeds.py. An audit-bound inventory permits offline replay.
"""
from __future__ import annotations
import argparse, concurrent.futures as cf, datetime as dt, gzip, hashlib, json
from collections import Counter,defaultdict
from pathlib import Path
from fetch_news import ROOT,CACHE,VERSION,PARSER_SCHEMA,WIN,UTC,fetch,make_jobs,cutoff_prefix_jobs,url_for,collect_feed,build_feed,atomic_json
DATES=[dt.date(2025,4,n) for n in range(1,31) if dt.date(2025,4,n).weekday()<5]
PLAN=ROOT/'audit/news_query_plan.json'
COVERAGE=ROOT/'audit/news_coverage.json'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):
 raw=path.read_bytes();return json.loads(gzip.decompress(raw)if path.suffix=='.gz'else raw)
def serial(job):return [*job[:3],list(job[3]),job[4].isoformat(),job[5].isoformat()]
def job(row):return (*row[:3],tuple(row[3]),dt.date.fromisoformat(row[4]),dt.date.fromisoformat(row[5]))
def signature(job):
 url,_=url_for(job[1],job[4],job[5],job[3]);return hashlib.sha256((VERSION+'\n'+url).encode()).hexdigest(),url

def add(mapping,j,kind,parent=None):
 sig,url=signature(j)
 if url not in mapping:mapping[url]={'signature':sig,'request_url':url,'contexts':[]}
 context={'job':serial(j),'kind':kind}
 if parent:context['parent_signature']=parent
 if context not in mapping[url]['contexts']:mapping[url]['contexts'].append(context)

def harvest(workers,offline=False):
 started=dt.datetime.now(UTC).isoformat();mapping={}
 weekly=make_jobs(DATES);prefixes=cutoff_prefix_jobs(DATES)
 for j in weekly:add(mapping,j,'weekly')
 for parent,j in prefixes:add(mapping,j,'cutoff_prefix',signature(parent)[0])
 initial_count=len(mapping); rounds=[]
 for turn in range(2):
  rows=list(mapping.values());pending=[]
  for r in rows:
   path=CACHE/(r['signature']+'.json.gz')
   if not path.exists():pending.append(r);continue
   old=read(path)
   if old.get('status')!='fetched'or old.get('parser_schema')!=PARSER_SCHEMA:pending.append(r)
  print('round',turn+1,'unique requests',len(rows),'to fetch',len(pending),'workers',workers,flush=True)
  if offline and pending:
   atomic_json(PLAN,{'version':VERSION,'status':'planned_missing','dates':[d.isoformat()for d in DATES],'weekly_contexts':len(weekly),'prefix_contexts':len(prefixes),'initial_unique_requests':initial_count,'requests':list(mapping.values()),'rounds':rounds})
   target=ROOT/'work/news_missing_queries.json'
   atomic_json(target,{'jobs':[{'signature':r['signature'],'request_url':r['request_url'],'job':r['contexts'][0]['job']}for r in pending],'part_size':750})
   print('OFFLINE pending public requests',len(pending),'saved',target,flush=True);return None
  with cf.ThreadPoolExecutor(max_workers=workers)as pool:
   for n,(row,batch)in enumerate(zip(pending,pool.map(fetch,[job(r['contexts'][0]['job'])for r in pending])),1):
    if n%100==0 or batch['status']!='fetched':print(n,'/',len(pending),batch['status'],row['contexts'][0]['job'][4:6],flush=True)
  failed=[r['signature']for r in rows if read(CACHE/(r['signature']+'.json.gz')).get('status')!='fetched' or(not read(CACHE/(r['signature']+'.json.gz')).get('raw_count',0)and not read(CACHE/(r['signature']+'.json.gz')).get('response_format_verified'))]
  rounds.append({'round':turn+1,'unique_requests':len(rows),'new_requests':len(pending),'failed_requests':len(failed)})
  atomic_json(PLAN,{'version':VERSION,'dates':[d.isoformat()for d in DATES],'weekly_contexts':len(weekly),'prefix_contexts':len(prefixes),'initial_unique_requests':initial_count,'requests':list(mapping.values()),'rounds':rounds})
  if failed:raise SystemExit(str(len(failed))+' required requests failed; resume harvest')
  if turn==0:
   for row in rows:
    batch=read(CACHE/(row['signature']+'.json.gz'))
    if not batch.get('possibly_capped'):continue
    for context in row['contexts'][:]:
     j=job(context['job']);lo,hi=j[4:]
     if(hi-lo).days<=1:continue
     for n in range((hi-lo).days):
      day=lo+dt.timedelta(days=n);add(mapping,(*j[:4],day,day+dt.timedelta(days=1)),'daily_refinement',row['signature'])
  else:break
 # All added requests are daily, hence no further splittable caps can be introduced.
 inventory=[];dailycaps=[];multi_caps=[]
 for row in mapping.values():
  path=CACHE/(row['signature']+'.json.gz');batch=read(path)
  entry={**row,'cache_path':str(path.relative_to(ROOT)),'cache_sha256':sha(path),'raw_sha256':batch['raw_sha256'],'raw_count':batch['raw_count'],'eligible_items':len(batch['items']),'status':batch['status'],'parser_schema':batch.get('parser_schema'),'possibly_capped':batch.get('possibly_capped',False),'lower_date':batch['lower_date'],'upper_date_exclusive':batch['upper_date_exclusive']}
  inventory.append(entry)
  if entry['possibly_capped']:
   (dailycaps if(dt.date.fromisoformat(entry['upper_date_exclusive'])-dt.date.fromisoformat(entry['lower_date'])).days==1 else multi_caps).append(entry['signature'])
 plan={'version':VERSION,'dates':[d.isoformat()for d in DATES],'weekly_contexts':len(weekly),'prefix_contexts':len(prefixes),'initial_unique_requests':initial_count,'requests':inventory,'rounds':rounds}
 atomic_json(PLAN,plan)
 batches=load_harvest(plan);date_rows=[]
 for d in DATES:
  receipt=build_feed(d,batches);path=ROOT/'work/unreviewed_feeds'/(d.isoformat()+'.json.gz')
  receipt['raw_feed_path']=str(path.relative_to(ROOT));receipt['raw_feed_sha256']=sha(path)
  used=[r['signature']for r in inventory if any(c['job'][4]<d.isoformat()and c['job'][5]<=d.isoformat()and c['job'][5]>(d-dt.timedelta(days=WIN[c['job'][2]])).isoformat()for c in r['contexts'])]
  receipt['eligible_query_signatures']=sorted(used);receipt['eligible_queries']=len(used);date_rows.append(receipt)
  print(d,receipt['items'],'own-date rows',len(used),'query URLs',flush=True)
 proof={'version':VERSION,'status':'acquired_verified','started_at_utc':started,'finished_at_utc':dt.datetime.now(UTC).isoformat(),'report_dates':len(DATES),'query_catalog_contexts':sum(len(x)for x in __import__('topics').TOPICS.values()),'weekly_contexts':len(weekly),'cutoff_prefix_contexts':len(prefixes),'unique_query_urls':len(inventory),'daily_refinement_urls':len(inventory)-initial_count,'failed_requests':0,'remaining_daily_caps':len(dailycaps),'remaining_daily_cap_signatures':dailycaps,'refined_multiday_cap_signatures':multi_caps,'parser_schema':PARSER_SCHEMA,'query_plan':'audit/news_query_plan.json','query_plan_sha256':sha(PLAN),'acquisition_tool_sha256':{str(p.relative_to(ROOT)):sha(p)for p in [ROOT/'tools/fetch_news.py',ROOT/'tools/expand_capped_news.py',ROOT/'tools/topics.py',ROOT/'tools/ready_feeds.py']},'helper_tool_sha256':{str(p.relative_to(ROOT)):sha(p)for p in [ROOT/'tools/digest.py',ROOT/'posthoc/resolve_news_url.py']},'dates':date_rows,'own_date_records':sum(r['items']for r in date_rows),'rules':['All catalogue weekly windows and every straddled report-cutoff prefix requested.','Every capped multi-day response receives daily child requests in every retained context.','Only response windows ending at or before consuming report cutoff are merged.','RSS timestamps strictly before 00:00UTC report cutoff and within category age.'],'limits':['Google historical search selection/indexing and daily response caps prevent exhaustive coverage.','Contemporary original RSS server responses and publisher article-body vintages are not archived; these are retrieval-time historical search results.','Canonical URL dates and release guards provide conservative selected screening; every narrative claim requires its own-date editorial review.']}
 proof['transport_tool_sha256']={'tools/import_public_rss.py':sha(ROOT/'tools/import_public_rss.py')}
 proof['public_rss_ingestions']=[{'path':str(p.relative_to(ROOT)),'sha256':sha(p),'records':read(p)['records'],'head':read(p)['head']}for p in sorted((ROOT/'audit').glob('news_public_rss_ingestion_*.json'))]
 atomic_json(COVERAGE,proof);return proof

def load_harvest(plan=None):
 plan=plan or read(PLAN);batches=[]
 for row in plan['requests']:
  path=ROOT/row.get('cache_path',str((CACHE/(row['signature']+'.json.gz')).relative_to(ROOT)));batch=read(path)
  if row.get('cache_sha256'):assert sha(path)==row['cache_sha256']
  assert batch['status']=='fetched'and batch.get('parser_schema')==PARSER_SCHEMA
  contexts=set()
  for c in row['contexts']:
   j=job(c['job']);context=(j[0],j[1],j[2],j[3],j[4],j[5])
   if context in contexts:continue
   contexts.add(context)
   batches.append({**batch,'topic':j[0],'query':j[1],'category':j[2],'locale':list(j[3]),'lower_date':j[4].isoformat(),'upper_date_exclusive':j[5].isoformat()})
 return batches

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--workers',type=int,default=12);ap.add_argument('--replay',action='store_true');ap.add_argument('--plan-offline',action='store_true');args=ap.parse_args()
 if args.replay:
  batches=load_harvest()
  for d in DATES:
   items,_,failed=collect_feed(d,batches,asof_queries=True);raw=read(ROOT/'work/unreviewed_feeds'/(d.isoformat()+'.json.gz'))
   for n,item in enumerate(items,1):item['id']=f'n{n:04d}'
   assert not failed and items==raw['items'],d
  print('offline replay passed',len(DATES),'dates')
 else:harvest(args.workers,offline=args.plan_offline)
if __name__=='__main__':main()
