"""Freeze one edition only after every qualifying global-plan request/refinement exists.
The final full-month replay must yield byte-identical ready feeds. No partial source set.
"""
from __future__ import annotations
import argparse,concurrent.futures as cf,datetime as dt,json,gzip,hashlib
from fetch_news import ROOT,CACHE,WIN,fetch,atomic_json,build_feed
from expand_capped_news import DATES,make_jobs,cutoff_prefix_jobs,add,signature,read,job,serial,load_harvest
from ready_feeds import screen

def relevant(j,d):return j[4]<d and j[5]<=d and j[5]>d-dt.timedelta(days=WIN[j[2]])
def freeze(d,workers):
 mapping={}
 for j in make_jobs(DATES):add(mapping,j,'weekly')
 for parent,j in cutoff_prefix_jobs(DATES):add(mapping,j,'cutoff_prefix',signature(parent)[0])
 required={u:{**r,'contexts':[c for c in r['contexts'] if relevant(job(c['job']),d)]}for u,r in mapping.items()}
 required={u:r for u,r in required.items()if r['contexts']}
 missing=[r for r in required.values() if not(CACHE/(r['signature']+'.json.gz')).exists()]
 if missing:
  print(d,'NOT READY',len(missing),'required initial URLs absent',flush=True);return False
 for row in list(required.values()):
  batch=read(CACHE/(row['signature']+'.json.gz'))
  if batch.get('status')!='fetched':raise ValueError('required initial request failed '+row['signature'])
  if not batch.get('possibly_capped'):continue
  for context in row['contexts'][:]:
   j=job(context['job']);lo,hi=j[4:]
   if(hi-lo).days<=1:continue
   for n in range((hi-lo).days):
    day=lo+dt.timedelta(days=n);add(required,(*j[:4],day,day+dt.timedelta(days=1)),'daily_refinement',row['signature'])
 missing=[r for r in required.values()if not(CACHE/(r['signature']+'.json.gz')).exists()]
 print(d,'required URLs',len(required),'refinements to fetch',len(missing),flush=True)
 with cf.ThreadPoolExecutor(max_workers=workers)as pool:
  for r,b in zip(missing,pool.map(fetch,[job(r['contexts'][0]['job'])for r in missing])):
   if b['status']!='fetched':raise ValueError('required refinement failed')
 rows=[]
 for row in required.values():
  path=CACHE/(row['signature']+'.json.gz');b=read(path)
  assert b['status']=='fetched'
  rows.append({**row,'cache_path':str(path.relative_to(ROOT)),'cache_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'raw_count':b['raw_count'],'possibly_capped':b.get('possibly_capped',False)})
 plan={'version':'nov-2024-priority-complete-v1','date':d.isoformat(),'requests':rows,'scope':'Every qualifying full-month initial URL and daily cap refinement is complete; later report-cutoff URLs cannot contribute to this edition.'}
 atomic_json(ROOT/'audit'/('news_query_plan_priority_'+d.isoformat()+'.json'),plan)
 receipt=build_feed(d,load_harvest(plan));ready=screen(d)
 atomic_json(ROOT/'audit'/('news_frozen_'+d.isoformat()+'.json'),{'date':d.isoformat(),'feed_sha256':ready['ready_sha256'],'query_plan':'audit/news_query_plan_priority_'+d.isoformat()+'.json','request_count':len(rows),'status':'frozen_complete_own_date','full_month_replay_pending':True})
 print(d,'READY',receipt['items'],'raw',ready['ready_items'],'screened',ready['ready_sha256'],flush=True);return True
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('date');ap.add_argument('--workers',type=int,default=8);a=ap.parse_args();raise SystemExit(0 if freeze(dt.date.fromisoformat(a.date),a.workers)else 2)
