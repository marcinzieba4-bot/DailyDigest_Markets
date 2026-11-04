"""Independent physical XML reparse, request-plan replay and source-ID reconstruction.
No owner fetch/merge/build/screen functions are imported or invoked.
"""
from pathlib import Path
import json,gzip,hashlib,datetime as dt,email.utils,xml.etree.ElementTree as ET
import re,ast,sys,urllib.parse
from collections import Counter
R=Path('/workspace/work/sep2024/repo/corrections/2024-09')
sys.path.insert(0,str(R/'tools'))
from topics import TOPICS,EN
dates=[dt.date(2024,9,n) for n in range(1,31) if dt.date(2024,9,n).weekday()<5]
WIN={'news':7,'result':14,'monthly':35};UTC=dt.timezone.utc
VERSION='sep-2024-cutoff-prefix-v1'
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bytesof(j):return gzip.compress(json.dumps(j,ensure_ascii=False,separators=(',',':')).encode(),mtime=0)
STAGE_ONLY='--stage-only' in sys.argv
errors=[];checks=Counter()
def ck(v,m,g='structure'):
 checks[g]+=1
 if not v:errors.append(m)
def patterns(file):
 # Parse only declarative regex/literal guard data, never owner functions.
 tree=ast.parse((R/'tools'/file).read_text());out={};constants={}
 def literal(node,env):
  if isinstance(node,ast.Constant):return node.value
  if isinstance(node,ast.Name) and node.id in env:return env[node.id]
  if isinstance(node,(ast.List,ast.Tuple)):return [literal(n,env) for n in node.elts] if isinstance(node,ast.List) else tuple(literal(n,env)for n in node.elts)
  if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Add):return literal(node.left,env)+literal(node.right,env)
  raise ValueError('Nondeclarative guard expression '+ast.dump(node))
 def append(node,env):
  if isinstance(node,ast.Expr) and isinstance(node.value,ast.Call):
   call=node.value
   if isinstance(call.func,ast.Attribute) and isinstance(call.func.value,ast.Name) and call.func.value.id=='RELEASE_GUARDS' and call.func.attr in ('append','extend'):
    if call.func.attr=='append':out['RELEASE_GUARDS'].append(literal(call.args[0],env))
    else:out['RELEASE_GUARDS'].extend(literal(call.args[0],env))
 for node in tree.body:
  if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
   name=node.targets[0].id
   if isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Attribute) and node.value.func.attr=='compile':out[name]=re.compile(literal(node.value.args[0],constants),re.I)
   else:
    try:constants[name]=literal(node.value,constants)
    except ValueError:continue
    if name=='RELEASE_GUARDS':out[name]=list(constants[name])
  elif isinstance(node,ast.Expr):append(node,constants)
  elif isinstance(node,ast.For) and isinstance(node.target,ast.Tuple):
   try:values=literal(node.iter,constants)
   except ValueError:continue
   for valueset in values:
    env={**constants,**{n.id:v for n,v in zip(node.target.elts,valueset)}}
    for statement in node.body:append(statement,env)
 return out
fp=patterns('fetch_news.py');sp=patterns('ready_feeds.py')
def semantic(title,category):
 if fp['PREVIEW'].search(title):return 'news'
 if category=='result':return 'result' if fp['RESULT_TEXT'].search(title) else 'news'
 if category=='monthly' and fp['CORPORATE'].search(title):return 'result' if fp['RESULT_TEXT'].search(title) else 'news'
 if category=='monthly' and fp['CALENDAR_PREVIEW'].search(title):return 'news'
 if category=='monthly' and (fp['TRANSIENT_MARKET'].search(title) or fp['CORPORATE_EVENT'].search(title)):return 'news'
 if category=='monthly' and not fp['MACRO_MONTHLY'].search(title):return 'result' if fp['RESULT_TEXT'].search(title) else 'news'
 return category
def guard(title,published,stamp):
 normal=sp['NEUTRALISE'].sub('',title)
 for label,eligible,start,pattern in sp['RELEASE_GUARDS']:
  if stamp<eligible and start<=published<stamp and re.search(pattern,title,re.I):
   residual=sp['FORWARD_ACTION'].sub('',normal)
   if sp['COMPLETED'].search(residual):return label
   if any(p.search(normal) for p in (sp['EXPLICIT_PREVIEW'],fp['PREVIEW'],sp['FORWARD'])):continue
   return label
 return None
def sigurl(j):
 topic,q,cat,loc,lo,hi=j
 query=f'{q} after:{(dt.date.fromisoformat(lo)-dt.timedelta(days=1)).isoformat()} before:{hi}'
 url='https://news.google.com/rss/search?'+urllib.parse.urlencode({'q':query,'hl':loc[0],'gl':loc[1],'ceid':loc[2]})
 return hashlib.sha256((VERSION+'\n'+url).encode()).hexdigest(),url
mapping={}
def add(j,kind,parent=None):
 sig,url=sigurl(j)
 if url not in mapping:mapping[url]={'signature':sig,'request_url':url,'contexts':[]}
 c={'job':j,'kind':kind}
 if parent:c['parent_signature']=parent
 if c not in mapping[url]['contexts']:mapping[url]['contexts'].append(c)
weekly=[]
for topic,queries in TOPICS.items():
 for entry in queries:
  q,category=entry[:2];loc=list(entry[2] if len(entry)>2 else EN)
  lo=min(dates)-dt.timedelta(days=WIN[category])
  while lo<max(dates):
   hi=min(lo+dt.timedelta(days=7),max(dates))
   weekly.append([topic,q,category,loc,lo.isoformat(),hi.isoformat()]);lo=hi
weekly.sort(key=lambda j:(j[4],j[5],j[0],j[1]))
for j in weekly:add(j,'weekly')
for d in dates:
 for j in weekly:
  if j[4]<d.isoformat()<j[5]:add([*j[:5],d.isoformat()],'cutoff_prefix',sigurl(j)[0])
plan=read(R/'audit/news_query_plan.json');coverage=read(R/'audit/news_coverage.json')
rows=plan['requests'];physical={};xmlbytes=0;parsed_items=0
for row in rows:
 p=R/row['cache_path'];j=read(p);physical[row['signature']]=j
 ck(sha(p)==row['cache_sha256'],row['signature']+' parsed cachehash','raw_transport')
 ck(j['signature']==row['signature'] and j['request_url']==row['request_url'],row['signature']+' physical identity','raw_transport')
 rp=R/j['raw_response_path'];compressed=rp.read_bytes();raw=gzip.decompress(compressed);xmlbytes+=len(raw)
 ck(hashlib.sha256(compressed).hexdigest()==j['raw_response_compressed_sha256']==row['raw_response_compressed_sha256'],row['signature']+' raw compressedhash','raw_transport')
 ck(hashlib.sha256(raw).hexdigest()==j['raw_sha256']==row['raw_sha256'],row['signature']+' rawXMLhash','raw_transport')
 root=ET.fromstring(raw);ck(root.tag=='rss' and root.find('channel') is not None,row['signature']+' RSSformat','xml_reparse')
 nodes=root.findall('.//item');items=[];discarded=Counter()
 for node in nodes:
  try:
   pdt=email.utils.parsedate_to_datetime(node.findtext('pubDate'))
   if pdt.tzinfo is None:raise ValueError('naive publicationtime')
   pub=pdt.astimezone(UTC)
  except Exception:discarded['malformed_timestamp']+=1;continue
  if not j['lower_date']<=pub.date().isoformat()<j['upper_date_exclusive']:discarded['outside_query_window']+=1;continue
  title=(node.findtext('title') or '').strip();url=(node.findtext('link') or '').strip();source=node.find('source')
  if not title or not url.startswith('https://'):discarded['missing_title_or_https_url']+=1;continue
  if fp['ROLLING'].search(title):discarded['rolling_headline']+=1;continue
  items.append({'published_at':pub.isoformat(),'src':(source.text or '') if source is not None else '', 'source_url':source.get('url','') if source is not None else '', 'title':title,'url':url})
 parsed_items+=len(items)
 ck(items==j['items'],row['signature']+' independent parsed items','xml_reparse')
 ck(dict(discarded)==j['discarded'] and len(nodes)==j['raw_count']==row['raw_count'],row['signature']+' raw/discardcounts','xml_reparse')
 ck(j['status']=='fetched' and j['response_format_verified'] and j['parser_schema']=='rss-root-channel-aware-timestamp-v1',row['signature']+' fetched parserstatus','raw_transport')
 ck(bool(j['possibly_capped'])==(len(nodes)>=100),row['signature']+' capclassification','xml_reparse')
ck(set((R/'cache/news').glob('*.json.gz'))=={R/r['cache_path'] for r in rows},'Every physical parsed cache is in the audited plan','physical_inventory')
ck(set((R/'cache/rss_raw').glob('*.xml.gz'))=={R/r['raw_response_path'] for r in rows},'Every physical RSS XML is in the audited plan','physical_inventory')
inventory={'status':'all_physical_source_files_reparsed','query_plan_sha256':sha(R/'audit/news_query_plan.json'),'files':[{'signature':r['signature'],'parsed_cache_path':r['cache_path'],'parsed_cache_sha256':sha(R/r['cache_path']),'raw_xml_path':r['raw_response_path'],'raw_xml_compressed_sha256':sha(R/r['raw_response_path']),'raw_xml_uncompressed_sha256':r['raw_sha256']}for r in rows]}
(Path(__file__).parent/'physical_source_inventory.json').write_text(json.dumps(inventory,indent=2)+'\n')
for row in list(mapping.values()):
 batch=physical[row['signature']]
 if not batch['possibly_capped']:continue
 for c in row['contexts'][:]:
  j=c['job'];lo,hi=map(dt.date.fromisoformat,j[4:6])
  if (hi-lo).days<=1:continue
  for n in range((hi-lo).days):
   day=lo+dt.timedelta(days=n);add([*j[:4],day.isoformat(),(day+dt.timedelta(days=1)).isoformat()],'daily_refinement',row['signature'])
ck(len(mapping)==len(rows),'Independent physical request count','plan')
ck(list(mapping)==[r['request_url'] for r in rows],'Physical request order','plan')
ck(all(mapping[r['request_url']]['contexts']==r['contexts'] for r in rows),'All weekly/prefix/refinement contexts exactly reconstructed','plan')
ck(all(sigurl(c['job'])==(r['signature'],r['request_url']) for r in rows for c in r['contexts']),'Every physical signature/URL matches context','plan')
parents={r['signature']:r['contexts'][0]['job'][5] for r in rows}
caps=[r['signature'] for r in rows if physical[r['signature']]['possibly_capped'] and (dt.date.fromisoformat(physical[r['signature']]['upper_date_exclusive'])-dt.date.fromisoformat(physical[r['signature']]['lower_date'])).days==1]
ck(len(caps)==coverage['remaining_daily_caps'] and set(caps)==set(coverage['remaining_daily_cap_signatures']),'Residual dailycaps documented','plan')
ck(coverage['failed_requests']==0 and all(j['status']=='fetched' for j in physical.values()),'Zero failed physicalrequests','plan')
ck(sha(R/'audit/news_query_plan.json')==coverage['query_plan_sha256'],'Coverage binds physicalplan','plan')
dateproof=[];old_monthly=[]
for date in dates:
 stamp=date.isoformat();cutoff=dt.datetime.combine(date,dt.time(),UTC);merged={};provenance={};qualifying=set();contexts=set();prefixfuture=0;dailyexcluded=0
 for row in rows:
  batch=physical[row['signature']]
  for c in row['contexts']:
   j=c['job'];topic,query,category,loc,lo,hi=j
   unique=(topic,query,category,tuple(loc),lo,hi,c.get('parent_signature'))
   if (row['signature'],unique) in contexts:continue
   contexts.add((row['signature'],unique))
   if c['kind']=='daily_refinement' and parents[c['parent_signature']]>stamp:dailyexcluded+=1;continue
   if hi>stamp or hi<=(date-dt.timedelta(days=WIN[category])).isoformat() or lo>=stamp:continue
   if c['kind']=='cutoff_prefix' and parents[c['parent_signature']]>stamp:prefixfuture+=1
   qualifying.add(row['signature'])
   for item in batch['items']:
    pub=dt.datetime.fromisoformat(item['published_at']);cat=semantic(item['title'],category)
    if not cutoff-dt.timedelta(days=WIN[cat])<=pub<cutoff:continue
    key=(item['title'].casefold(),item['src'].casefold(),item['published_at'])
    provenance.setdefault(key,set()).add(row['signature'])
    if key not in merged:merged[key]={**item,'cat':cat,'topics':[topic],'q':query,'queries':[query],'lang':loc[0]}
    else:
     old=merged[key]
     if topic not in old['topics']:old['topics'].append(topic)
     if query not in old['queries']:old['queries'].append(query)
     if WIN[cat]<WIN[old['cat']]:old['cat']=cat
 items=[v for v in merged.values() if cutoff-dt.timedelta(days=WIN[v['cat']])<=dt.datetime.fromisoformat(v['published_at'])<cutoff]
 items.sort(key=lambda x:(x['topics'][0],x['published_at'],x['title'],x['src'],x['url']))
 for n,item in enumerate(items,1):item['id']=f'n{n:04d}'
 ledger={x['id']:sorted(provenance[(x['title'].casefold(),x['src'].casefold(),x['published_at'])]) for x in items}
 rawpath=R/('work/source_candidates/unreviewed_feeds' if STAGE_ONLY else 'work/unreviewed_feeds')/f'{stamp}.json.gz';rawfeed=read(rawpath)
 ck(rawfeed['items']==items,stamp+' full independent own-cutoff merge/IDs','merge')
 ck(rawfeed['date']==stamp and dt.datetime.fromisoformat(rawfeed['cutoff_utc'])==cutoff and not rawfeed['fails'],stamp+' own-date identity/failures','merge')
 lp=R/('work/source_candidates/news_provenance' if STAGE_ONLY else 'audit/news_provenance')/f'{stamp}.json.gz';ck(read(lp)['records']==ledger,stamp+' every physical provenance signature','merge')
 screened=[];excluded=[]
 for item in items:
  hit=guard(item['title'],item['published_at'][:10],stamp)
  if hit:excluded.append({'id':item['id'],'published_at':item['published_at'],'src':item['src'],'title':item['title'],'guard':hit})
  else:screened.append(item)
 feedpath=R/('work/source_candidates/feeds' if STAGE_ONLY else 'feeds')/f'{stamp}.json.gz';feed=read(feedpath)
 ck(feed['items']==screened,stamp+' release screening replay','screening')
 if not STAGE_ONLY:
  receiptpath=R/'audit'/f'news_ready_{stamp}.json';ready=read(receiptpath);frozen=read(R/'audit'/f'news_frozen_{stamp}.json')
  ck(ready['excluded']==excluded,stamp+' exclusion receipt replay','screening')
  ck(sha(feedpath)==ready['ready_sha256']==frozen['feed_sha256'],stamp+' ready/freeze bytehash','freeze')
  ck(sha(rawpath)==ready['unreviewed_sha256'],stamp+' raw receipt bytehash','freeze')
  ck(frozen['full_month_replay_verified'] and not frozen['full_month_replay_pending'],stamp+' complete full-month replay','freeze')
  ck(sha(feedpath)==sha(R/'work/source_candidates/feeds'/f'{stamp}.json.gz'),stamp+' staged ready identical','freeze')
  ck(sha(rawpath)==sha(R/'work/source_candidates/unreviewed_feeds'/f'{stamp}.json.gz'),stamp+' staged raw identical','freeze')
  ck(sha(lp)==sha(R/'work/source_candidates/news_provenance'/f'{stamp}.json.gz'),stamp+' staged provenance identical','freeze')
 for item in screened:
  pub=dt.datetime.fromisoformat(item['published_at']);ck(cutoff-dt.timedelta(days=WIN[item['cat']])<=pub<cutoff,stamp+' '+item['id']+' exact7/14/35 age','age')
  if item['cat']=='monthly' and pub<cutoff-dt.timedelta(days=7):old_monthly.append({'date':stamp,'id':item['id'],'title':item['title'],'src':item['src'],'published_at':item['published_at']})
 dateproof.append({'date':stamp,'raw_items':len(items),'ready_items':len(screened),'excluded':len(excluded),'feed_sha256':sha(feedpath),'raw_sha256':sha(rawpath),'provenance_sha256':sha(lp),'ready_receipt_sha256':sha(receiptpath) if not STAGE_ONLY else None,'qualifying_physical_requests':len(qualifying),'own_cutoff_prefix_contexts_whose_parent_ends_later':prefixfuture,'later_parent_daily_contexts_excluded':dailyexcluded})
 print(stamp,len(items),len(screened),'replayed',flush=True)
manifest=read(R/'work/source_candidates/comparison_manifest.json')
ck(manifest['status']=='all_21_compared_before_destination_write' and len(manifest['dates'])==21,'All21 staged comparisonmanifest','staging')
ck([r['date'] for r in manifest['dates']]==[d.isoformat() for d in dates],'Candidate manifest exact21dates','staging')
for row in manifest['dates']:
 stamp=row['date']
 ck(row['all_stage_bytes_verified'],'Candidate physical byte comparison '+stamp,'staging')
 ck(row['raw_candidate_sha256']==sha(R/'work/source_candidates/unreviewed_feeds'/f'{stamp}.json.gz'),'Candidate raw manifest hash '+stamp,'staging')
 ck(row['ready_candidate_sha256']==sha(R/'work/source_candidates/feeds'/f'{stamp}.json.gz'),'Candidate ready manifest hash '+stamp,'staging')
 ck(row['provenance_candidate_sha256']==sha(R/'work/source_candidates/news_provenance'/f'{stamp}.json.gz'),'Candidate provenance manifest hash '+stamp,'staging')
ck(manifest['query_plan_sha256']==sha(R/'audit/news_query_plan.json'),'Candidate exact queryplan hash','staging')
if not STAGE_ONLY:
 freeze=read(R/'audit/source_freeze.json')
 ck(freeze['status']=='all_21_ready' and len(freeze['dates'])==21 and freeze['frozen_feeds_immutable'],'All21 freeze status','freeze')
 ck(freeze['query_plan_sha256']==sha(R/'audit/news_query_plan.json') and freeze['coverage_sha256']==sha(R/'audit/news_coverage.json'),'Global source-freeze bindings','freeze')
 ck(freeze['candidate_manifest_sha256']==sha(R/'work/source_candidates/comparison_manifest.json'),'Candidate manifest binding','freeze')
# Regression scenarios are synthetic guard tests, not acquired story evidence.
guardcases=[
 ('Broadcom beats quarterly earnings estimates as Adobe is set to report','2024-09-04','2024-09-05',True),
 ('Broadcom will beat quarterly earnings estimates','2024-09-04','2024-09-05',False),
 ('US August payrolls rise, could boost equities','2024-09-05','2024-09-06',True),
 ('US August payrolls expected to rise','2024-09-05','2024-09-06',False),
 ('Fed cuts rates, ahead of the Bank of Japan decision','2024-09-17','2024-09-18',True),
 ('Fed expected to cut rates as China unveils stimulus','2024-09-23','2024-09-24',True),
 ('China September manufacturing PMI expands, could boost equities','2024-09-29','2024-09-30',True),
 ('China September PMI expected to expand','2024-09-29','2024-09-30',False),
 ('Japan August consumer prices rose more than expected','2024-09-19','2024-09-20',False),
 ('Japan August consumer prices rose more than expected','2024-09-18','2024-09-19',True),
 ('Japan August industrial production falls','2024-09-29','2024-09-30',False),
 ('Micron expected to report earnings as Costco beats quarterly estimates','2024-09-25','2024-09-26',True),
 ('China September PMI expands, ahead of BoJ decision','2024-09-29','2024-09-30',True),
]
for title,p,d,e in guardcases:ck(bool(guard(title,p,d))==e,'Guard regression '+title,'screening')
out={'status':('staged_infrastructure_verified' if STAGE_ONLY else 'accepted_for_authoring_with_semantic_exclusions') if not errors else 'failed','passed':not errors,'infrastructure_status':'accepted' if not errors else 'failed','semantic_status':'requires_own_claim_review','scope':'All21 September source acquisition/identity/immutability infrastructure only. Every physical raw RSS XML independently reparsed; catalogue jobs, capped daily refinements, own-cutoff merges, IDs and physical provenance independently reconstructed. Screening/semantic regex policy inspected and separately applied, not independently known article publication dates. No report narrative or retail-selection approval is conferred.','checks':sum(checks.values()),'checks_by_scope':dict(checks),'errors':errors,'dates':dateproof,'physical_requests':len(rows),'raw_xml_uncompressed_bytes':xmlbytes,'independently_reparsed_items':parsed_items,'failed_queries':sum(j['status']!='fetched' for j in physical.values()),'physical_source_inventory_sha256':sha(Path(__file__).parent/'physical_source_inventory.json'),'remaining_daily_caps':len(caps),'remaining_daily_cap_signatures':caps,'query_plan_sha256':sha(R/'audit/news_query_plan.json'),'source_freeze_sha256':sha(R/'audit/source_freeze.json') if not STAGE_ONLY else None,'card_sha256':{d.isoformat():sha(R/'cards'/f'{d.isoformat()}.json') for d in dates} if not STAGE_ONLY else {},'tool_sha256':{f:sha(R/'tools'/f) for f in ['fetch_news.py','expand_capped_news.py','ready_feeds.py','topics.py','finalize_sources.py']},'contract_sha256':{f:sha(R/f) for f in ['AUTHORING.md','BRIEF.md']},'guard_regressions_tested':len(guardcases),'declared_release_guards_extracted':len(sp['RELEASE_GUARDS']),'age_policy':'Headline semantics tighten maximum7day news/preview,14day company results,35day macro/policy windows. Independent replay uses inspected regex policy; semantic review by authors remains required.','limits':['Retrieval-time historical Google search results are not original contemporaneous RSS vintages. Raw retrieval responses are archived and hash-bound.','Daily100result caps and search indexing/selection prevent exhaustive coverage; residual daily caps explicitly listed.','RSS pubDate can precede actual release; publisher canonical dates and article bodies were not independently resolved.','Finite headline semantics/release regexes may miss relevant names or conservatively remove previews; exact cited claims require own-date editorial timing/meaning review.','This infrastructure acceptance does not approve report prose, concrete numeric claims, causal interpretation or historical trade selection.']}
output=Path(__file__).parent/('stage_review.json' if STAGE_ONLY else 'source_review_draft.json')
output.write_text(json.dumps(out,indent=2)+'\n')
(Path(__file__).parent/'old_monthly_for_manual_review.json').write_text(json.dumps(old_monthly,indent=2)+'\n')
print(json.dumps({'status':out['status'],'checks':out['checks'],'errors':errors,'requests':len(rows),'residual_daily_caps':len(caps)},indent=2))
raise SystemExit(bool(errors))
