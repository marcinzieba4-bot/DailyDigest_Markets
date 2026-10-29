"""Recover public canonical URL metadata only; never fetch publisher bodies."""
import concurrent.futures as cf
import datetime as dt
import hashlib
import json
import re
import time
import urllib.parse
from pathlib import Path
from resolve_news_url import resolve

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'output';OUT.mkdir(exist_ok=True)

def job(url):
    error=''
    for attempt in range(6):
        try:
            canonical=resolve(url)
            match=re.search(r'(\d{4}-\d{2}-\d{2})/?$',urllib.parse.urlparse(canonical).path)
            return url,{'canonical_url':canonical,'canonical_date':match.group(1) if match else None,
                        'observed_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'publisher_body_fetched':False,
                        'transport':'isolated_github_hosted_public_metadata_recovery'}
        except Exception as exc:
            error=f'{type(exc).__name__}: {exc}'
            if attempt<5:time.sleep(min(2**attempt,15))
    return url,{'error':error,'observed_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
                'publisher_body_fetched':False,'transport':'isolated_github_hosted_public_metadata_recovery'}

source=ROOT/'input.json';obj=json.loads(source.read_text());urls=sorted(set(obj['urls']))
assert all(urllib.parse.urlparse(u).hostname=='news.google.com' for u in urls)
records={}
with cf.ThreadPoolExecutor(max_workers=10) as pool:
    for i,(url,result) in enumerate(pool.map(job,urls),1):
        records[url]=result
        if i%25==0:print(f'{i}/{len(urls)} metadata requests complete',flush=True)
target=OUT/'canonical_metadata.json';target.write_text(json.dumps(records,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
receipt={'purpose':'Public Google News canonical publisher URL metadata only. No publisher bodies, AWS credentials or production report invocation.',
         'input_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'resolver_sha256':hashlib.sha256((ROOT/'resolve_news_url.py').read_bytes()).hexdigest(),
         'output_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'records':len(records),'failures':sum(bool(r.get('error')) for r in records.values()),
         'original_body_vintage_proven':False}
(OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)

# Hash-bound public payload in connector-readable logs when artifact CDN is unreachable.
import base64, gzip
bundle=json.dumps({'canonical_metadata_json':target.read_text(),'receipt_json':(OUT/'receipt.json').read_text()},ensure_ascii=False,separators=(',',':')).encode()
payload=gzip.compress(bundle,mtime=0)
print('AUG2025_PAYLOAD_SHA256:'+hashlib.sha256(payload).hexdigest(),flush=True)
encoded=base64.b64encode(payload).decode()
for i in range(0,len(encoded),512):print('AUG2025_PAYLOAD_B64:'+encoded[i:i+512],flush=True)
print('AUG2025_PAYLOAD_END',flush=True)
