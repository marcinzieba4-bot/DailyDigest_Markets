"""Fetch reviewed public Google News RSS jobs with the exact strict parser.

Only public news.google.com RSS search URLs are allowed. No publisher bodies,
credentials, prose, production code or deployment. Output is parsed public RSS.
"""
import argparse,base64,concurrent.futures as cf,datetime as dt,gzip,hashlib,json,sys,types,urllib.parse
from pathlib import Path
ROOT=Path(__file__).resolve().parent
# The source acquisition module imports its query catalogue, but this runner uses
# only explicit reviewed input jobs. No catalogue or report code is downloaded.
stub=types.ModuleType('topics');stub.TOPICS={};stub.EN=('en-US','US','US:en');sys.modules['topics']=stub
import fetch_news as source
ap=argparse.ArgumentParser();ap.add_argument('--part',type=int,default=0);args=ap.parse_args()
input_path=ROOT/'input.json';obj=json.loads(input_path.read_text());jobs=obj['jobs'];part_size=obj.get('part_size',750)
assert 0<len(jobs)<=15000 and 0<part_size<=1000
rows=jobs[args.part*part_size:(args.part+1)*part_size];assert rows
parsed=[]
for row in rows:
 t,q,c,loc,lo,hi=row['job'];job=(t,q,c,tuple(loc),dt.date.fromisoformat(lo),dt.date.fromisoformat(hi))
 url,_=source.url_for(q,job[4],job[5],job[3]);u=urllib.parse.urlsplit(url)
 assert url==row['request_url'] and u.scheme=='https'and u.hostname=='news.google.com'and u.path=='/rss/search'
 assert hashlib.sha256((source.VERSION+'\n'+url).encode()).hexdigest()==row['signature']
 parsed.append(job)
records={}
with cf.ThreadPoolExecutor(max_workers=4)as pool:
 for n,(row,result)in enumerate(zip(rows,pool.map(source.fetch,parsed)),1):
  records[row['signature']]=result
  if n%25==0:print(f'{n}/{len(rows)} public RSS requests complete',flush=True)
raw=json.dumps(records,ensure_ascii=False,separators=(',',':')).encode()
receipt={'purpose':'Public Google News RSS recovery through the reviewed strict parser only. No publisher bodies, credentials, report prose or deployment.','input_sha256':hashlib.sha256(input_path.read_bytes()).hexdigest(),'fetcher_sha256':hashlib.sha256((ROOT/'fetch_news.py').read_bytes()).hexdigest(),'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'part':args.part,'part_size':part_size,'records':len(records),'failures':sum(r['status']!='fetched'for r in records.values()),'parser_schema':source.PARSER_SCHEMA,'records_sha256':hashlib.sha256(raw).hexdigest()}
OUT=ROOT/'output';OUT.mkdir(exist_ok=True);(OUT/'records.json').write_bytes(raw);(OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt),flush=True)
bundle=json.dumps({'records_json':raw.decode(),'receipt_json':(OUT/'receipt.json').read_text()},ensure_ascii=False,separators=(',',':')).encode();payload=gzip.compress(bundle,mtime=0)
print('APR2025_RSS_PAYLOAD_SHA256:'+hashlib.sha256(payload).hexdigest(),flush=True)
encoded=base64.b64encode(payload).decode()
for n in range(0,len(encoded),512):print('APR2025_RSS_PAYLOAD_B64:'+encoded[n:n+512],flush=True)
print('APR2025_RSS_PAYLOAD_END',flush=True)
assert receipt['failures']==0,'Public RSS requests failed; no accepted import'
