"""Materialize early feeds once all their shared query windows are cached."""
import datetime as dt, gzip, hashlib, json
from fetch_news import ROOT,CACHE,VERSION,WIN,make_jobs,url_for,build_feed,atomic_json

dates=[dt.date(2025,10,d) for d in range(1,32) if dt.date(2025,10,d).weekday()<5]
jobs=make_jobs(dates); cached={};missing=[]
for job in jobs:
    topic,q,cat,loc,lo,hi=job
    url,_=url_for(q,lo,hi,loc)
    sig=hashlib.sha256((VERSION+'\n'+url).encode()).hexdigest()
    path=CACHE/(sig+'.json.gz')
    if path.exists():cached[sig]=json.loads(gzip.decompress(path.read_bytes()))
    else:missing.append(job)
for date in dates:
    needed=[j for j in missing if j[4]<date and j[5]>date-dt.timedelta(days=WIN[j[2]])]
    if needed:print(date,'waiting',len(needed),'query windows');continue
    audit=build_feed(date,list(cached.values()))
    atomic_json(ROOT/'checks'/('news_'+date.isoformat()+'.json'),audit)
    print(date,'READY',audit['items'],'headlines',audit['failed_query_windows'],'failed query windows')
