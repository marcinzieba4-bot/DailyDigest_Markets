"""Independent July request-plan/XML/provenance/frozen-projection replay.
No acquisition, owner merge/screen function, remote service or report authoring is invoked.
"""
from pathlib import Path,PurePosixPath
import argparse,ast,collections,datetime as dt,email.utils,gzip,hashlib,json,re,urllib.parse,xml.etree.ElementTree as ET
R=Path('/workspace/work/july2024');UTC=dt.timezone.utc;DATES=[dt.date(2024,7,n)for n in range(1,32)if dt.date(2024,7,n).weekday()<5];WIN={'news':7,'result':14,'monthly':35};VERSION='jul-2024-cutoff-prefix-partition-v1';SCHEMA='rss-root-channel-aware-timestamp-ledger-v2';EN=['en-US','US','US:en']
READ=lambda p:json.loads(gzip.decompress(p.read_bytes())if p.suffix=='.gz'else p.read_bytes())
SHA=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
CANON=lambda o:json.dumps(o,sort_keys=True,separators=(',',':'))
ENC=lambda o:gzip.compress(json.dumps(o,ensure_ascii=False,separators=(',',':')).encode(),mtime=0)
class Audit:
 def __init__(self):self.errors=[];self.counts=collections.Counter()
 def ck(self,ok,message,group='structure'):
  self.counts[group]+=1
  if not ok:self.errors.append({'scope':group,'error':message})
 def safe(self,relative):
  p=PurePosixPath(relative);f=R/p;self.ck(not p.is_absolute()and'..'not in p.parts and str(p)==relative and not f.is_symlink()and f.resolve().is_relative_to(R),'safe path '+relative,'paths');return f

def literal(node,env):
 if isinstance(node,ast.Constant):return node.value
 if isinstance(node,ast.Name)and node.id in env:return env[node.id]
 if isinstance(node,(ast.List,ast.Tuple,ast.Set)):
  values=[literal(n,env)for n in node.elts];return tuple(values)if isinstance(node,ast.Tuple)else set(values)if isinstance(node,ast.Set)else values
 if isinstance(node,ast.Dict):return{literal(k,env):literal(v,env)for k,v in zip(node.keys,node.values)}
 if isinstance(node,ast.BinOp)and isinstance(node.op,ast.Add):return literal(node.left,env)+literal(node.right,env)
 raise ValueError('Unsupported declarative expression '+ast.dump(node))
def constants(path):
 env={}
 for node in ast.parse(path.read_text()).body:
  if isinstance(node,ast.Assign)and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
   try:env[node.targets[0].id]=literal(node.value,env)
   except ValueError:pass
 return env

def patterns(path):
 env={};out={}
 def append(node,local):
  if isinstance(node,ast.Expr)and isinstance(node.value,ast.Call):
   call=node.value
   if isinstance(call.func,ast.Attribute)and isinstance(call.func.value,ast.Name)and call.func.value.id=='RELEASE_GUARDS'and call.func.attr in('append','extend'):
    value=literal(call.args[0],local)
    if call.func.attr=='append':out['RELEASE_GUARDS'].append(value)
    else:out['RELEASE_GUARDS'].extend(value)
 for node in ast.parse(path.read_text()).body:
  if isinstance(node,ast.Assign)and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
   name=node.targets[0].id
   if isinstance(node.value,ast.Call)and isinstance(node.value.func,ast.Attribute)and node.value.func.attr=='compile':
    try:out[name]=re.compile(literal(node.value.args[0],env),re.I)
    except ValueError:
     if name!='CORPORATE':raise
   else:
    try:env[name]=literal(node.value,env)
    except ValueError:continue
    if name=='RELEASE_GUARDS':out[name]=list(env[name])
  elif isinstance(node,ast.Expr):append(node,env)
  elif isinstance(node,ast.For)and isinstance(node.target,ast.Tuple):
   try:values=literal(node.iter,env)
   except ValueError:continue
   for val in values:
    local={**env,**{n.id:v for n,v in zip(node.target.elts,val)}}
    for statement in node.body:append(statement,local)
 return out

def request(j):
 topic,q,cat,loc,lo,hi=j;query=q+' after:'+(dt.date.fromisoformat(lo)-dt.timedelta(days=1)).isoformat()+' before:'+hi;url='https://news.google.com/rss/search?'+urllib.parse.urlencode({'q':query,'hl':loc[0],'gl':loc[1],'ceid':loc[2]});return hashlib.sha256((VERSION+'\n'+url).encode()).hexdigest(),url,query

def initial_plan(declaration):
 mapping={};weekly=[];prefixes=[]
 def add(j,kind,parent=None,**extra):return add_context(mapping,j,kind,parent,**extra)
 for topic,entries in declaration['topic_catalogue'].items():
  for entry in entries:
   q,cat=entry[:2];loc=list(entry[2])if len(entry)>2 else EN.copy();lo=min(DATES)-dt.timedelta(days=WIN[cat])
   while lo<max(DATES):
    hi=min(lo+dt.timedelta(days=7),max(DATES));weekly.append([topic,q,cat,loc,lo.isoformat(),hi.isoformat()]);lo=hi
 weekly.sort(key=lambda j:(j[4],j[5],j[0],j[1]))
 for j in weekly:add(j,'weekly')
 for d in DATES:
  for j in weekly:
   if j[4]<d.isoformat()<j[5]:
    child=[*j[:5],d.isoformat()];prefixes.append((j,child));add(child,'cutoff_prefix',request(j)[0])
 return mapping,weekly,prefixes

def add_context(mapping,j,kind,parent=None,**extra):
 sig,url,_=request(j)
 if url not in mapping:mapping[url]={'signature':sig,'request_url':url,'contexts':[]}
 context={'job':j,'kind':kind,**extra}
 if parent:context['parent_signature']=parent
 if context not in mapping[url]['contexts']:mapping[url]['contexts'].append(context)
 return sig

def parse_xml(raw,lo,hi,rolling):
 root=ET.fromstring(raw)
 if root.tag!='rss'or root.find('channel')is None:raise ValueError('RSS root/channel absent')
 nodes=root.findall('.//item');items=[];discard=collections.Counter()
 for node in nodes:
  try:
   date=email.utils.parsedate_to_datetime(node.findtext('pubDate'))
   if date.tzinfo is None:raise ValueError('naive publication timestamp')
   pub=date.astimezone(UTC)
  except Exception:discard['malformed_timestamp']+=1;continue
  if not lo<=pub.date().isoformat()<hi:discard['outside_query_window']+=1;continue
  title=(node.findtext('title')or'').strip();link=(node.findtext('link')or'').strip();source=node.find('source')
  if not title or not link.startswith('https://'):discard['missing_title_or_https_url']+=1;continue
  if rolling.search(title):discard['rolling_headline']+=1;continue
  items.append({'published_at':pub.isoformat(),'src':(source.text or'')if source is not None else'','source_url':source.get('url','')if source is not None else'','title':title,'url':link})
 return items,dict(discard),len(nodes)

def declared_plan_review(a):
 declaration=READ(R/'audit_work/news_catalogue_declaration.json');base=READ(R/'audit/news_base_query_plan.json');mapping,weekly,prefixes=initial_plan(declaration);a.ck(declaration['version']==VERSION and declaration['parser_schema']==SCHEMA,'declared July request/parser versions','declaration');a.ck(declaration['dates']==[d.isoformat()for d in DATES]==base['dates'],'exact23July dates','declaration');a.ck(sum(map(len,declaration['topic_catalogue'].values()))==declaration['catalogue_contexts'],'declared catalogue cardinality','declaration');a.ck(SHA(R/'tools/topics.py')==declaration['topics_sha256'],'fixed topic catalogue hash','declaration');a.ck(SHA(R/'tools/fetch_news.py')==declaration['fetch_tool_sha256'],'fetch/parser tool unchanged from declaration','declaration');a.ck(base['weekly_contexts']==len(weekly)and base['prefix_contexts']==len(prefixes),'independent weekly/prefix counts','base_plan');a.ck({row['request_url']:row for row in base['requests']}==mapping and len(base['requests'])==len(mapping),'every physical base URL/context independently reconstructed (declaration order does not govern fetch queue)','base_plan')
 return declaration,mapping,weekly,prefixes

def physical_replay(a,rows,fp):
 physical={};index=[];attempt_index={};ledger_path=R/'audit/news_physical_requests.jsonl';ledger_bytes=ledger_path.read_bytes();ledger=[]
 for line in ledger_bytes.splitlines():
  if line:ledger.append(json.loads(line))
 for x in ledger:
  key=(x['signature'],x['attempt'],x['started_at_utc']);a.ck(key not in attempt_index,'unique physical attempt '+str(key),'attempt_ledger');attempt_index[key]=x
 xmlbytes=0;parsed_total=0;received_attempts=0;failed_attempts=0;seen_attempts=set()
 for row in rows:
  sig=row['signature'];p=a.safe(row['cache_path']);batch=READ(p);physical[sig]=batch;a.ck(SHA(p)==row['cache_sha256'],'cache hash '+sig,'raw_transport');a.ck(batch['signature']==sig and batch['request_url']==row['request_url']and batch['version']==VERSION,'physical request identity '+sig,'raw_transport');a.ck(request([batch['topic'],batch['query'],batch['category'],batch['locale'],batch['lower_date'],batch['upper_date_exclusive']])==(sig,row['request_url'],batch['request_query']),'cache request URL/bounds reconstructed '+sig,'raw_transport');a.ck(all(c['job'][4:6]==[batch['lower_date'],batch['upper_date_exclusive']]for c in row['contexts']),'all context bounds equal physical cache '+sig,'raw_transport');a.ck(batch['status']=='fetched'and batch.get('response_format_verified')and batch['parser_schema']==SCHEMA,'final fetched RSS parser status '+sig,'raw_transport');rp=a.safe(batch['raw_response_path']);compressed=rp.read_bytes();raw=gzip.decompress(compressed);xmlbytes+=len(raw);a.ck(SHA(rp)==batch['raw_response_compressed_sha256']==row['raw_response_compressed_sha256'],'compressed raw SHA '+sig,'raw_transport');a.ck(hashlib.sha256(raw).hexdigest()==batch['raw_sha256']==row['raw_sha256'],'raw XML SHA '+sig,'raw_transport');items,discard,nodes=parse_xml(raw,batch['lower_date'],batch['upper_date_exclusive'],fp['ROLLING']);parsed_total+=len(items);a.ck(items==batch['items'],'complete independent XML item reparse '+sig,'xml_reparse');a.ck(discard==batch['discarded']and nodes==batch['raw_count']==row['raw_count'],'discard/raw counts '+sig,'xml_reparse');a.ck(bool(batch['possibly_capped'])==(nodes>=100)==bool(row['possibly_capped']),'observed cap classification '+sig,'xml_reparse');success=[]
  for attempt in batch['physical_attempts']:
   key=(sig,attempt['attempt'],attempt['started_at_utc']);seen_attempts.add(key);a.ck(attempt_index.get(key)==attempt,'cache attempt equals append-only physical ledger '+str(key),'attempt_ledger');a.ck(attempt['signature']==sig and attempt['request_url']==row['request_url'],'attempt URL identity '+str(key),'attempt_ledger');a.ck(dt.datetime.fromisoformat(attempt['finished_at_utc'])>=dt.datetime.fromisoformat(attempt['started_at_utc']),'attempt clock order '+str(key),'attempt_ledger')
   if attempt.get('raw_response_path'):
    ap=a.safe(attempt['raw_response_path']);ab=ap.read_bytes();ar=gzip.decompress(ab);received_attempts+=1;a.ck(SHA(ap)==attempt['raw_compressed_sha256']and hashlib.sha256(ar).hexdigest()==attempt['raw_sha256'],'every received physical attempt body retained '+str(key),'attempt_bodies')
    if attempt['status']=='fetched':
     ai,ad,an=parse_xml(ar,batch['lower_date'],batch['upper_date_exclusive'],fp['ROLLING']);a.ck(an==attempt['raw_count']and attempt['response_format_verified'],'successful attempt RSS counts '+str(key),'attempt_bodies');success.append((attempt,ar))
   if attempt['status']!='fetched':failed_attempts+=1
  a.ck(bool(success)and success[-1][1]==raw,'canonical raw bytes equal final successful physical attempt '+sig,'attempt_bodies');index.append({'signature':sig,'parsed_cache_path':row['cache_path'],'parsed_cache_sha256':SHA(p),'raw_xml_path':str(rp.relative_to(R)),'raw_xml_compressed_sha256':SHA(rp),'raw_xml_uncompressed_sha256':hashlib.sha256(raw).hexdigest(),'raw_items':nodes,'eligible_reparsed_items':len(items),'physical_attempts':len(batch['physical_attempts'])})
 a.ck(seen_attempts<=set(attempt_index),'all current cache attempts have ledger records','attempt_ledger');
 # Earlier failed fetch runs may be superseded by a later successful cache. Their physical attempts remain independently bound.
 for key in set(attempt_index)-seen_attempts:
  attempt=attempt_index[key];sig=attempt['signature'];a.ck(sig in physical and attempt['request_url']==physical[sig]['request_url'],'historical attempt belongs to planned URL '+str(key),'attempt_ledger');a.ck(dt.datetime.fromisoformat(attempt['finished_at_utc'])>=dt.datetime.fromisoformat(attempt['started_at_utc']),'historical attempt clocks '+str(key),'attempt_ledger')
  if attempt.get('raw_response_path'):
   ap=a.safe(attempt['raw_response_path']);ab=ap.read_bytes();ar=gzip.decompress(ab);received_attempts+=1;a.ck(SHA(ap)==attempt['raw_compressed_sha256']and hashlib.sha256(ar).hexdigest()==attempt['raw_sha256'],'historical received body preserved '+str(key),'attempt_bodies')
   if attempt['status']=='fetched':
    _,_,an=parse_xml(ar,physical[sig]['lower_date'],physical[sig]['upper_date_exclusive'],fp['ROLLING']);a.ck(an==attempt['raw_count']and attempt['response_format_verified'],'historical successful RSS attempt '+str(key),'attempt_bodies')
  if attempt['status']!='fetched':failed_attempts+=1
 declaration=READ(R/'audit_work/news_catalogue_declaration.json');a.ck(all(dt.datetime.fromisoformat(x['started_at_utc'])>=dt.datetime.fromisoformat(declaration['declared_at_utc'])for x in ledger),'catalogue declared before every recorded acquisition attempt','attempt_ledger');a.ck({str(p.relative_to(R))for p in(R/'cache/news').glob('*.json.gz')}=={r['cache_path']for r in rows},'all parsed physical cache files in plan','physical_inventory');a.ck({str(p.relative_to(R))for p in(R/'cache/rss_raw').glob('*.xml.gz')}=={r['raw_response_path']for r in rows},'all canonical raw physical files in plan','physical_inventory');attempt_paths={str(p.relative_to(R))for p in(R/'cache/rss_raw/attempts').glob('*.xml.gz')};a.ck(attempt_paths=={x['raw_response_path']for x in ledger if x.get('raw_response_path')},'all received attempt bodies in ledger','physical_inventory');return physical,index,{'raw_xml_uncompressed_bytes':xmlbytes,'independently_reparsed_items':parsed_total,'physical_attempts':len(ledger),'received_attempt_bodies':received_attempts,'failed_attempts':failed_attempts,'ledger_sha256':hashlib.sha256(ledger_bytes).hexdigest()}

def reuse_physical_replay(a,rows):
 """Reuse the completed XML interpretation only after rebinding every unchanged physical byte."""
 proofpath=R/'audit/independent_physical_source_review.json';proof=READ(proofpath);invpath=R/'audit_work/physical_source_inventory.json';inventory=READ(invpath);a.ck(proof.get('passed')is True and not proof.get('errors')and proof.get('status')=='physical_infrastructure_replay_passed','prior independent physical XML replay passed','physical_reuse');a.ck(proof['query_plan_sha256']==SHA(R/'audit/news_query_plan.json')==inventory['query_plan_sha256'],'unchanged physical plan for prior XML proof','physical_reuse');a.ck(proof['physical_source_inventory_sha256']==SHA(invpath),'exact prior independently reparsed physical inventory','physical_reuse');a.ck(proof['ledger_sha256']==SHA(R/'audit/news_physical_requests.jsonl'),'unchanged every-attempt ledger for prior XML proof','physical_reuse');index=inventory['files'];a.ck([x['signature']for x in index]==[x['signature']for x in rows],'exact prior physical inventory order/cardinality','physical_reuse');physical={}
 for row,old in zip(rows,index):
  cache=a.safe(row['cache_path']);raw=a.safe(row['raw_response_path']);a.ck(str(cache.relative_to(R))==old['parsed_cache_path']and SHA(cache)==old['parsed_cache_sha256']==row['cache_sha256'],'unchanged previously reparsed cache '+row['signature'],'physical_reuse');a.ck(str(raw.relative_to(R))==old['raw_xml_path']and SHA(raw)==old['raw_xml_compressed_sha256']==row['raw_response_compressed_sha256'],'unchanged previously reparsed raw XML '+row['signature'],'physical_reuse');physical[row['signature']]=READ(cache)
 ledger=[json.loads(x)for x in(R/'audit/news_physical_requests.jsonl').read_bytes().splitlines()if x];paths=set()
 for attempt in ledger:
  if attempt.get('raw_response_path'):
   p=a.safe(attempt['raw_response_path']);paths.add(attempt['raw_response_path']);a.ck(SHA(p)==attempt['raw_compressed_sha256'],'unchanged every recorded physical attempt body '+attempt['signature'],'physical_reuse')
 a.ck({str(p.relative_to(R))for p in(R/'cache/news').glob('*.json.gz')}=={x['cache_path']for x in rows},'no new/unplanned parsed caches','physical_reuse');a.ck({str(p.relative_to(R))for p in(R/'cache/rss_raw').glob('*.xml.gz')}=={x['raw_response_path']for x in rows},'no new/unplanned canonical raw XML','physical_reuse');a.ck({str(p.relative_to(R))for p in(R/'cache/rss_raw/attempts').glob('*.xml.gz')}==paths,'no new/unrecorded received attempts','physical_reuse');stats={k:proof[k]for k in ['raw_xml_uncompressed_bytes','independently_reparsed_items','physical_attempts','received_attempt_bodies','failed_attempts','ledger_sha256']};stats.update(physical_xml_replay_mode='prior_complete_independent_XML_reparse_with_all_current_physical_bytes_rebound',prior_physical_review_sha256=SHA(proofpath),prior_physical_checks=proof['checks']);return physical,index,stats

def refinement_replay(a,mapping,physical,plan):
 policy=plan['refinement_policy'];terms=policy['neutral_terms'];maxdepth=policy['maximum_partition_depth'];maxreq=policy['maximum_physical_requests'];a.ck(maxdepth==24 and maxreq==75000 and len(terms)==len(set(terms)),'declared finite complementary policy','cap_plan');expanded=set()
 for cutoff in[d.isoformat()for d in DATES]:
  while True:
   changed=False
   for row in list(mapping.values()):
    if row['contexts'][0]['job'][5]>cutoff:continue
    batch=physical[row['signature']]
    if not batch['possibly_capped']:continue
    for context in row['contexts'][:]:
     token=CANON([row['signature'],context])
     if token in expanded:continue
     j=context['job'];lo,hi=map(dt.date.fromisoformat,j[4:6]);bound=context.get('refinement_root_upper_date_exclusive',j[5]);children=[]
     if(hi-lo).days>1:
      strategy='daily_split'
      for n in range((hi-lo).days):
       day=lo+dt.timedelta(days=n);children.append(add_context(mapping,[*j[:4],day.isoformat(),(day+dt.timedelta(days=1)).isoformat()],'daily_refinement',row['signature'],refinement_root_upper_date_exclusive=bound,catalogue_query=context.get('catalogue_query',j[1])))
     else:
      strategy='complementary_term_partition';depth=context.get('partition_depth',0);a.ck(depth<maxdepth,'daily recursion finite '+row['signature'],'cap_plan');used=context.get('partition_terms',[]);available=[t for t in terms if t not in used and not re.search(r'\b'+re.escape(t)+r'\b',j[1],re.I)];a.ck(bool(available),'neutral term available '+row['signature'],'cap_plan');titles=[x['title']for x in batch['items']];counts={t:sum(bool(re.search(r'\b'+re.escape(t)+r'\b',title,re.I))for title in titles)for t in available};term=min(available,key=lambda t:(abs(counts[t]/max(len(titles),1)-.5),terms.index(t)));basis={'method':'balanced exact-headline count among fixed neutral terms; both complementary searches required','title_matches':counts[term],'eligible_titles':len(titles)}
      for side in['include','exclude']:
       query='('+j[1]+') '+(''if side=='include'else'-')+'"'+term+'"';children.append(add_context(mapping,[j[0],query,*j[2:]],'term_refinement',row['signature'],refinement_root_upper_date_exclusive=bound,catalogue_query=context.get('catalogue_query',j[1]),partition_depth=depth+1,partition_terms=used+[term],partition={'term':term,'side':side,'basis':basis}))
     row.setdefault('cap_resolutions',[]).append({'context_sha256':hashlib.sha256(CANON(context).encode()).hexdigest(),'strategy':strategy,'children':children,'root_upper_date_exclusive':bound});expanded.add(token);changed=True
   if not changed:break
 a.ck(len(mapping)<=maxreq,'finite physical request budget','cap_plan');rows=plan['requests'];a.ck(len(mapping)==len(rows)and list(mapping)==[r['request_url']for r in rows],'exact physical refinement URL inventory/order','cap_plan')
 for row in rows:
  expected=mapping[row['request_url']];a.ck(expected['signature']==row['signature']and expected['contexts']==row['contexts'],'all parent/prefix/daily/term contexts '+row['signature'],'cap_plan');a.ck(expected.get('cap_resolutions',[])==row.get('cap_resolutions',[]),'every capped context has exact complementary/daily resolution '+row['signature'],'cap_plan')
  for context in row['contexts']:a.ck(request(context['job'])[:2]==(row['signature'],row['request_url']),'context URL/signature '+row['signature'],'cap_plan')
 a.ck(all(not physical[r['signature']]['possibly_capped']or r.get('cap_resolutions')for r in rows),'no unresolved capped request','cap_plan')
 return mapping

def semantic_patterns():
 fp=patterns(R/'tools/fetch_news.py');company=constants(R/'tools/topics.py')['COMPANY_CATALOGUE'];fp['CORPORATE']=re.compile(fp['CORPORATE'].pattern+'|'+'|'.join(r'\b'+re.escape(name)+r'\b'for names in company.values()for name in names),re.I);return fp

def semantic(title,category,fp):
 if fp['PREVIEW'].search(title):return'news'
 if category=='result':return'result'if fp['RESULT_TEXT'].search(title)else'news'
 if category=='monthly'and fp['CORPORATE'].search(title):return'result'if fp['RESULT_TEXT'].search(title)else'news'
 if category=='monthly'and fp['CALENDAR_PREVIEW'].search(title):return'news'
 if category=='monthly'and(fp['TRANSIENT_MARKET'].search(title)or fp['CORPORATE_EVENT'].search(title)):return'news'
 if category=='monthly'and not fp['MACRO_MONTHLY'].search(title):return'result'if fp['RESULT_TEXT'].search(title)else'news'
 return category

def own_cutoff_merge(a,date,rows,physical,fp):
 stamp=date.isoformat();cutoff=dt.datetime.combine(date,dt.time(),UTC);merged={};provenance={};excluded=collections.Counter();failed=[];qualifying=set();root_excluded=0
 for row in rows:
  batch=physical[row['signature']]
  for context in row['contexts']:
   topic,query,category,loc,lo,hi=context['job'];bound=context.get('refinement_root_upper_date_exclusive',hi)if context['kind']in{'daily_refinement','term_refinement'}else hi
   if bound>stamp:excluded['refinement_parent_extends_beyond_report_cutoff']+=1;root_excluded+=1;continue
   if hi>stamp:excluded['request_window_extends_beyond_report_cutoff']+=1;continue
   if hi<=(date-dt.timedelta(days=WIN[category])).isoformat()or lo>=stamp:continue
   if batch['status']!='fetched':failed.append(row['signature']);continue
   qualifying.add(row['signature'])
   for item in batch['items']:
    pub=dt.datetime.fromisoformat(item['published_at']);cat=semantic(item['title'],category,fp)
    if not cutoff-dt.timedelta(days=WIN[cat])<=pub<cutoff:excluded['outside_own_date_window']+=1;continue
    key=(item['title'].casefold(),item['src'].casefold(),item['published_at']);provenance.setdefault(key,set()).add(row['signature'])
    if key in merged:
     old=merged[key]
     if topic not in old['topics']:old['topics'].append(topic)
     if query not in old['queries']:old['queries'].append(query)
     if WIN[cat]<WIN[old['cat']]:old['cat']=cat
     excluded['duplicate_query_matches']+=1;continue
    merged[key]={**item,'cat':cat,'topics':[topic],'q':query,'queries':[query],'lang':loc[0]}
 items=[x for x in merged.values()if cutoff-dt.timedelta(days=WIN[x['cat']])<=dt.datetime.fromisoformat(x['published_at'])<cutoff];excluded['post_dedup_age_mismatch']+=len(merged)-len(items);items.sort(key=lambda x:(x['topics'][0],x['published_at'],x['title'],x['src'],x['url']))
 for n,item in enumerate(items,1):item['id']=f'n{n:04d}'
 ledger={x['id']:sorted(provenance[(x['title'].casefold(),x['src'].casefold(),x['published_at'])])for x in items};return items,ledger,excluded,sorted(set(failed)),{'qualifying_physical_requests':len(qualifying),'later_refinement_root_contexts_excluded':root_excluded}

def semantic_guards():
 tree=ast.parse((R/'tools/ready_feeds.py').read_text());node=next(n for n in tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='SEMANTIC_GUARDS'for t in n.targets));return[(literal(x.elts[0],{}),re.compile(literal(x.elts[1].args[0],{}),re.I))for x in node.value.elts]

def projection_replay(a,rows,physical,fp,stage_only):
 import importlib.util
 spec=importlib.util.spec_from_file_location('independent_july_guard_policy',R/'audit_work/independent_guard_policy.py');policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy);sp,_,schedule=policy.load();a.ck(not schedule.get('pending_root_review'),'all declared release-review pending items dispositioned before final replay','semantic_review');sem=semantic_guards();schedule_hash=SHA(R/'audit_work/july_release_schedule.json');version=constants(R/'tools/ready_feeds.py')['GUARD_VERSION'];dateproof=[];old_monthly=[];namedpath=R/'audit_work/july_named_source_exclusions.json';namedpolicy=READ(namedpath);namedhash=SHA(namedpath);recommendation_path=a.safe(namedpolicy['independent_recommendation_path']);recommendations=READ(recommendation_path)['exclusions'];a.ck(namedpolicy['independent_recommendation_sha256']==SHA(recommendation_path),'named source exclusions bind independent recommendations','named_exclusions');a.ck({(x['date'],x['id'])for x in namedpolicy['exclusions']}=={(x['date'],x['id'])for x in recommendations},'exact independently recommended own-date omissions','named_exclusions')
 for date in DATES:
  stamp=date.isoformat();cutoff=dt.datetime.combine(date,dt.time(),UTC);items,ledger,excluded_counts,failed,meta=own_cutoff_merge(a,date,rows,physical,fp);rawpath=R/('work/source_candidates/unreviewed_feeds'if stage_only else'work/unreviewed_feeds')/f'{stamp}.json.gz';provpath=R/('work/source_candidates/news_provenance'if stage_only else'audit/news_provenance')/f'{stamp}.json.gz';feedpath=R/('work/source_candidates/feeds'if stage_only else'feeds')/f'{stamp}.json.gz';receiptpath=R/('work/source_candidates/ready_receipts'if stage_only else'audit')/f'news_ready_{stamp}.json';raw=READ(rawpath);prov=READ(provpath);feed=READ(feedpath);receipt=READ(receiptpath);coverage_row=next(x for x in READ(R/'audit/news_coverage.json')['dates']if x['date']==stamp);a.ck(coverage_row['items']==len(items)and coverage_row['excluded']==dict(excluded_counts),stamp+' independent acquisition/exclusion counts','merge')
  a.ck(not failed and raw['fails']==failed and raw['items']==items,stamp+' full independent raw merge/IDs','merge');a.ck(raw['date']==stamp and dt.datetime.fromisoformat(raw['cutoff_utc'])==cutoff and raw['pipeline']==VERSION and raw['query_upper_bound_enforced'],stamp+' raw identity/cutoff','merge');a.ck(prov['date']==stamp and dt.datetime.fromisoformat(prov['cutoff_utc'])==cutoff and prov['records']==ledger,stamp+' every physical provenance signature','merge');screened=[];excluded=[];annotations=[];tightenings=[]
  named={x['id']:x for x in namedpolicy['exclusions']if x['date']==stamp};raw_by_id={x['id']:x for x in items}
  for identity,omission in named.items():
   original=raw_by_id.get(identity,{});a.ck(all(original.get(k)==omission[k]for k in ['id','title','published_at','src']),stamp+' exact named omission identity '+identity,'named_exclusions');recommended=next(x for x in recommendations if(x['date'],x['id'])==(stamp,identity));a.ck(all(original.get(k)==recommended[k]for k in ['id','title','published_at','source_url','url']),stamp+' named omission matches independent raw identity '+identity,'named_exclusions');a.ck(recommended['unreviewed_sha256']==SHA(rawpath)and omission['basis_url']==recommended['evidence']['url']and omission['screen_kind']=='timing_uncertainty',stamp+' named omission proof/raw bytes '+identity,'named_exclusions')
  for item in items:
   if item['title']in policy.OBSERVED_PREVIEWS:
    if dt.datetime.fromisoformat(item['published_at'])<cutoff-dt.timedelta(days=7):excluded.append({k:item[k]for k in ['id','published_at','src','title']}|{'guard':'Observed pending company preview older than seven days','screen_kind':'semantic_age'});continue
    if item['cat']!='news':tightenings.append({'id':item['id'],'from_category':item['cat'],'to_category':'news','reason':'Exact observed pending company preview; semantic seven-day window'});item={**item,'cat':'news'}
   if item['id']in named:excluded.append(named[item['id']]);continue
   semantic_label=next((label for label,pattern in sem if pattern.search(item['title'])),None);hit=semantic_label or policy.guard(item['title'],item['published_at'][:10],stamp,sp,fp,schedule)
   if hit:excluded.append({k:item[k]for k in['id','published_at','src','title']}|{'guard':hit,'screen_kind':'semantic'if semantic_label else'timing'})
   else:
    screened.append(item)
    if stamp=='2024-07-05'and re.search(r'exit.poll|projection|projected',item['title'],re.I)and re.search(r'Labour|Starmer|Britain|British|UK',item['title'],re.I):annotations.append({'id':item['id'],'status':'projection wording only; not a settled Friday result or PM appointment'})
  a.ck(feed['items']==screened,stamp+' independently screened items retain stable IDs/order','screening');a.ck(all(feed.get(k)==v for k,v in raw.items()if k!='items'),stamp+' all original raw metadata retained','screening');a.ck(feed['release_schedule_sha256']==schedule_hash and feed['release_guards_version']==version and feed['named_exclusions_sha256']==namedhash,stamp+' current guard table/version/named omission binding','screening');a.ck(receipt['excluded']==excluded and receipt['eligible_status_annotations']==annotations and receipt.get('category_tightenings')==tightenings,stamp+' exact timing/semantic exclusions and projection labels','screening');a.ck(receipt['excluded_by_guard']==dict(collections.Counter(x['guard']for x in excluded)),stamp+' exclusion group counts','screening');a.ck(receipt['input_items']==len(items)and receipt['ready_items']==len(screened)and receipt['excluded_items']==len(excluded),stamp+' exact raw/ready/excluded counts','screening');a.ck(SHA(feedpath)==receipt['ready_sha256']and SHA(rawpath)==receipt['unreviewed_sha256'],stamp+' raw/ready receipt hashes','byte_bindings');a.ck(receipt['release_schedule_sha256']==schedule_hash and receipt['release_guards_version']==version and receipt['named_exclusions_sha256']==namedhash,stamp+' receipt policy bindings','byte_bindings')
  for item in screened:
   pub=dt.datetime.fromisoformat(item['published_at']);a.ck(cutoff-dt.timedelta(days=WIN[item['cat']])<=pub<cutoff,stamp+' '+item['id']+' semantic age/cutoff','age')
   if item['cat']=='monthly'and pub<cutoff-dt.timedelta(days=7):old_monthly.append({'date':stamp,'id':item['id'],'title':item['title'],'src':item['src'],'published_at':item['published_at']})
  if not stage_only:
   frozen=READ(R/'audit'/f'news_frozen_{stamp}.json');a.ck(frozen['feed_sha256']==SHA(feedpath)and frozen['status']=='frozen_complete_own_date'and frozen['full_month_replay_verified']and not frozen['full_month_replay_pending']and frozen['query_plan_sha256']==SHA(R/'audit/news_query_plan.json')and frozen['semantic_review_sha256']==SHA(R/'audit_work/news_semantic_review.json'),stamp+' final immutable freeze proof','freeze')
   for path,staged in [(rawpath,R/'work/source_candidates/unreviewed_feeds'/f'{stamp}.json.gz'),(provpath,R/'work/source_candidates/news_provenance'/f'{stamp}.json.gz'),(feedpath,R/'work/source_candidates/feeds'/f'{stamp}.json.gz')]:a.ck(SHA(path)==SHA(staged),stamp+' actual frozen/staged bytes '+str(path.relative_to(R)),'freeze')
  dateproof.append({'date':stamp,'raw_items':len(items),'ready_items':len(screened),'excluded':len(excluded),'category_tightenings':len(tightenings),'feed_sha256':SHA(feedpath),'raw_sha256':SHA(rawpath),'provenance_sha256':SHA(provpath),'ready_receipt_sha256':SHA(receiptpath),'independent_merge_excluded':dict(excluded_counts),**meta});print(stamp,len(items),len(screened),'independent projection replay',flush=True)
 manifest_path=R/'work/source_candidates/comparison_manifest.json';manifest=READ(manifest_path);a.ck(manifest['status']=='all_23_compared_before_destination_write'and[row['date']for row in manifest['dates']]==[d.isoformat()for d in DATES],'all69actual staged candidates compared across23dates','staging');a.ck(manifest['query_plan_sha256']==SHA(R/'audit/news_query_plan.json'),'candidate manifest physical plan binding','staging')
 for row in manifest['dates']:
  stamp=row['date'];a.ck(row['all_stage_bytes_verified'],'candidate comparison '+stamp,'staging')
  for field,folder in [('raw_candidate_sha256','unreviewed_feeds'),('provenance_candidate_sha256','news_provenance'),('ready_candidate_sha256','feeds')]:a.ck(row[field]==SHA(R/'work/source_candidates'/folder/f'{stamp}.json.gz'),'candidate exact byte hash '+stamp+' '+folder,'staging')
 for name,value in manifest['tool_sha256'].items():a.ck(SHA(R/'tools'/name)==value,'candidate tool hash '+name,'staging')
 regressions=[]
 for title,pub,stamp,expected in policy.CASES:
  observed=policy.guard(title,pub,stamp,sp,fp,schedule);regressions.append({'title':title,'published_date':pub,'report_date':stamp,'expected_excluded':expected,'actual_guard':observed});a.ck(bool(observed)==expected,'independent guard regression '+title,'guard_regressions')
 for event in schedule['guards']:
  if isinstance(event.get('release_utc'),str):a.ck(dt.datetime.fromisoformat(event['eligible_edition']).replace(tzinfo=UTC)>dt.datetime.fromisoformat(event['release_utc']),'eligible cutoff after known UTC release '+event['label'],'guard_schedule')
 (R/'audit_work/old_monthly_for_manual_review.json').write_text(json.dumps(old_monthly,ensure_ascii=False,indent=2)+'\n');return dateproof,regressions,len(schedule['guards'])

# Final semantic projection and release-regression review are defined below after the engineer stabilizes the July guard table.
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--plan-only',action='store_true');parser.add_argument('--physical-only',action='store_true');parser.add_argument('--stage-only',action='store_true');parser.add_argument('--accept',action='store_true');parser.add_argument('--reuse-physical',action='store_true');args=parser.parse_args();a=Audit();declaration,mapping,weekly,prefixes=declared_plan_review(a)
 if args.plan_only:
  out={'status':'independent_declared_plan_verified_pending_physical_and_semantic_freeze','passed':False,'design_checks_passed':not a.errors,'checked_at_utc':dt.datetime.now(UTC).isoformat(),'checks':sum(a.counts.values()),'checks_by_scope':dict(a.counts),'errors':a.errors,'dates':[d.isoformat()for d in DATES],'catalogue_contexts':declaration['catalogue_contexts'],'weekly_contexts':len(weekly),'own_cutoff_prefix_contexts':len(prefixes),'independent_unique_base_requests':len(mapping),'catalogue_declaration_sha256':SHA(R/'audit_work/news_catalogue_declaration.json'),'base_query_plan_sha256':SHA(R/'audit/news_base_query_plan.json'),'fetch_tool_sha256':SHA(R/'tools/fetch_news.py'),'reviewer_tool_sha256':SHA(Path(__file__)),'pending':['All physical raw XML/cache/attempt ledger replay','Exact observed-cap refinement replay','July-specific release/preview screening and semantic projection','All23 immutable final feed/provenance/candidate/card bindings'],'scope':'Declared plan and parser/cap design only; no source-authoring acceptance.'};(R/'audit/independent_source_design_review.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items()if k not in['dates','pending']},indent=2));return
 if args.physical_only:
  plan_path=R/'audit/news_query_plan.json';coverage_path=R/'audit/news_coverage.json';plan=READ(plan_path);coverage=READ(coverage_path);before={str(p.relative_to(R)):SHA(p)for p in [plan_path,coverage_path,R/'audit/news_physical_requests.jsonl',R/'audit_work/news_catalogue_declaration.json']};a.ck(plan['status']=='all_requests_acquired_caps_resolved','all physical acquisition complete','plan');a.ck(coverage['failed_requests']==0 and coverage['unresolved_capped_requests']==0 and coverage['remaining_daily_caps']==0,'no failed or unresolved capped physical requests','plan');a.ck(coverage['query_plan_sha256']==SHA(plan_path),'coverage binds physical plan','plan');fp=semantic_patterns();physical,index,statistics=physical_replay(a,plan['requests'],fp);refinement_replay(a,mapping,physical,plan);inventory={'status':'all_physical_source_files_independently_reparsed','query_plan_sha256':SHA(plan_path),'files':index};inv=R/'audit_work/physical_source_inventory.json';inv.write_text(json.dumps(inventory,indent=2)+'\n')
  for path,value in before.items():a.ck(SHA(R/path)==value,'stable during physical review '+path,'concurrency')
  out={'status':'physical_infrastructure_replay_passed'if not a.errors else'physical_infrastructure_replay_failed','passed':not a.errors,'authoring_acceptance':False,'checked_at_utc':dt.datetime.now(UTC).isoformat(),'checks':sum(a.counts.values()),'checks_by_scope':dict(a.counts),'errors':a.errors,'dates':[d.isoformat()for d in DATES],'physical_requests':len(physical),**statistics,'query_plan_sha256':SHA(plan_path),'physical_source_inventory_sha256':SHA(inv),'reviewer_tool_sha256':SHA(Path(__file__)),'input_bindings':before,'scope':'Physical raw XML/cache/attempt-ledger and declared parent/prefix/refinement graph only. Semantic guards, staged projections, final feeds/cards and authoring acceptance remain pending.'};(R/'audit/independent_physical_source_review.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items()if k not in['dates','input_bindings','scope']},indent=2));return
 plan_path=R/'audit/news_query_plan.json';coverage_path=R/'audit/news_coverage.json';plan=READ(plan_path);coverage=READ(coverage_path);paths=[plan_path,coverage_path,R/'audit_work/news_policy_lock.json',R/'audit/news_physical_requests.jsonl',R/'audit_work/news_catalogue_declaration.json',R/'audit_work/july_release_schedule.json',R/'audit_work/july_named_source_exclusions.json',R/'audit_work/release_guard_refs/named_omission_recommendations.json',R/'audit_work/independent_guard_policy.py',R/'tools/fetch_news.py',R/'tools/expand_capped_news.py',R/'tools/ready_feeds.py',R/'tools/finalize_sources.py',R/'tools/topics.py',R/'work/source_candidates/comparison_manifest.json'];before={str(p.relative_to(R)):SHA(p)for p in paths};policy_lock=READ(R/'audit_work/news_policy_lock.json');a.ck(policy_lock['status']=='locked_for_final_release_review_and_candidate_replay','final policy explicitly locked for independent replay','policy_lock');[a.ck(SHA(a.safe(path))==value,'exact locked policy bytes '+path,'policy_lock')for path,value in policy_lock['files'].items()];a.ck(plan['status']=='all_requests_acquired_caps_resolved'and coverage['failed_requests']==0 and coverage['unresolved_capped_requests']==0 and coverage['remaining_daily_caps']==0,'complete uncapped physical acquisition','plan');a.ck(coverage['query_plan_sha256']==SHA(plan_path),'coverage physical-plan binding','plan');fp=semantic_patterns();physical,index,statistics=reuse_physical_replay(a,plan['requests'])if args.reuse_physical else physical_replay(a,plan['requests'],fp);refinement_replay(a,mapping,physical,plan);inv=R/'audit_work/physical_source_inventory.json';inv.write_text(json.dumps({'status':'all_physical_source_files_independently_reparsed','query_plan_sha256':SHA(plan_path),'files':index},indent=2)+'\n');dateproof,regressions,guard_count=projection_replay(a,plan['requests'],physical,fp,args.stage_only);card_hashes={}
 for row in dateproof:
  stamp=row['date']
  for field,relative in [('feed_sha256',('work/source_candidates/feeds'if args.stage_only else'feeds')+'/'+stamp+'.json.gz'),('raw_sha256',('work/source_candidates/unreviewed_feeds'if args.stage_only else'work/unreviewed_feeds')+'/'+stamp+'.json.gz'),('provenance_sha256',('work/source_candidates/news_provenance'if args.stage_only else'audit/news_provenance')+'/'+stamp+'.json.gz'),('ready_receipt_sha256',('work/source_candidates/ready_receipts'if args.stage_only else'audit')+'/news_ready_'+stamp+'.json')]:before[relative]=row[field]
 if not args.stage_only:
  freeze_path=R/'audit/source_freeze.json';freeze=READ(freeze_path);before[str(freeze_path.relative_to(R))]=SHA(freeze_path);semantic_path=R/'audit_work/news_semantic_review.json';semantic_review=READ(semantic_path);before[str(semantic_path.relative_to(R))]=SHA(semantic_path);a.ck(freeze['status']=='all_23_ready'and len(freeze['dates'])==23 and freeze['frozen_feeds_immutable']and freeze['candidates_all_compared_before_any_write'],'complete immutable23-source freeze','freeze');a.ck(freeze['query_plan_sha256']==SHA(plan_path)and freeze['coverage_sha256']==SHA(coverage_path)and freeze['candidate_manifest_sha256']==SHA(R/'work/source_candidates/comparison_manifest.json'),'global freeze exact plan/coverage/candidate bindings','freeze');a.ck(semantic_review.get('status')=='completed'and semantic_review.get('fatal_or_major_remaining')==0,'completed semantic review with no unresolved fatal/major issue','semantic_review');a.ck(semantic_review['query_plan_sha256']==SHA(plan_path)and semantic_review['release_schedule_sha256']==SHA(R/'audit_work/july_release_schedule.json')and semantic_review['screening_tool_sha256']==SHA(R/'tools/ready_feeds.py')and semantic_review.get('named_exclusions_sha256')==SHA(R/'audit_work/july_named_source_exclusions.json'),'semantic review exact physical/screening/table bindings','semantic_review');a.ck(freeze['semantic_review_sha256']==SHA(semantic_path)and freeze['physical_request_ledger_sha256']==SHA(R/'audit/news_physical_requests.jsonl'),'freeze binds semantic review and physical attempt ledger','freeze');latepath=R/'audit/independent_release_guard_review.json';a.ck(latepath.exists(),'independent calendar/guard review present','semantic_review')
  if latepath.exists():
   late=READ(latepath);before[str(latepath.relative_to(R))]=SHA(latepath);a.ck(late.get('passed')is True and late.get('fatal_or_major_remaining')==0 and not late.get('errors'),'independent calendar/guard review resolved','semantic_review');a.ck(late.get('release_schedule_sha256',late.get('schedule_sha256'))==SHA(R/'audit_work/july_release_schedule.json')and late.get('screening_tool_sha256',late.get('ready_tool_sha256'))==SHA(R/'tools/ready_feeds.py')and late.get('named_exclusions_sha256')==SHA(R/'audit_work/july_named_source_exclusions.json')and late.get('owner_policy_lock_sha256')==SHA(R/'audit_work/news_policy_lock.json'),'independent guard review binds current table/policy/named data/lock','semantic_review');a.ck(semantic_review.get('independent_release_guard_review_sha256')==SHA(latepath)and semantic_review.get('candidate_manifest_sha256')==SHA(R/'work/source_candidates/comparison_manifest.json'),'semantic review binds current independent guard review and69candidate manifest','semantic_review')
  for date in DATES:
   p=R/'cards'/f'{date.isoformat()}.json';a.ck(p.is_file(),'own-date card exists '+date.isoformat(),'cards')
   if p.is_file():card_hashes[date.isoformat()]=SHA(p);before[str(p.relative_to(R))]=SHA(p)
  for row in dateproof:
   frozen_row=next(x for x in freeze['dates']if x['date']==row['date']);a.ck(frozen_row['screened_sha256']==row['feed_sha256']and frozen_row['screened_items']==row['ready_items'],'global per-date source binding '+row['date'],'freeze')
  marketpath=R/'audit/independent_market_review.json';a.ck(marketpath.is_file(),'independent market review present','market_binding')
  if marketpath.is_file():
   market=READ(marketpath);a.ck(market.get('passed')is True and market.get('status')=='accepted'and not market.get('errors'),'independent market review accepted without errors','market_binding');a.ck(market.get('dates')==[d.isoformat()for d in DATES],'independent market review exact23dates','market_binding');a.ck(market.get('source_freeze_sha256')==SHA(freeze_path),'independent market review bound to current immutable source freeze','market_binding');a.ck(market.get('card_sha256')==card_hashes,'independent market review all23 current card hashes','market_binding');before[str(marketpath.relative_to(R))]=SHA(marketpath)
 for path,value in before.items():a.ck(SHA(R/path)==value,'stable throughout replay '+path,'concurrency')
 status=('staged_infrastructure_verified'if args.stage_only else'accepted_for_authoring_with_semantic_exclusions')if not a.errors else'failed';out={'status':status,'passed':not a.errors,'infrastructure_status':'accepted'if not a.errors else'failed','semantic_status':'requires_own_claim_review','authoring_acceptance':bool(args.accept and not args.stage_only and not a.errors),'checked_at_utc':dt.datetime.now(UTC).isoformat(),'scope':'Independent July physical acquisition/parser/attempt-ledger/refinement/own-cutoff merge/IDs/provenance and finite semantic-screen projection replay. No factual report, retail selection or original publisher-vintage approval.','checks':sum(a.counts.values()),'checks_by_scope':dict(a.counts),'errors':a.errors,'structural_errors':len(a.errors),'pending_dates':0 if not a.errors else 23,'dates':dateproof,'physical_requests':len(physical),**statistics,'observed_capped_requests':sum(bool(x['possibly_capped'])for x in physical.values()),'refinement_contexts':sum(c['kind']in{'daily_refinement','term_refinement'}for row in plan['requests']for c in row['contexts']),'remaining_daily_caps':0,'remaining_daily_cap_signatures':[],'failed_queries':sum(x['status']!='fetched'for x in physical.values()),'physical_source_inventory_sha256':SHA(inv),'query_plan_sha256':SHA(plan_path),'source_freeze_sha256':SHA(R/'audit/source_freeze.json')if not args.stage_only else None,'card_sha256':card_hashes,'independent_market_review_sha256':SHA(R/'audit/independent_market_review.json')if not args.stage_only else None,'tool_sha256':{name:SHA(R/'tools'/name)for name in ['fetch_news.py','expand_capped_news.py','ready_feeds.py','topics.py','finalize_sources.py']},'contract_sha256':{name:SHA(R/name)for name in ['AUTHORING.md','BRIEF.md']},'declared_release_guards_extracted':guard_count,'guard_regressions_tested':len(regressions),'guard_regressions':regressions,'input_bindings':before,'reviewer_tool_sha256':SHA(Path(__file__)),'reviewer_dependency_sha256':{'independent_guard_policy.py':SHA(R/'audit_work/independent_guard_policy.py')},'age_policy':'Headline semantics cap company news/previews7days,company results14days,macro/current-policy35days; actual versus preview is separately screened.','limits':['Retrieval-time historical Google RSS/search bytes are archived, not original contemporaneous publisher or full-article vintages.','Finite semantic/release guard coverage and headline-only meaning still require exact own-date editorial review.','Observed response caps are resolved through deterministic daily/complementary branches, but historical indexing/selection does not prove exhaustive reporting coverage.','Any subsequent change to frozen feed/card/provenance or guarded policy requires a separately reviewed revision; no unrecorded amendment is accepted.']};output=R/'audit_work'/('independent_staged_source_review.json'if args.stage_only else'source_review_draft.json');output.write_text(json.dumps(out,indent=2)+'\n')
 if args.accept:
  if args.stage_only or a.errors:raise SystemExit('No authoring acceptance permitted for staged or failed replay')
  (R/'audit/independent_source_review.json').write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps({'status':status,'passed':not a.errors,'checks':out['checks'],'errors':a.errors,'dates':len(dateproof),'physical_requests':len(physical),'guard_regressions':len(regressions)},indent=2));raise SystemExit(bool(a.errors))
if __name__=='__main__':main()
