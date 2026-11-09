"""Start the fixed July base plan; no feeds or freeze destinations are written."""
import concurrent.futures as cf,datetime as dt,hashlib,json,sys
from pathlib import Path
R=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(R/'tools'))
from fetch_news import ROOT,VERSION,PARSER_SCHEMA,TOPICS,make_jobs,cutoff_prefix_jobs,fetch,url_for,atomic_json,UTC
DATES=[dt.date(2024,7,n)for n in range(1,32)if dt.date(2024,7,n).weekday()<5]
def serial(j):return [*j[:3],list(j[3]),j[4].isoformat(),j[5].isoformat()]
weekly=make_jobs(DATES);prefix=cutoff_prefix_jobs(DATES);mapping={}
for kind,entries in [('weekly',[(None,j)for j in weekly]),('cutoff_prefix',prefix)]:
 for parent,j in entries:
  url,_=url_for(j[1],j[4],j[5],j[3]);sig=hashlib.sha256((VERSION+'\n'+url).encode()).hexdigest();row=mapping.setdefault(url,dict(signature=sig,request_url=url,contexts=[]));context=dict(job=serial(j),kind=kind)
  if parent:
   pu,_=url_for(parent[1],parent[4],parent[5],parent[3]);context['parent_signature']=hashlib.sha256((VERSION+'\n'+pu).encode()).hexdigest()
  if context not in row['contexts']:row['contexts'].append(context)
rows=sorted(mapping.values(),key=lambda x:(x['contexts'][0]['job'][5],x['contexts'][0]['job'][4],x['request_url']))
declaration=ROOT/'audit_work/news_catalogue_declaration.json'
if not declaration.exists():atomic_json(declaration,dict(declared_at_utc=dt.datetime.now(UTC).isoformat(),version=VERSION,parser_schema=PARSER_SCHEMA,dates=[d.isoformat()for d in DATES],catalogue_contexts=sum(map(len,TOPICS.values())),topics_sha256=hashlib.sha256((ROOT/'tools/topics.py').read_bytes()).hexdigest(),fetch_tool_sha256=hashlib.sha256((ROOT/'tools/fetch_news.py').read_bytes()).hexdigest(),basis='Fixed broad company and sector catalogue declared before July physical acquisition; no month outcome/mover/attention list used.',topic_catalogue=TOPICS))
atomic_json(ROOT/'audit/news_base_query_plan.json',dict(status='declared_before_base_harvest',version=VERSION,dates=[d.isoformat()for d in DATES],weekly_contexts=len(weekly),prefix_contexts=len(prefix),requests=rows))
print('BASE',len(rows),'unique URLs;',sum(map(len,TOPICS.values())),'catalogue contexts; workers 16',flush=True)
jobs=[]
for row in rows:
 j=row['contexts'][0]['job'];jobs.append((*j[:3],tuple(j[3]),dt.date.fromisoformat(j[4]),dt.date.fromisoformat(j[5])))
failed=[]
with cf.ThreadPoolExecutor(max_workers=16)as pool:
 for i,b in enumerate(pool.map(fetch,jobs),1):
  if b['status']!='fetched':failed.append(b['signature'])
  if i%100==0 or b['status']!='fetched':print(i,'/',len(jobs),b['status'],b['upper_date_exclusive'],flush=True)
atomic_json(ROOT/'audit/news_base_harvest_receipt.json',dict(version=VERSION,completed_at_utc=dt.datetime.now(UTC).isoformat(),requests=len(rows),failed_signatures=failed,feeds_written=False,rule='Base responses only; capped-window refinements and July semantic screening remain mandatory.'))
print('BASE COMPLETE',len(jobs),'failed',len(failed),'NO FEEDS FROZEN',flush=True)
raise SystemExit(bool(failed))
