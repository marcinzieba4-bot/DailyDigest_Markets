"""Independent physical XML reparse, request-plan replay and source-ID reconstruction.
No owner fetch/merge/build/screen functions are imported or invoked.
"""
from pathlib import Path
import json,gzip,hashlib,datetime as dt,email.utils,xml.etree.ElementTree as ET
import re,ast,sys,urllib.parse
from collections import Counter
R=Path('/workspace/work/oct2024/repo/corrections/2024-10')
sys.path.insert(0,str(R/'tools'))
from topics import TOPICS,EN
dates=[dt.date(2024,10,n) for n in range(1,32) if dt.date(2024,10,n).weekday()<5]
WIN={'news':7,'result':14,'monthly':35};UTC=dt.timezone.utc
VERSION='oct-2024-cutoff-prefix-v1'
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bytesof(j):return gzip.compress(json.dumps(j,ensure_ascii=False,separators=(',',':')).encode(),mtime=0)
errors=[];checks=Counter()
def ck(v,m,g='structure'):
 checks[g]+=1
 if not v:errors.append(m)
def patterns(file):
 tree=ast.parse((R/'tools'/file).read_text());out={}
 for node in tree.body:
  if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
   name=node.targets[0].id
   if isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Attribute) and node.value.func.attr=='compile':out[name]=re.compile(ast.literal_eval(node.value.args[0]),re.I)
   elif name=='RELEASE_GUARDS':out[name]=ast.literal_eval(node.value)
 return out
fp=patterns('fetch_news.py');sp=patterns('ready_feeds.py')
def semantic(title,category):
 if fp['PREVIEW'].search(title):return 'news'
 if category=='result' or (category=='monthly' and fp['CORPORATE'].search(title)):return 'result' if fp['RESULT_TEXT'].search(title) else 'news'
 return category
def guard(title,published,stamp):
 normal=sp['NEUTRALISE'].sub('',title)
 for label,eligible,start,pattern in sp['RELEASE_GUARDS']:
  if stamp<eligible and start<=published<stamp and re.search(pattern,title,re.I):
   residual=sp['FORWARD_ACTION'].sub('',normal)
   if sp['COMPLETED'].search(residual):return label
   if any(p.search(normal) for p in (sp['EXPLICIT_PREVIEW'],fp['PREVIEW'],sp['FORWARD'])):return None
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
 rawpath=R/'work/unreviewed_feeds'/f'{stamp}.json.gz';rawfeed=read(rawpath)
 ck(rawfeed['items']==items,stamp+' full independent own-cutoff merge/IDs','merge')
 ck(rawfeed['date']==stamp and dt.datetime.fromisoformat(rawfeed['cutoff_utc'])==cutoff and not rawfeed['fails'],stamp+' own-date identity/failures','merge')
 lp=R/'audit/news_provenance'/f'{stamp}.json.gz';ck(read(lp)['records']==ledger,stamp+' every physical provenance signature','merge')
 screened=[];excluded=[]
 for item in items:
  hit=guard(item['title'],item['published_at'][:10],stamp)
  if hit:excluded.append({'id':item['id'],'published_at':item['published_at'],'src':item['src'],'title':item['title'],'guard':hit})
  else:screened.append(item)
 feedpath=R/'feeds'/f'{stamp}.json.gz';feed=read(feedpath);receiptpath=R/'audit'/f'news_ready_{stamp}.json';ready=read(receiptpath);frozen=read(R/'audit'/f'news_frozen_{stamp}.json')
 ck(feed['items']==screened and ready['excluded']==excluded,stamp+' release screening replay','screening')
 ck(sha(feedpath)==ready['ready_sha256']==frozen['feed_sha256'],stamp+' ready/freeze bytehash','freeze')
 ck(sha(rawpath)==ready['unreviewed_sha256'],stamp+' raw receipt bytehash','freeze')
 ck(frozen['full_month_replay_verified'] and not frozen['full_month_replay_pending'],stamp+' complete full-month replay','freeze')
 ck(sha(feedpath)==sha(R/'work/source_candidates/feeds'/f'{stamp}.json.gz'),stamp+' staged ready identical','freeze')
 ck(sha(rawpath)==sha(R/'work/source_candidates/unreviewed_feeds'/f'{stamp}.json.gz'),stamp+' staged raw identical','freeze')
 ck(sha(lp)==sha(R/'work/source_candidates/news_provenance'/f'{stamp}.json.gz'),stamp+' staged provenance identical','freeze')
 for item in screened:
  pub=dt.datetime.fromisoformat(item['published_at']);ck(cutoff-dt.timedelta(days=WIN[item['cat']])<=pub<cutoff,stamp+' '+item['id']+' exact7/14/35 age','age')
  if item['cat']=='monthly' and pub<cutoff-dt.timedelta(days=14):old_monthly.append({'date':stamp,'id':item['id'],'title':item['title'],'src':item['src'],'published_at':item['published_at']})
 dateproof.append({'date':stamp,'raw_items':len(items),'ready_items':len(screened),'excluded':len(excluded),'feed_sha256':sha(feedpath),'raw_sha256':sha(rawpath),'provenance_sha256':sha(lp),'ready_receipt_sha256':sha(receiptpath),'qualifying_physical_requests':len(qualifying),'own_cutoff_prefix_contexts_whose_parent_ends_later':prefixfuture,'later_parent_daily_contexts_excluded':dailyexcluded})
 print(stamp,len(items),len(screened),'replayed',flush=True)
freeze=read(R/'audit/source_freeze.json');manifest=read(R/'work/source_candidates/comparison_manifest.json')
ck(freeze['status']=='all_23_ready' and len(freeze['dates'])==23 and freeze['frozen_feeds_immutable'],'All23 freeze status','freeze')
ck(manifest['status']=='all_23_compared_before_destination_write' and len(manifest['dates'])==23,'All23 staged comparisonmanifest','freeze')
ck(freeze['query_plan_sha256']==sha(R/'audit/news_query_plan.json') and freeze['coverage_sha256']==sha(R/'audit/news_coverage.json'),'Global source-freeze bindings','freeze')
ck(freeze['candidate_manifest_sha256']==sha(R/'work/source_candidates/comparison_manifest.json'),'Candidate manifest binding','freeze')
# Regression scenarios are synthetic guard tests, not acquired story evidence.
guardcases=[('Microsoft beats quarterly earnings estimates as Meta is set to report','2024-10-29','2024-10-30',True),('China October manufacturing activity expands, could boost equities','2024-10-30','2024-10-31',True),('Microsoft will beat quarterly earnings estimates','2024-10-29','2024-10-30',False),('China October PMI expected to expand','2024-10-30','2024-10-31',False),('China October PMI expands, ahead of the BOJ decision','2024-10-30','2024-10-31',True),('Tesla expected to report earnings as Microsoft beats Q3 estimates','2024-10-29','2024-10-30',True),('Japan September production rises in September','2024-10-30','2024-10-31',False),('Japan September production rises in September','2024-10-29','2024-10-30',True),('Japan September consumer prices rose more than expected','2024-10-17','2024-10-18',False),('Japan September consumer prices rose more than expected','2024-10-16','2024-10-17',True)]
for title,p,d,e in guardcases:ck(bool(guard(title,p,d))==e,'Guard regression '+title,'screening')
out={'status':'accepted' if not errors else 'failed','passed':not errors,'scope':'All23 October source acquisition/identity/immutability infrastructure only. Every physical raw RSS XML independently reparsed; catalogue jobs, capped daily refinements, own-cutoff merges, IDs and physical provenance independently reconstructed. Screening/semantic regex policy inspected and separately applied, not independently known article publication dates. No report narrative or retail-selection approval is conferred.','checks':sum(checks.values()),'checks_by_scope':dict(checks),'errors':errors,'dates':dateproof,'physical_requests':len(rows),'raw_xml_uncompressed_bytes':xmlbytes,'independently_reparsed_items':parsed_items,'failed_queries':sum(j['status']!='fetched' for j in physical.values()),'remaining_daily_caps':len(caps),'remaining_daily_cap_signatures':caps,'query_plan_sha256':sha(R/'audit/news_query_plan.json'),'source_freeze_sha256':sha(R/'audit/source_freeze.json'),'card_sha256':{d.isoformat():sha(R/'cards'/f'{d.isoformat()}.json') for d in dates},'tool_sha256':{f:sha(R/'tools'/f) for f in ['fetch_news.py','expand_capped_news.py','ready_feeds.py','topics.py','finalize_sources.py']},'contract_sha256':{f:sha(R/f) for f in ['AUTHORING.md','BRIEF.md']},'guard_regressions_tested':len(guardcases),'age_policy':'Headline semantics tighten maximum7day news/preview,14day company results,35day macro/policy windows. Independent replay uses inspected regex policy; semantic review by authors remains required.','limits':['Retrieval-time historical Google search results are not original contemporaneous RSS vintages. Raw retrieval responses are archived and hash-bound.','Daily100result caps and search indexing/selection prevent exhaustive coverage; residual daily caps explicitly listed.','RSS pubDate can precede actual release; publisher canonical dates and article bodies were not independently resolved.','Finite headline semantics/release regexes may miss relevant names or conservatively remove previews; exact cited claims require own-date editorial timing/meaning review.','This infrastructure acceptance does not approve report prose, concrete numeric claims, causal interpretation or historical trade selection.']}
(R/'audit/independent_source_review.json').write_text(json.dumps(out,indent=2)+'\n')
(Path(__file__).parent/'old_monthly_for_manual_review.json').write_text(json.dumps(old_monthly,indent=2)+'\n')
print(json.dumps({'status':out['status'],'checks':out['checks'],'errors':errors,'requests':len(rows),'residual_daily_caps':len(caps)},indent=2))
raise SystemExit(bool(errors))
