"""Independent raw-XML replay and explicit append-only revision for an own-card-driven retail coverage gap.
The complete accepted base set is preserved byte-for-byte; existing IDs/items never change.
"""
from pathlib import Path
import json,gzip,hashlib,datetime as dt,email.utils,xml.etree.ElementTree as ET,re,urllib.parse,sys
R=Path('/workspace/work/august2024'); A=R/'audit/source_amendments';UTC=dt.timezone.utc
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
enc=lambda j:gzip.compress(json.dumps(j,ensure_ascii=False,separators=(',',':')).encode(),mtime=0)
fields=['published_at','src','source_url','title','url']
trusted={'Reuters','CNBC','AP News','BBC','NBC News','Starbucks','WSJ','CBS News','PR Newswire','Fortune','Bloomberg.com',"Investor's Business Daily",'The Washington Post','The New York Times','Business Insider','Investopedia','CBC','Fast Company','The Seattle Times','GeekWire','MarketWatch','Morningstar','The Economist','CFO Dive','Restaurant Business','The Independent'}
relevant=re.compile(r'CEO|Niccol|Narasimhan|chief executive|executive|Starboard|shares|stock|activist|departure|Elliott|leader|leadership|retirement|What.s Wrong|Trading Day',re.I)
rolling=re.compile(r'\b(?:live updates|live blog|as it happened|stock market today|markets today)\b',re.I)
errors=[];checks=0

def ck(ok,msg):
 global checks
 checks+=1
 if not ok:errors.append(msg)
def atomic(path,data):
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.revision.tmp');tmp.write_bytes(data);tmp.replace(path)
def js(path,obj):atomic(path,(json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode())
def key(i):return tuple(i[k] for k in fields)

m=read(R/'source_supplements/retail_coverage_manifest.json');base_accept=read(R/'audit/independent_source_review.json');base_freeze=read(R/'audit/source_freeze.json');market=read(R/'audit/independent_market_review.json')
ck(base_accept['passed'] and not base_accept['errors'],'Accepted base infrastructure')
ck(not (A/'amendment.json').exists(),'Revision has not already been committed')
ck(m['unique_requests']==30 and m['failed_requests']==0 and m['remaining_daily_caps']==0,'Complete uncapped scoped requests')
ck(sha(R/m['script_path'])==m['script_sha256'],'Saved acquisition tool identity')
prepared=[];request_count=0
for row in m['dates']:
 d=row['date'];cut=dt.datetime.fromisoformat(d).replace(tzinfo=UTC);payload=read(R/row['path']);ck(sha(R/row['path'])==row['sha256'],d+' research payload hash')
 ck(payload['report_date']==d and payload['cutoff_utc']==d+'T00:00:00Z' and payload['category']=='news' and payload['window_days']==7,d+' payload cutoff/category')
 batches={b['signature']:b for b in payload['batches']};physical={};merged={}
 for req in row['requests']:
  request_count+=1;cache=read(R/req['cache_path']);sig=req['signature'];ck(sha(R/req['cache_path'])==req['cache_sha256'],d+' parsed cache hash')
  ck(cache==batches[sig],d+' payload batch equals exact physical cache')
  ck(cache['upper_date_exclusive']==d and cache['lower_date']==(cut-dt.timedelta(days=7)).date().isoformat(),d+' exact own request window')
  query=cache['query']+' after:'+str((cut-dt.timedelta(days=8)).date())+' before:'+d
  expected='https://news.google.com/rss/search?'+urllib.parse.urlencode({'q':query,'hl':'en-US','gl':'US','ceid':'US:en'})
  ck(cache['request_url']==req['request_url']==expected,d+' URL rebuilt independently')
  ck(sig==hashlib.sha256(('aug-2024-own-cutoff-retail-supplement-v1\n'+expected).encode()).hexdigest(),d+' physical signature')
  compressed=(R/req['raw_response_path']).read_bytes();raw=gzip.decompress(compressed)
  ck(hashlib.sha256(compressed).hexdigest()==req['raw_response_compressed_sha256']==cache['raw_response_compressed_sha256'],d+' raw compressed hash')
  ck(hashlib.sha256(raw).hexdigest()==req['raw_sha256']==cache['raw_sha256'],d+' raw XML hash')
  root=ET.fromstring(raw);ck(root.tag=='rss' and root.find('channel') is not None,d+' RSS format')
  nodes=root.findall('.//item');parsed=[]
  for node in nodes:
   pub=email.utils.parsedate_to_datetime(node.findtext('pubDate')).astimezone(UTC);title=(node.findtext('title') or '').strip();url=(node.findtext('link') or '').strip();s=node.find('source')
   if not cache['lower_date']<=pub.date().isoformat()<d or not title or not url.startswith('https://') or rolling.search(title):continue
   parsed.append({'published_at':pub.isoformat(),'src':(s.text or '') if s is not None else '', 'source_url':s.get('url','') if s is not None else '', 'title':title,'url':url})
  ck(parsed==cache['items'],d+' complete independent item reparse')
  ck(len(nodes)==cache['raw_count']==req['raw_count']<100 and not cache['possibly_capped'] and cache['status']=='fetched',d+' no failed/capped query')
  physical[sig]=parsed
 for item in payload['items']:
  pub=dt.datetime.fromisoformat(item['published_at']);ck(cut-dt.timedelta(days=7)<=pub<cut,d+' headline seven-day cutoff')
  actual=[sig for sig,items in physical.items() if any(key(x)==key(item) for x in items)]
  ck(set(actual)==set(item['query_signatures']) and bool(actual),d+' exact own physical provenance')
  ck(all(s in row['request_signatures'] for s in actual),d+' no later-cutoff source')
 base_path=R/'feeds'/f'{d}.json.gz';base=read(base_path);record=next(x for x in base_accept['dates'] if x['date']==d)
 ck(sha(base_path)==record['feed_sha256'],d+' accepted original feed bytes')
 known={key(x) for x in base['items']};selected=[];rejected=[]
 for i in payload['items']:
  if i['src'] not in trusted or not re.search(r'Starbucks|Chipotle|Niccol',i['title'],re.I) or not relevant.search(i['title']):
   rejected.append({'title':i['title'],'src':i['src'],'reason':'Outside the targeted financial/leadership coverage or preferred attribution set'});continue
  if key(i) in known:continue
  selected.append(i)
 selected.sort(key=lambda x:(x['published_at'],x['src'],x['title'],x['url']))
 additions=[]
 for n,i in enumerate(selected,900001):
  additions.append({**{k:i[k] for k in fields},'cat':'news','topics':['retail','sectors'],'q':i['queries'][0],'queries':i['queries'],'lang':'en-US','id':f'n{n}','supplement_signatures':i['query_signatures'],'source_revision':'retail-coverage-v2'})
 ck(not ({x['id'] for x in additions}&{x['id'] for x in base['items']}),d+' stable noncolliding new IDs')
 result={**base,'items':base['items']+additions,'source_revision':2,'source_revision_note':'Accepted base is preserved unchanged; own-cutoff retail coverage additions carry dedicated physical provenance and stable new IDs.'}
 ck(result['items'][:len(base['items'])]==base['items'],d+' base item order/content preserved')
 prepared.append({'date':d,'base_path':base_path,'base_bytes':base_path.read_bytes(),'base':base,'result':result,'result_bytes':enc(result),'additions':additions,'rejected':rejected,'payload_sha256':row['sha256']})
if errors:
 print(json.dumps({'passed':False,'checks':checks,'errors':errors},indent=2));raise SystemExit(1)
# Stage all physical candidates and verify every byte before any active writer projection changes.
for x in prepared:
 p=A/'staged'/f'{x["date"]}.json.gz';atomic(p,x['result_bytes']);ck(p.read_bytes()==x['result_bytes'],'Staged projection byte equality')
ck(not errors,'All candidates verified')
if '--commit' not in sys.argv:
 print(json.dumps({'stage_only':True,'checks':checks,'errors':errors,'dates':[{'date':x['date'],'base_items':len(x['base']['items']),'added_items':len(x['additions'])} for x in prepared]},indent=2));raise SystemExit(0)
# Preserve exact base receipts and feeds before active revision; do not re-run the closed base acquisition workflow.
for name in ['independent_source_review.json','source_freeze.json','independent_market_review.json']:
 p=A/('base_'+name);ck(not p.exists(),'Base receipt backup must be new');atomic(p,(R/'audit'/name).read_bytes())
for x in prepared:atomic(A/'base_feeds'/f'{x["date"]}.json.gz',x['base_bytes'])
for x in prepared:atomic(x['base_path'],x['result_bytes'])
rows=[]
for x in prepared:
 d=x['date'];fp=x['base_path'];ck(sha(fp)==hashlib.sha256(x['result_bytes']).hexdigest(),d+' final projection body hash')
 rows.append({'date':d,'base_feed_path':str((A/'base_feeds'/f'{d}.json.gz').relative_to(R)),'base_feed_sha256':hashlib.sha256(x['base_bytes']).hexdigest(),'feed_sha256':sha(fp),'base_items_unchanged':True,'base_items':len(x['base']['items']),'new_items':x['additions'],'new_item_count':len(x['additions']),'research_payload_sha256':x['payload_sha256'],'omitted_candidates':x['rejected']})
 if d in base_accept['known_semantic_exclusions']['by_date']:base_accept['known_semantic_exclusions']['by_date'][d]['feed_sha256']=sha(fp)
 if d in base_accept['known_timing_exclusions']['by_date']:base_accept['known_timing_exclusions']['by_date'][d]['feed_sha256']=sha(fp)
 rec=next(v for v in base_accept['dates'] if v['date']==d);rec['base_feed_sha256']=rec['feed_sha256'];rec['feed_sha256']=sha(fp);rec['supplement_items']=len(x['additions']);rec['ready_items']+=len(x['additions'])
if errors:
 raise RuntimeError('Revision body verification failed: '+repr(errors))
base_freeze['source_revision']=2;base_freeze['base_freeze_path']='audit/source_amendments/base_source_freeze.json';base_freeze['base_freeze_sha256']=sha(A/'base_source_freeze.json');base_freeze['append_only_revision']='audit/source_amendments/amendment.json';base_freeze['current_feed_sha256']={v['date']:sha(R/'feeds'/f'{v["date"]}.json.gz') for v in base_accept['dates']};base_freeze['frozen_feeds_immutable']=True;base_freeze['immutability_scope']='The accepted v1 base is immutable and physically preserved; v2 is a separately staged, verified append-only projection. Existing records/IDs and all earlier source evidence remain unchanged.'
js(R/'audit/source_freeze.json',base_freeze)
proof={'status':'accepted_append_only_revision','passed':not errors,'checks':checks,'errors':errors,'request_count':request_count,'coverage_manifest_sha256':sha(R/'source_supplements/retail_coverage_manifest.json'),'reviewer_tool_sha256':sha(Path(__file__)),'base_acceptance_sha256':sha(A/'base_independent_source_review.json'),'base_freeze_sha256':sha(A/'base_source_freeze.json'),'current_source_freeze_sha256':sha(R/'audit/source_freeze.json'),'dates':rows,'reason':'An Aug14 own-card +24.50% Starbucks/-7.50% Chipotle move exposed a missing explanatory headline. Neutral company queries ended at each independent own cutoff; no later query or remembered cause supplies an earlier report fact.','limits':['Headline records only; original publisher vintages/article bodies unverified.','Targeted financial coverage is screened, not a claim to exhaust all web coverage.','No change to historical prices, existing feed IDs, or previously cited source records.']}
js(A/'amendment.json',proof)
base_accept['source_revision']=2;base_accept['base_acceptance_path']='audit/source_amendments/base_independent_source_review.json';base_accept['base_acceptance_sha256']=sha(A/'base_independent_source_review.json');base_accept['append_only_revision_sha256']=sha(A/'amendment.json');base_accept['source_freeze_sha256']=sha(R/'audit/source_freeze.json');base_accept['supplement_checks']=checks;base_accept['supplement_request_count']=request_count;base_accept['scope']+=' Controlled revision v2 adds independently reparsed own-cutoff retail coverage; immutable base proofs and existing IDs/items are preserved.';js(R/'audit/independent_source_review.json',base_accept)
market['base_acceptance_path']='audit/source_amendments/base_independent_market_review.json';market['source_freeze_sha256']=sha(R/'audit/source_freeze.json');market['source_revision_binding_note']='Only news projection added; all card hashes and validated market inputs remain unchanged.';js(R/'audit/independent_market_review.json',market)
print(json.dumps({'passed':proof['passed'],'checks':checks,'new_records':sum(x['new_item_count'] for x in rows),'dates':[{'date':x['date'],'added':x['new_item_count']} for x in rows]},indent=2))
