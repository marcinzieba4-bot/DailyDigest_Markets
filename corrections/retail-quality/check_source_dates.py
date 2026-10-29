"""Canonical-date rejection check for retrospective retail Reuters citations.

Only public Google News URL metadata is queried. No article bodies are fetched;
URL dates do not prove original article vintages or intraday availability.
"""
from pathlib import Path
import concurrent.futures as cf
import datetime as dt
import gzip
import hashlib
import importlib.util
import json
import re
import time
import urllib.parse

ROOT=Path(__file__).resolve().parent
MONTHS=['2025-09','2025-10','2025-11','2025-12','2026-02']


def main():
    resolver_path=ROOT.parent/'2025-09/posthoc/resolve_news_url.py'
    sp=importlib.util.spec_from_file_location('news_resolver',resolver_path)
    resolver=importlib.util.module_from_spec(sp);sp.loader.exec_module(resolver)
    cache_path=ROOT/'audit/canonical_retail_urls.json'
    cache=json.loads(cache_path.read_text()) if cache_path.exists() else {}
    refs={};hashes={}
    for month in MONTHS:
        folder=ROOT.parent/month
        for name in ['canonical_reuters_urls.json','canonical_cited_urls.json']:
            p=folder/'audit'/name
            if p.exists():
                for url,row in json.loads(p.read_text()).items():
                    if url not in cache or (cache[url].get('error') and not row.get('error')):cache[url]=row
        for p in sorted((folder/'specs').glob('*.json')):
            spec=json.loads(p.read_text());hashes[p.stem]=hashlib.sha256(p.read_bytes()).hexdigest()
            ids=set(re.findall(r'\[\[(n\d+)\]\]',json.dumps(spec['retail'])))
            feed=json.load(gzip.open(folder/'feeds'/f'{p.stem}.json.gz','rt'))
            for e in feed['items']:
                if e['id'] in ids and ('reuters' in e['src'].lower() or e['title'].lower().endswith(' - reuters')):
                    refs.setdefault(e['url'],[]).append({'date':p.stem,'id':e['id'],'title':e['title'],'indexed_at':e['published_at']})
    need=[u for u in refs if u not in cache or cache[u].get('error') or not cache[u].get('canonical_date')]
    print(len(refs),'cited retail Reuters URLs;',len(need),'new metadata lookups',flush=True)
    def fetch(url):
        last_error=''
        last_type=''
        for i in range(3):
            try:
                canonical=resolver.resolve(url);m=re.search(r'(\d{4}-\d{2}-\d{2})/?$',urllib.parse.urlparse(canonical).path)
                return url,{'canonical_url':canonical,'canonical_date':m.group(1) if m else None,
                    'observed_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'publisher_body_fetched':False}
            except Exception as error:
                last_error=str(error)[:200]
                last_type=type(error).__name__
                if i<2:time.sleep(i+1)
        return url,{'error_type':last_type,'error':last_error,'publisher_body_fetched':False}
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        for i,(u,row) in enumerate(ex.map(fetch,need),1):
            cache[u]=row
            if i%20==0:
                cache_path.write_text(json.dumps(cache,indent=2));print('Metadata',i,'of',len(need),flush=True)
    cache_path.write_text(json.dumps(cache,indent=2))
    failed=[u for u in refs if cache[u].get('error') or not cache[u].get('canonical_date')]
    conflicts=[{**e,**cache[u]} for u,entries in refs.items() for e in entries if cache[u].get('canonical_date','')>=e['date']]
    out={'purpose':__doc__,'unique_cited_urls':len(refs),'spec_sha256':hashes,'lookup_failures':len(failed),
         'failed_urls':failed,'conflicts':conflicts,'passed':not failed and not conflicts,
         'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat()}
    (ROOT/'audit/retail_canonical_dates.json').write_text(json.dumps(out,indent=2))
    print('Canonical retail date audit:',len(failed),'lookup failures;',len(conflicts),'date conflicts',flush=True)
    if not out['passed']:raise SystemExit(1)


if __name__=='__main__':main()
