from pathlib import Path
import concurrent.futures as cf, datetime as dt, importlib.util, json,re,time,urllib.parse
root=Path(__file__).resolve().parent.parent
sp=importlib.util.spec_from_file_location('resolver',root/'posthoc/resolve_news_url.py');resolver=importlib.util.module_from_spec(sp);sp.loader.exec_module(resolver)
urls=json.loads((root/'cited_urls.json').read_text());out={}
def one(url):
 for attempt in range(4):
  try:
   value=resolver.resolve(url);m=re.search(r'(\d{4}-\d{2}-\d{2})/?$',urllib.parse.urlparse(value).path)
   return url,{'canonical_url':value,'canonical_date':m.group(1) if m else None,'observed_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'publisher_body_fetched':False,'execution':'isolated GitHub public metadata job'}
  except Exception as error:
   if attempt==3:return url,{'error':type(error).__name__+': '+str(error),'publisher_body_fetched':False}
   time.sleep(2**attempt)
with cf.ThreadPoolExecutor(max_workers=4) as pool:
 for n,(url,value) in enumerate(pool.map(one,urls),1):
  out[url]=value
  print(n,'of',len(urls),'metadata records',flush=True)
(root/'cited_url_results.json').write_text(json.dumps(out,indent=2))
if any(x.get('error') for x in out.values()):raise SystemExit('Some metadata requests failed; results retained for retry')
