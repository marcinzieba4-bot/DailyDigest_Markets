"""Read-only targeted historical retail headline recovery; strict own-date eligibility."""
import concurrent.futures as cf,datetime as dt,gzip,hashlib,importlib.util,json,sys
from pathlib import Path
r=Path(__file__).resolve().parent;sys.path.insert(0,str(r.parent/'2025-09/tools'))
sp=importlib.util.spec_from_file_location('news',r.parent/'2025-09/tools/fetch_news.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);m.CACHE=r/'work/news_cache';m.VERSION='retail-revision-weekly-2026-v1'
queries=['("Stocktwits" OR "Reddit") stock sentiment','"retail investors" stocks','"meme stock"','"retail traders" options']
lo=dt.date(2025,12,25);end=dt.date(2026,10,29);jobs=[]
while lo<end:
 hi=min(lo+dt.timedelta(days=7),end)
 for q in queries:jobs.append(('retail',q,'news',('en-US','US','US:en'),lo,hi))
 lo=hi
out=[]
with cf.ThreadPoolExecutor(max_workers=4) as ex:
 for i,x in enumerate(ex.map(lambda j:m.fetch(j,attempts=3,backoff_cap=4),jobs),1):
  out.append(x)
  if i%25==0:print('Retail source windows',i,'of',len(jobs),'failed',sum(x['status']!='fetched' for x in out),flush=True)
dates=[Path(x['Key']).stem for x in json.loads((r/'audit/published_inventory.json').read_text()) if Path(x['Key']).stem>='2026-01-01' and not (r.parent/Path(x['Key']).stem[:7]/'specs'/(Path(x['Key']).stem+'.json')).exists()]
ready=[]
for d in dates:
 cutoff=dt.datetime.fromisoformat(d).replace(tzinfo=dt.timezone.utc);seen={}
 for b in out:
  for e in b['items']:
   t=dt.datetime.fromisoformat(e['published_at'])
   if cutoff-dt.timedelta(days=7)<=t<cutoff:
    key=(e['title'],e['src'],e['published_at']);seen[key]=e
 items=sorted(seen.values(),key=lambda e:(e['published_at'],e['title']))
 for i,e in enumerate(items,1):e['id']=f'r{i:04d}'
 p=r/'work/retail_feeds'/f'{d}.json.gz';p.parent.mkdir(exist_ok=True);p.write_bytes(gzip.compress(json.dumps({'date':d,'cutoff_utc':cutoff.isoformat(),'rule':'Strict midnight cutoff, earlier than legacy intraday generation;7day news; headline facts only. Original article vintages unverified.','items':items},ensure_ascii=False).encode(),mtime=0));ready.append({'date':d,'items':len(items),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
(r/'audit/retail_source_fetch.json').write_text(json.dumps({'query_windows':len(out),'failed_windows':sum(x['status']!='fetched' for x in out),'possibly_capped_windows':sum(x.get('possibly_capped',False) for x in out),'feeds':ready,'raw_headline_records':sum(x['items'] for x in ready),'original_body_vintages_proven':False},indent=2));print('Retail feeds complete',len(ready),'failed windows',sum(x['status']!='fetched' for x in out),flush=True)
