"""July own-cutoff acquisition with daily and complementary capped-response refinements.

All physical URLs and their contexts are retained. Capped multi-day windows split
by day; capped days receive BOTH neutral term and -term branches, recursively,
with finite fail-closed limits. Historical Google search is discovery, not an
assertion of exhaustive contemporary reporting or publisher article vintages.
"""
from __future__ import annotations
import argparse,concurrent.futures as cf,datetime as dt,gzip,hashlib,json,re
from collections import Counter
from fetch_news import ROOT,CACHE,VERSION,PARSER_SCHEMA,WIN,UTC,fetch,make_jobs,cutoff_prefix_jobs,url_for,collect_feed,build_feed,atomic_json
DATES=[dt.date(2024,7,n)for n in range(1,32)if dt.date(2024,7,n).weekday()<5]
PLAN=ROOT/'audit/news_query_plan.json';COVERAGE=ROOT/'audit/news_coverage.json'
MAX_PARTITION_DEPTH=24;MAX_PHYSICAL_REQUESTS=75000
NEUTRAL_TERMS=['Reuters','Bloomberg','CNBC','Yahoo','MarketWatch','Investing','Financial Times','Wall Street Journal','Associated Press','BBC','Guardian','Forbes','Barron','investors','company','shares','stocks','market','economy','bank','China','Japan','US','Europe','Poland','Australia','Canada','UK','Fed','rates','inflation','earnings','revenue','sales','profit','AI','technology','energy','oil','gold','bitcoin','quarter','ETF','Nasdaq','New York','London','Tokyo','Beijing','growth','business','finance','prices','trading','capital','retail','services','manufacturing','demand','supply','investment','dollar','yen','euro','credit','bonds','funds','consumer','production','employment','policy']
_READ_CACHE={};_SHA_CACHE={}
def sha(path):
 if not path.exists():return'not-applicable-july-2024'
 st=path.stat();key=(str(path),st.st_mtime_ns,st.st_size)
 if key not in _SHA_CACHE:_SHA_CACHE[key]=hashlib.sha256(path.read_bytes()).hexdigest()
 return _SHA_CACHE[key]
def read(path):
 if path.parent==CACHE:
  st=path.stat();key=(str(path),st.st_mtime_ns,st.st_size)
  if key in _READ_CACHE:return _READ_CACHE[key]
 raw=path.read_bytes();result=json.loads(gzip.decompress(raw)if path.suffix=='.gz'else raw)
 if path.parent==CACHE:_READ_CACHE[key]=result
 return result
def serial(j):return[*j[:3],list(j[3]),j[4].isoformat(),j[5].isoformat()]
def job(row):return(*row[:3],tuple(row[3]),dt.date.fromisoformat(row[4]),dt.date.fromisoformat(row[5]))
def signature(j):
 url,_=url_for(j[1],j[4],j[5],j[3]);return hashlib.sha256((VERSION+'\n'+url).encode()).hexdigest(),url

def add(mapping,j,kind,parent=None,**extra):
 sig,url=signature(j)
 if url not in mapping:mapping[url]={'signature':sig,'request_url':url,'contexts':[]}
 context={'job':serial(j),'kind':kind,**extra}
 if parent:context['parent_signature']=parent
 if context not in mapping[url]['contexts']:mapping[url]['contexts'].append(context)
 if len(mapping)>MAX_PHYSICAL_REQUESTS:raise RuntimeError('Finite physical-request limit reached; no freeze permitted')
 return sig

def initial_plan():
 mapping={};weekly=make_jobs(DATES);prefixes=cutoff_prefix_jobs(DATES)
 for j in weekly:add(mapping,j,'weekly')
 for parent,j in prefixes:add(mapping,j,'cutoff_prefix',signature(parent)[0])
 return mapping,weekly,prefixes

def choose_term(batch,context):
 query=context['job'][1];used=context.get('partition_terms',[])
 available=[t for t in NEUTRAL_TERMS if t not in used and not re.search(r'\b'+re.escape(t)+r'\b',query,re.I)]
 if not available:raise RuntimeError('No neutral partition term remains; no freeze permitted')
 titles=[x['title']for x in batch['items']];total=max(len(titles),1)
 counts={t:sum(bool(re.search(r'\b'+re.escape(t)+r'\b',title,re.I))for title in titles)for t in available}
 term=min(available,key=lambda t:(abs(counts[t]/total-.5),NEUTRAL_TERMS.index(t)))
 return term,dict(method='balanced exact-headline count among fixed neutral terms; both complementary searches required',title_matches=counts[term],eligible_titles=len(titles))

def expand_caps(mapping,cutoff,expanded):
 changed=False
 for row in list(mapping.values()):
  if row['contexts'][0]['job'][5]>cutoff:continue
  path=CACHE/(row['signature']+'.json.gz')
  if not path.exists():continue
  batch=read(path)
  if batch.get('status')!='fetched'or not batch.get('possibly_capped'):continue
  for context in row['contexts'][:]:
   token=json.dumps([row['signature'],context],sort_keys=True,separators=(',',':'))
   if token in expanded:continue
   j=job(context['job']);lo,hi=j[4:];bound=context.get('refinement_root_upper_date_exclusive',j[5].isoformat());children=[]
   if(hi-lo).days>1:
    strategy='daily_split'
    for n in range((hi-lo).days):
     day=lo+dt.timedelta(days=n)
     children.append(add(mapping,(*j[:4],day,day+dt.timedelta(days=1)),'daily_refinement',row['signature'],refinement_root_upper_date_exclusive=bound,catalogue_query=context.get('catalogue_query',j[1])))
   else:
    strategy='complementary_term_partition';depth=context.get('partition_depth',0)
    if depth>=MAX_PARTITION_DEPTH:raise RuntimeError('Finite daily-cap partition limit reached: '+row['signature'])
    term,basis=choose_term(batch,context)
    for side in['include','exclude']:
     childquery='('+j[1]+') '+(''if side=='include'else'-')+'"'+term+'"'
     child=(*j[:1],childquery,*j[2:])
     children.append(add(mapping,child,'term_refinement',row['signature'],refinement_root_upper_date_exclusive=bound,catalogue_query=context.get('catalogue_query',j[1]),partition_depth=depth+1,partition_terms=context.get('partition_terms',[])+[term],partition={'term':term,'side':side,'basis':basis}))
   row.setdefault('cap_resolutions',[]).append(dict(context_sha256=hashlib.sha256(json.dumps(context,sort_keys=True,separators=(',',':')).encode()).hexdigest(),strategy=strategy,children=children,root_upper_date_exclusive=bound))
   expanded.add(token);changed=True
 return changed

def inventory(mapping,*,complete=False):
 rows=[]
 for row in mapping.values():
  path=CACHE/(row['signature']+'.json.gz')
  if not path.exists():
   if complete:raise AssertionError('Missing physical request '+row['signature'])
   rows.append(row);continue
  b=read(path)
  if complete:assert b['status']=='fetched'and b.get('response_format_verified')and b.get('parser_schema')==PARSER_SCHEMA,row['signature']
  rows.append({**row,'cache_path':str(path.relative_to(ROOT)),'cache_sha256':sha(path),'raw_sha256':b.get('raw_sha256'),'raw_response_path':b.get('raw_response_path'),'raw_response_compressed_sha256':b.get('raw_response_compressed_sha256'),'raw_count':b.get('raw_count'),'eligible_items':len(b.get('items',[])),'status':b['status'],'parser_schema':b.get('parser_schema'),'possibly_capped':b.get('possibly_capped',False),'lower_date':b['lower_date'],'upper_date_exclusive':b['upper_date_exclusive']})
 return rows

def load_harvest(plan=None,*,through=None):
 plan=plan or read(PLAN);batches=[]
 for row in plan['requests']:
  if through and row['contexts'][0]['job'][5]>through:continue
  path=ROOT/row.get('cache_path',str((CACHE/(row['signature']+'.json.gz')).relative_to(ROOT)));batch=read(path)
  if row.get('cache_sha256'):assert sha(path)==row['cache_sha256']
  assert batch['status']=='fetched'and batch.get('parser_schema')==PARSER_SCHEMA
  for c in row['contexts']:
   j=job(c['job']);bound=c.get('refinement_root_upper_date_exclusive',j[5].isoformat())
   batches.append({**batch,'topic':j[0],'query':j[1],'category':j[2],'locale':list(j[3]),'lower_date':j[4].isoformat(),'upper_date_exclusive':j[5].isoformat(),'parent_upper_date_exclusive':bound if c['kind']in{'daily_refinement','term_refinement'}else j[5].isoformat()})
 return batches

def harvest(workers,offline=False,through_date=None):
 acceptance=ROOT/'audit/independent_source_review.json'
 if acceptance.exists()and read(acceptance).get('passed'):raise RuntimeError('Accepted source set is immutable; use --replay')
 started=dt.datetime.now(UTC).isoformat();mapping,weekly,prefixes=initial_plan();initial_count=len(mapping);rounds=[];expanded=set()
 def save_plan(status,complete=False):
  p=dict(version=VERSION,status=status,dates=[d.isoformat()for d in DATES],weekly_contexts=len(weekly),prefix_contexts=len(prefixes),initial_unique_requests=initial_count,requests=inventory(mapping,complete=complete),rounds=rounds,refinement_policy=dict(multiday='all daily children',daily='both neutral term and -term branches recursively',maximum_partition_depth=MAX_PARTITION_DEPTH,maximum_physical_requests=MAX_PHYSICAL_REQUESTS,neutral_terms=NEUTRAL_TERMS),catalogue_declaration='audit_work/news_catalogue_declaration.json')
  atomic_json(PLAN,p);return p
 for d in DATES:
  if through_date and d.isoformat()>through_date:break
  cutoff=d.isoformat();turn=0
  while True:
   turn+=1;required=[r for r in mapping.values()if r['contexts'][0]['job'][5]<=cutoff];pending=[]
   for r in required:
    path=CACHE/(r['signature']+'.json.gz');old=read(path)if path.exists()else{}
    if old.get('status')!='fetched'or old.get('parser_schema')!=PARSER_SCHEMA:pending.append(r)
   pending.sort(key=lambda r:(r['contexts'][0]['job'][5],r['contexts'][0]['job'][4],r['request_url']))
   print(cutoff,'round',turn,'known URLs',len(mapping),'required',len(required),'to fetch',len(pending),flush=True)
   if offline and pending:
    save_plan('planned_missing');atomic_json(ROOT/'work/news_missing_queries.json',{'jobs':[{'signature':r['signature'],'request_url':r['request_url'],'job':r['contexts'][0]['job']}for r in pending]});return None
   with cf.ThreadPoolExecutor(max_workers=workers)as pool:
    for n,b in enumerate(pool.map(fetch,[job(r['contexts'][0]['job'])for r in pending]),1):
     if n%100==0 or b['status']!='fetched':print(cutoff,n,'/',len(pending),b['status'],flush=True)
   failed=[r['signature']for r in required if read(CACHE/(r['signature']+'.json.gz')).get('status')!='fetched']
   rounds.append(dict(cutoff=cutoff,round=turn,known_requests=len(mapping),required_requests=len(required),new_requests=len(pending),failed_requests=len(failed)))
   if failed:save_plan('failed_required_requests');raise RuntimeError(str(len(failed))+' unresolved required requests; no freeze permitted')
   changed=expand_caps(mapping,cutoff,expanded)
   if not changed:break
  plan=save_plan('acquiring_complete_cutoffs_through_'+cutoff);batches=load_harvest(plan,through=cutoff);receipt=build_feed(d,batches,persist=False)
  stage=ROOT/'work/source_candidates_partial';atomic_json(stage/'unreviewed_feeds'/(cutoff+'.json.gz'),receipt.pop('_payload'),True);atomic_json(stage/'news_provenance'/(cutoff+'.json.gz'),receipt.pop('_ledger'),True)
  atomic_json(stage/'receipts'/(cutoff+'.json'),{**receipt,'status':'raw_cutoff_queries_complete_semantic_screen_pending_do_not_author','query_plan_sha256':sha(PLAN)})
  print(cutoff,'RAW STAGED',receipt['items'],'records; NO AUTHOR-READY FREEZE',flush=True)
 if through_date and through_date<DATES[-1].isoformat():
  save_plan('partial_raw_staged_through_'+through_date);print('PARTIAL RAW STAGING COMPLETE; FULL PLAN AND SEMANTIC SCREEN STILL REQUIRED',flush=True);return None
 plan=save_plan('all_requests_acquired_caps_resolved',complete=True);batches=load_harvest(plan);date_rows=[]
 for d in DATES:
  receipt=build_feed(d,batches,persist=False);path=ROOT/'work/acquisition_feeds'/(d.isoformat()+'.json.gz');atomic_json(path,receipt.pop('_payload'),True);receipt.pop('_ledger');receipt.update(raw_feed_path=str(path.relative_to(ROOT)),raw_feed_sha256=sha(path));date_rows.append(receipt)
 capped=[r for r in plan['requests']if r['possibly_capped']];terminal=[r['signature']for r in capped if not r.get('cap_resolutions')];assert not terminal,terminal
 proof=dict(version=VERSION,status='acquired_verified_semantic_screen_pending',started_at_utc=started,finished_at_utc=dt.datetime.now(UTC).isoformat(),report_dates=len(DATES),query_catalog_contexts=sum(map(len,__import__('topics').TOPICS.values())),weekly_contexts=len(weekly),cutoff_prefix_contexts=len(prefixes),unique_query_urls=len(plan['requests']),refinement_urls=len(plan['requests'])-initial_count,daily_refinement_urls=sum(any(c['kind']=='daily_refinement'for c in r['contexts'])for r in plan['requests']),complementary_term_refinement_urls=sum(any(c['kind']=='term_refinement'for c in r['contexts'])for r in plan['requests']),capped_requests=len(capped),unresolved_capped_requests=0,remaining_daily_caps=0,remaining_daily_cap_signatures=[],failed_requests=0,parser_schema=PARSER_SCHEMA,query_plan='audit/news_query_plan.json',query_plan_sha256=sha(PLAN),physical_request_ledger='audit/news_physical_requests.jsonl',physical_request_ledger_sha256=sha(ROOT/'audit/news_physical_requests.jsonl'),catalogue_declaration='audit_work/news_catalogue_declaration.json',catalogue_declaration_sha256=sha(ROOT/'audit_work/news_catalogue_declaration.json'),dates=date_rows,own_date_records=sum(r['items']for r in date_rows),rules=['All fixed catalogue weekly windows and every straddled own-cutoff prefix were physically requested.','Every capped multi-day context receives all daily children; every capped day receives both complementary neutral-term branches until uncapped leaves.','Only requests ending by the consuming cutoff and refinement roots ending by that cutoff contribute.','RSS timestamps are strictly before 00:00 UTC and within semantic category age; July release screening is still required.'],limits=['Google historical search selection/indexing prevents exhaustive coverage of all reporting even after observed response caps are refined.','Responses are retrieval-time historical search results; original contemporary RSS and unrevised publisher article vintages are not asserted.','No publisher article body is read. Exact headline meaning and release timing still require editorial review.'])
 proof['acquisition_tool_sha256']={str(p.relative_to(ROOT)):sha(p)for p in[ROOT/'tools/fetch_news.py',ROOT/'tools/expand_capped_news.py',ROOT/'tools/topics.py',ROOT/'tools/ready_feeds.py']};atomic_json(COVERAGE,proof);print('ALL 23 RAW ACQUIRED, CAPS RESOLVED; SEMANTIC SCREEN/FREEZE PENDING',flush=True);return proof

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--workers',type=int,default=16);ap.add_argument('--replay',action='store_true');ap.add_argument('--plan-offline',action='store_true');ap.add_argument('--through-date');args=ap.parse_args()
 if args.replay:
  batches=load_harvest()
  for d in DATES:
   items,_,failed=collect_feed(d,batches,asof_queries=True);raw=read(ROOT/'work/acquisition_feeds'/(d.isoformat()+'.json.gz'))
   for n,item in enumerate(items,1):item['id']=f'n{n:04d}'
   assert not failed and items==raw['items'],d
  print('offline own-cutoff replay passed',len(DATES),'dates')
 else:harvest(args.workers,offline=args.plan_offline,through_date=args.through_date)
if __name__=='__main__':main()
