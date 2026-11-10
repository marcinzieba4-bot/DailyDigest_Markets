"""April offline physical XML, request graph, own-cutoff IDs/provenance and policy replay.

Query/XML/merge/cap routines are adapted from the reviewed June independent
checker. Finite semantic policy is an explicit separately retained code snapshot,
not a claim of publisher-vintage or factual report approval. No acquisition,
owner merge/screen function, remote service or report authoring is invoked.
"""
from pathlib import Path,PurePosixPath
import argparse,ast,collections,datetime as dt,email.utils,gzip,hashlib,importlib.util,json,re,sys,urllib.parse,xml.etree.ElementTree as ET
R=Path(__file__).resolve().parent.parent
UTC=dt.timezone.utc
DATES=[dt.date(2024,4,n)for n in range(1,31)if dt.date(2024,4,n).weekday()<5]
WIN={'news':7,'result':14,'monthly':35}
VERSION='apr-2024-cutoff-prefix-partition-v1'
SCHEMA='rss-root-channel-aware-timestamp-ledger-v2'
EN=['en-US','US','US:en']
READ=lambda p:json.loads(gzip.decompress(p.read_bytes())if p.suffix=='.gz'else p.read_bytes())
SHA=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
CANON=lambda o:json.dumps(o,sort_keys=True,separators=(',',':'))
COMPACT=lambda o:json.dumps(o,ensure_ascii=False,separators=(',',':')).encode()
ENC=lambda o:gzip.compress(COMPACT(o),mtime=0)
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
 a.ck({str(p.relative_to(R))for p in(R/'cache/news').glob('*.json.gz')}=={row['cache_path']for row in rows},'exact parsed physical cache inventory','physical_inventory')
 a.ck({str(p.relative_to(R))for p in(R/'cache/rss_raw').glob('*.xml.gz')}=={row['raw_response_path']for row in rows},'exact canonical raw inventory','physical_inventory')
 return physical,index,{'raw_xml_uncompressed_bytes':xmlbytes,'independently_reparsed_items':parsed_total}


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
 if fp['PREVIEW'].search(title)or fp['COMPANY_PENDING'].search(title):return'news'
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

def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value

def write(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');temp.replace(path)

def bind(paths):
 result={}
 for p in paths:
  p=Path(p);relative=p.relative_to(R).as_posix()
  if p.is_symlink()or not p.is_file()or not p.resolve().is_relative_to(R):raise ValueError('Unsafe/missing review dependency '+relative)
  result[relative]=SHA(p)
 return result

def no_collectors():
 helper=module('april_resume_process_check',R/'tools/resume_final_cutoff.py')
 active=[x for x in helper.collectors()if not('--replay'in x['args']and any(Path(v).name=='expand_capped_news.py'for v in x['args']))]
 if active:raise ValueError('Offline final source review requires settled collectors: '+json.dumps(active))

def refresh_capture_disclosure():
 no_collectors();p=R/'audit_work/acquisition_capture_limitation.json';old=p.read_bytes();value=READ(p)
 ledger=[json.loads(x)for x in(R/'audit/news_physical_requests.jsonl').read_text().splitlines()if x]
 starts=[json.loads(x)for x in(R/'audit/news_physical_attempt_starts.jsonl').read_text().splitlines()if x]
 ids={x['attempt_id']for x in ledger};unknown=[x for x in starts if x['attempt_id']not in ids]
 assert unknown==value['unmatched_attempt_starts']and len(unknown)==value['unmatched_attempt_start_count_at_review'],'Unreconciled new interrupted starts'
 missing=[x for x in ledger if not x.get('raw_response_path')]
 if value.get('affected_attempts')==missing and value.get('recorded_failed_attempts_missing_bodies')==len(missing):
  print(json.dumps({'capture_disclosure_unchanged':True,'journaled_unknown_starts':len(unknown),'recorded_completed_without_exposed_body':len(missing),'capture_limitation_sha256':SHA(p)},indent=2));return
 assert all(x['status']=='failed'and x.get('response_body_unavailable')is True for x in missing),'Unexplained missing completed response body'
 prior=R/'audit/source_amendments/capture_disclosure'/(hashlib.sha256(old).hexdigest()+'.json');prior.parent.mkdir(parents=True,exist_ok=True)
 if prior.exists():assert prior.read_bytes()==old
 else:prior.write_bytes(old)
 value.update(affected_attempts=missing,recorded_failed_attempts_missing_bodies=len(missing),completed_unexposed_body_scope='Exact recorded completed transport failures with no HTTP response body exposed; no discarded HTTPError body is inferred.',completed_body_reconciliation_at_utc=dt.datetime.now(UTC).isoformat(),prior_disclosure_path=prior.relative_to(R).as_posix(),prior_disclosure_sha256=SHA(prior))
 write(p,value)
 print(json.dumps({'journaled_unknown_starts':len(unknown),'recorded_completed_without_exposed_body':len(missing),'capture_limitation_sha256':SHA(p)},indent=2))

def refresh_private_commitments(inventory):
 names=inventory.scan_private_research();rows=[{'path':n,'sha256':SHA(inventory.private_path(n)),'bytes':inventory.private_path(n).stat().st_size}for n in names]
 assert rows,'No retained private research originals'
 path=R/inventory.PRIVATE_MANIFEST
 if path.exists():
  old=path.read_bytes();previous=R/'audit/source_amendments/private_commitments'/(hashlib.sha256(old).hexdigest()+'.json');previous.parent.mkdir(parents=True,exist_ok=True)
  if previous.exists():assert previous.read_bytes()==old
  else:previous.write_bytes(old)
 write(path,{'schema':'april-private-research-commitments-v1','scope':'Exact original research bytes remain private outside ROOT. Public archive exposes hash commitments only, without original response/body replay.','files':rows})
 print(json.dumps({'private_files':len(rows),'commitment_manifest_sha256':SHA(path),'originals_exported':False},indent=2))

def catalogue(a):
 declaration=READ(R/'audit_work/news_catalogue_declaration.json')
 a.ck(declaration['dates']==[d.isoformat()for d in DATES],'exact22weekday catalogue scope','declaration')
 a.ck(declaration['tool_sha256']['topics.py']==SHA(R/'tools/topics.py'),'fixed catalogue code commitment','declaration')
 a.ck(declaration['tool_sha256']['fetch_news.py']==SHA(R/'tools/fetch_news.py'),'unchanged acquisition URL/parser implementation commitment','declaration')
 proxy={'topic_catalogue':declaration['catalogue_topics']};mapping,weekly,prefixes=initial_plan(proxy)
 a.ck(len(weekly)==declaration['weekly_context_count']and len(prefixes)==declaration['prefix_context_count']and len(mapping)==declaration['initial_physical_urls'],'independently rebuilt fixed catalogue/window/prefix cardinalities','declaration')
 return declaration,mapping,weekly,prefixes

def semantic_projection(a,rows,physical,fp,stage_only):
 policy=module('april_independent_finite_policy',R/'audit_work/independent_april_guard_policy.py')
 origin=READ(R/'audit_work/april_guard_snapshot_origin.json')
 a.ck(origin['owner_ready_tool_sha256']==SHA(R/'tools/ready_feeds.py')and origin['guard_policy_snapshot_sha256']==SHA(R/'audit_work/independent_april_guard_policy.py'),'explicit current finite-policy snapshot origin','policy_snapshot')
 observed=policy.DISPOSITIONS
 a.ck(len({(x['title'],x['guard'])for x in observed})==len(observed),'unique observed title/event dispositions','policy_snapshot')
 a.ck(all(x.get('disposition')in{'not_this_event','preview'}and x.get('reason')and x.get('reviewer')for x in observed),'explicit reason/reviewer for finite event identities','policy_snapshot')
 for g in policy.SCHEDULE['guards']:
  if g.get('release_utc'):a.ck(dt.datetime.fromisoformat(g['eligible_edition']).replace(tzinfo=UTC)>dt.datetime.fromisoformat(g['release_utc']),'eligible cutoff follows known release '+g['label'],'release_clocks')
  a.ck(bool(g.get('evidence')),'clock evidence reference '+g['label'],'release_clocks')
 coverage=READ(R/'audit/news_coverage.json');proof=[]
 for date in DATES:
  stamp=date.isoformat();cutoff=dt.datetime.combine(date,dt.time(),UTC)
  items,provenance,discard,failed,meta=own_cutoff_merge(a,date,rows,physical,fp)
  rawpath=R/('work/source_candidates/unreviewed_feeds'if stage_only else'work/unreviewed_feeds')/(stamp+'.json.gz')
  provpath=R/('work/source_candidates/news_provenance'if stage_only else'audit/news_provenance')/(stamp+'.json.gz')
  feedpath=R/('work/source_candidates/feeds'if stage_only else'feeds')/(stamp+'.json.gz')
  receiptpath=R/('work/source_candidates/ready_receipts'if stage_only else'audit')/('news_ready_'+stamp+'.json')
  raw,prov,feed,receipt=map(READ,[rawpath,provpath,feedpath,receiptpath])
  a.ck(raw['date']==stamp and dt.datetime.fromisoformat(raw['cutoff_utc'])==cutoff and raw['pipeline']==VERSION and raw['query_upper_bound_enforced']is True,stamp+' raw cutoff identity','projection')
  a.ck(not failed and raw['fails']==failed and raw['items']==items,stamp+' independent raw merge/order/IDs','projection')
  a.ck(prov['date']==stamp and dt.datetime.fromisoformat(prov['cutoff_utc'])==cutoff and prov['records']==provenance,stamp+' every physical request provenance membership','projection')
  row=next(x for x in coverage['dates']if x['date']==stamp)
  a.ck(row['items']==len(items)and row['excluded']==dict(discard),stamp+' independent raw merge/exclusion counts','projection')
  named={x['id']:x for x in policy.NAMED if x['date']==stamp};by_id={x['id']:x for x in items}
  for key,x in named.items():a.ck(key in by_id and all(by_id[key].get(k)==x[k]for k in ['id','title','published_at','src']),stamp+' named exact raw identity '+key,'named_exclusions')
  previews={x['title']for x in observed if x['disposition']=='preview'and x.get('applies_from_edition','0000-00-00')<=stamp}
  screened=[];removed=[];tightenings=[]
  for item in items:
   pub=dt.datetime.fromisoformat(item['published_at'])
   a.ck(cutoff-dt.timedelta(days=WIN[item['cat']])<=pub<cutoff,stamp+' '+item['id']+' initial semantic age','age')
   if item['title']in policy.OBSERVED_COMPANY_PREVIEWS or item['title']in previews:
    if pub<cutoff-dt.timedelta(days=7):removed.append({k:item[k]for k in ['id','published_at','src','title']}|{'guard':'Observed pending preview older than seven days','screen_kind':'semantic_age'});continue
    if item['cat']!='news':
     tightenings.append({'id':item['id'],'from_category':item['cat'],'to_category':'news','reason':'Exact independently reviewed pending preview; semantic seven-day window'});item={**item,'cat':'news'}
   if item['id']in named:removed.append(named[item['id']]);continue
   semantic_label=next((label for label,pattern in policy.SEMANTIC_GUARDS if pattern.search(item['title'])),None)
   hit=semantic_label or policy.guard_hit(item['title'],item['published_at'][:10],stamp)
   if hit:removed.append({k:item[k]for k in ['id','published_at','src','title']}|{'guard':hit,'screen_kind':'semantic'if semantic_label else'timing'})
   else:screened.append(item)
  effective=[g for g in policy.SCHEDULE['guards']if stamp<g['eligible_edition']and any(g['earliest_pub_date']<=x['published_at'][:10]<stamp and re.search(g['pattern'],x['title'],re.I)for x in items)]
  labels={g['label']for g in effective};titles={x['title']for x in items}
  effective_dispositions=[x for x in observed if x['title']in titles and x.get('applies_from_edition','0000-00-00')<=stamp and(x['guard']in labels or x['disposition']=='preview')]
  scoped={'date':stamp,'guards':effective,'named_exclusions':[x for x in policy.NAMED if x['date']==stamp],'observed_semantic_dispositions':effective_dispositions}
  expected={**raw,'items':screened,'canonical_screening':policy.CANONICAL_SCREENING,'release_guards_version':policy.GUARD_VERSION,'own_date_screen_policy_sha256':hashlib.sha256(COMPACT(scoped)).hexdigest(),'own_date_screen_policy':scoped}
  a.ck(feed==expected and SHA(feedpath)==hashlib.sha256(ENC(expected)).hexdigest(),stamp+' full independent ready projection bytes','screening')
  a.ck(receipt['date']==stamp and receipt['status']=='ready'and receipt['excluded']==removed and receipt['eligible_status_annotations']==[]and receipt['category_tightenings']==tightenings,stamp+' exact reviewed screen decisions','screening')
  a.ck(receipt['excluded_by_guard']==dict(collections.Counter(x['guard']for x in removed)),stamp+' exclusion grouping','screening')
  a.ck([receipt[k]for k in ['input_items','ready_items','excluded_items']]==[len(items),len(screened),len(removed)],stamp+' exact screening counts','screening')
  a.ck(receipt['ready_sha256']==SHA(feedpath)and receipt['unreviewed_sha256']==SHA(rawpath),stamp+' exact ready/raw receipt hashes','screening')
  for key,path in [('release_schedule_sha256','audit_work/april_release_schedule.json'),('named_exclusions_sha256','audit_work/april_named_source_exclusions.json'),('observed_semantic_dispositions_sha256','audit_work/april_observed_semantic_dispositions.json')]:a.ck(receipt[key]==SHA(R/path),stamp+' current complete policy receipt binding '+key,'screening')
  proof.append({'date':stamp,'raw_items':len(items),'ready_items':len(screened),'excluded':len(removed),'category_tightenings':len(tightenings),'feed_sha256':SHA(feedpath),'raw_sha256':SHA(rawpath),'provenance_sha256':SHA(provpath),'ready_receipt_sha256':SHA(receiptpath),'independent_merge_excluded':dict(discard),**meta})
  print(stamp,len(items),len(screened),'independent projection replay',flush=True)
 return proof,len(policy.SCHEDULE['guards'])

def verify_editorial(a,dateproof):
 extra=READ(R/'audit/additional_release_exclusions.json');seen=set()
 for row in dateproof:
  stamp=row['date'];feed=READ(R/'feeds'/(stamp+'.json.gz'));by={x['id']:x for x in feed['items']};record=READ(R/'exclusions'/(stamp+'.json'))
  a.ck(record['date']==stamp and record['feed_sha256']==row['feed_sha256'],stamp+' editorial ledger binds exact feed','editorial_exclusions')
  ids=[x['id']for x in record['exclusions']];a.ck(len(ids)==len(set(ids)),stamp+' unique editorial exclusions','editorial_exclusions')
  for x in record['exclusions']:
   a.ck(x['id']in by and all(x.get(k)==by[x['id']].get(k)for k in ['id','title','src','published_at']),stamp+' exact retained omitted headline '+x['id'],'editorial_exclusions')
   a.ck(bool(x.get('reason'))and x.get('feed_sha256')==row['feed_sha256'],stamp+' explicit editorial omission rationale '+x['id'],'editorial_exclusions');seen.add((stamp,x['id']))
 for x in extra['exclusions']:a.ck((x['date'],x['id'])in seen,'additional omission present in own-date ledger '+x['date']+'/'+x['id'],'editorial_exclusions')

def verify_final(a,dateproof,inventory):
 freeze=READ(R/'audit/source_freeze.json');semantic=READ(R/'audit_work/news_semantic_review.json');late=READ(R/'audit/independent_release_guard_review.json')
 a.ck(freeze['status']=='all_22_ready'and len(freeze['dates'])==22 and freeze['frozen_feeds_immutable']and freeze['candidates_all_compared_before_any_write'],'complete22-date immutable final freeze','final')
 a.ck(freeze['query_plan_sha256']==SHA(R/'audit/news_query_plan.json')and freeze['coverage_sha256']==SHA(R/'audit/news_coverage.json'),'final freeze plan/coverage binding','final')
 a.ck(semantic['status']=='completed'and type(semantic['fatal_or_major_remaining'])is int and semantic['fatal_or_major_remaining']==0,'actual completed root semantic review','final')
 a.ck(late.get('passed')is True and not late.get('errors')and type(late.get('fatal_or_major_remaining'))is int and late['fatal_or_major_remaining']==0,'actual independent finite-clock/guard review','final')
 for key,path in [('query_plan_sha256','audit/news_query_plan.json'),('release_schedule_sha256','audit_work/april_release_schedule.json'),('screening_tool_sha256','tools/ready_feeds.py'),('named_exclusions_sha256','audit_work/april_named_source_exclusions.json'),('observed_semantic_dispositions_sha256','audit_work/april_observed_semantic_dispositions.json'),('candidate_manifest_sha256','work/source_candidates/comparison_manifest.json'),('independent_release_guard_review_sha256','audit/independent_release_guard_review.json')]:a.ck(semantic[key]==SHA(R/path),'current semantic review '+key,'final')
 a.ck(freeze['semantic_review_sha256']==SHA(R/'audit_work/news_semantic_review.json')and freeze['physical_request_ledger_sha256']==SHA(R/'audit/news_physical_requests.jsonl'),'freeze semantic/physical binding','final')
 for relative,digest in late.get('input_bindings',{}).items():a.ck(SHA(a.safe(relative))==digest,'actual independent guard-review evidence '+relative,'final')
 spec=module('april_announced_integrity_review',R/'tools/announced_source_integrity.py')
 for row in dateproof:
  stamp=row['date'];old=READ(R/'audit'/('news_frozen_'+stamp+'.json'));spec.check_announced(stamp,old)
  a.ck(old['status']=='frozen_complete_own_date'and old['full_month_replay_verified']and not old['full_month_replay_pending'],'final immutable date '+stamp,'final')
  for actual,stage,key in [(R/'feeds',R/'work/source_candidates/feeds','feed_sha256'),(R/'work/unreviewed_feeds',R/'work/source_candidates/unreviewed_feeds','raw_sha256'),(R/'audit/news_provenance',R/'work/source_candidates/news_provenance','provenance_sha256')]:a.ck(SHA(actual/(stamp+'.json.gz'))==SHA(stage/(stamp+'.json.gz'))==row[key],stamp+' actual/staged exact '+key,'final')
  fr=next(x for x in freeze['dates']if x['date']==stamp);a.ck(fr['screened_sha256']==row['feed_sha256']and fr['screened_items']==row['ready_items'],'global date binding '+stamp,'final')
 expected=[{k:row[k]for k in ['date','feed_sha256','raw_sha256','ready_receipt_sha256','raw_items','ready_items','excluded']}for row in dateproof]
 a.ck(freeze['news_ready_dates']==expected,'global exact ready receipt rows','final')
 a.ck(freeze['input_bindings']=={'audit/news_ready_'+x['date']+'.json':x['ready_receipt_sha256']for x in dateproof},'global actual receipt hashes','final')
 market=READ(R/'audit/independent_market_review.json');cards={d.isoformat():SHA(R/'cards'/(d.isoformat()+'.json'))for d in DATES}
 a.ck(market.get('passed')is True and market.get('status')=='accepted'and not market.get('errors'),'actual accepted independent market review','market')
 a.ck(market.get('dates')==[d.isoformat()for d in DATES]and market.get('card_sha256')==cards,'all22 independently accepted market cards current','market')
 a.ck(market.get('source_freeze_sha256')==SHA(R/'audit/source_freeze.json'),'market proof rebinds current final source freeze','market')
 verify_editorial(a,dateproof);inventory.require_code_provenance()
 private=inventory.private_commitments();actual=inventory.scan_private_research()
 a.ck(list(private)==actual,'exact actual private original file scope, hash commitments only public','private_commitments')
 for name,row in private.items():a.ck(SHA(inventory.private_path(name))==row['sha256']and inventory.private_path(name).stat().st_size==row['bytes'],'retained exact private original '+name,'private_commitments')
 return cards

def refresh_coverage_scope(inventory):
 no_collectors();p=R/'audit/news_coverage.json';old=p.read_bytes();coverage=READ(p)
 plan=READ(R/'audit/news_query_plan.json');assert plan['status']=='all_requests_acquired_caps_resolved'and coverage['failed_requests']==0
 current=inventory.inspect_transport();counts=current['counts'];prior=R/'audit/source_amendments/coverage_transport_scope'/(hashlib.sha256(old).hexdigest()+'.json');prior.parent.mkdir(parents=True,exist_ok=True)
 if prior.exists():assert prior.read_bytes()==old
 else:prior.write_bytes(old)
 legacy=[x for x in coverage['limits']if 'Initial inherited HTTPError bodies were discarded'in x or 'up to16unloggedinflight'in x]
 coverage['limits']=[x for x in coverage['limits']if x not in legacy]
 statement=str(counts['journaled_interrupted_attempts'])+' journaled starts have unknown completion/status/body after environment interruptions; '+str(counts['recorded_missing_response_bodies'])+' completed transport failures exposed no response body. Exact recorded identities remain in acquisition_capture_limitation.json. Canonical planned queries each retain successful raw RSS; complete attempt-response byte retention is not asserted.'
 statement+=' '+str(READ(R/'audit_work/acquisition_capture_limitation.json').get('unattributed_error_body_objects',0))+' unattributed error-body objects are separately retained with original-path/hash commitments, without completed status or start attribution.'
 if statement not in coverage['limits']:coverage['limits'].append(statement)
 coverage['capture_limitation']={'path':'audit_work/acquisition_capture_limitation.json','sha256':SHA(R/'audit_work/acquisition_capture_limitation.json')}
 coverage['transport_scope_amendment']={'prior_coverage_path':prior.relative_to(R).as_posix(),'prior_coverage_sha256':SHA(prior),'reason':'Earlier in-memory collector retained inherited narrative boilerplate; this explicit amendment reconciles actual journal/body scope without changing request or source records.','removed_legacy_statements':legacy,'actual_transport_counts':counts}
 write(p,coverage);print(json.dumps({'coverage_sha256':SHA(p),'transport_scope_amended':True,'source_records_changed':False},indent=2))

def unattributed_body_evidence(a=None):
 path=R/'audit/source_amendments/unattributed_attempt_bodies/manifest.json';record=READ(path)
 assert record['status']=='retained_unattributed_error_body_objects'and record['count']==len(record['files'])==16
 paths=[path];seen=set()
 for row in record['files']:
  original=R/row['original_path'];preserved=R/row['preserved_path']
  assert row['original_path'].startswith('cache/rss_raw/attempts/')and row['preserved_path'].startswith('audit/source_amendments/unattributed_attempt_bodies/')
  assert not original.exists()and preserved.is_file()and not preserved.is_symlink()and row['preserved_path']not in seen
  seen.add(row['preserved_path']);blob=preserved.read_bytes();raw=gzip.decompress(blob)
  assert SHA(preserved)==row['sha256']and hashlib.sha256(raw).hexdigest()==row['uncompressed_sha256']and len(blob)==row['bytes']and len(raw)==row['uncompressed_bytes']
  paths.append(preserved)
 limit=READ(R/'audit_work/acquisition_capture_limitation.json')
 assert limit['unattributed_error_body_objects']==16 and limit['unattributed_error_body_manifest']==path.relative_to(R).as_posix()and limit['unattributed_error_body_manifest_sha256']==SHA(path)
 return paths,{'unattributed_error_body_objects':16,'unattributed_error_body_manifest':path.relative_to(R).as_posix(),'unattributed_error_body_manifest_sha256':SHA(path)}


def base_paths():
 names=['audit/news_query_plan.json','audit/news_physical_requests.jsonl','audit/news_physical_attempt_starts.jsonl','audit_work/acquisition_capture_limitation.json','audit_work/news_catalogue_declaration.json','tools/fetch_news.py','tools/topics.py','tools/expand_capped_news.py','audit_work/review_sources.py','tools/build_source_inventory.py']
 extra,_=unattributed_body_evidence()
 return[R/name for name in names]+extra

def physical_stage(a,plan,mapping,fp,inventory):
 a.ck(plan['status']=='all_requests_acquired_caps_resolved','all logical queries fetched and caps closed','plan')
 if a.errors:raise ValueError('Incomplete physical query plan: '+repr(a.errors))
 before=bind(base_paths());physical,index,stats=physical_replay(a,plan['requests'],fp);refinement_replay(a,mapping,physical,plan)
 transport=inventory.inspect_transport();limitation=READ(R/'audit_work/acquisition_capture_limitation.json')
 a.ck(limitation.get('affected_attempts')==transport['missing_attempts']and limitation.get('recorded_failed_attempts_missing_bodies')==len(transport['missing_attempts']),'actual completed no-exposed-body disclosure reconciled; use --refresh-capture-disclosure first','transport')
 output=R/'audit_work/physical_source_inventory.json';write(output,transport['inventory'])
 for name,digest in before.items():a.ck(SHA(R/name)==digest,'stable during physical replay '+name,'concurrency')
 _,unattributed=unattributed_body_evidence()
 counts={**transport['counts'],**unattributed,'physical_source_inventory_sha256':SHA(output),'discarded_error_body_limitations_sha256':SHA(R/'audit_work/acquisition_capture_limitation.json')}
 receipt={'status':'physical_infrastructure_replay_passed'if not a.errors else'physical_infrastructure_replay_failed','passed':not a.errors,'authoring_acceptance':False,'checked_at_utc':dt.datetime.now(UTC).isoformat(),'dates':[d.isoformat()for d in DATES],'checks':sum(a.counts.values()),'checks_by_scope':dict(a.counts),'errors':a.errors,'reviewer_tool_sha256':SHA(Path(__file__)),'input_bindings':before,**counts,**stats,'independently_xml_reparsed_signatures':len(physical),'scope':'Independent exact request URL/XML/parser/cap graph and every recorded body/start/completion replay. Successful canonical RSS complete; explicit journaled interruptions and completed no-exposed-body failures remain disclosed. No article-vintage, report-fact or authoring acceptance.'}
 write(R/'audit/independent_physical_source_review.json',receipt)
 return physical,receipt

def staged_bindings(dateproof,stage_only):
 paths=[]
 for row in dateproof:
  stamp=row['date'];paths.extend([R/('work/source_candidates/feeds'if stage_only else'feeds')/(stamp+'.json.gz'),R/('work/source_candidates/unreviewed_feeds'if stage_only else'work/unreviewed_feeds')/(stamp+'.json.gz'),R/('work/source_candidates/news_provenance'if stage_only else'audit/news_provenance')/(stamp+'.json.gz'),R/('work/source_candidates/ready_receipts'if stage_only else'audit')/('news_ready_'+stamp+'.json')])
 return paths

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--plan-only',action='store_true');ap.add_argument('--physical-only',action='store_true');ap.add_argument('--stage-only',action='store_true');ap.add_argument('--accept',action='store_true');ap.add_argument('--reuse-physical',action='store_true');ap.add_argument('--refresh-capture-disclosure',action='store_true');ap.add_argument('--refresh-private-commitments',action='store_true');ap.add_argument('--refresh-coverage-transport-scope',action='store_true');args=ap.parse_args()
 sys.path.insert(0,str(R/'tools'));inventory=module('april_source_inventory_engineering',R/'tools/build_source_inventory.py')
 if args.refresh_capture_disclosure:refresh_capture_disclosure();return
 if args.refresh_private_commitments:refresh_private_commitments(inventory);return
 if args.refresh_coverage_transport_scope:refresh_coverage_scope(inventory);return
 a=Audit();declaration,mapping,weekly,prefixes=catalogue(a);plan=READ(R/'audit/news_query_plan.json')
 if args.plan_only:
  a.ck(plan['dates']==[d.isoformat()for d in DATES]and plan['version']==VERSION,'current exact22-date plan identity','plan')
  for row in plan['requests']:
   for context in row['contexts']:a.ck(request(context['job'])[:2]==(row['signature'],row['request_url']),'exact URL/context signature '+row['signature'],'plan')
  out={'status':'declared_plan_verified_full_acquisition_and_semantic_replay_pending','passed':False,'design_checks_passed':not a.errors,'authoring_acceptance':False,'checked_at_utc':dt.datetime.now(UTC).isoformat(),'checks':sum(a.counts.values()),'errors':a.errors,'physical_urls':len(plan['requests']),'base_urls':len(mapping),'dates':[d.isoformat()for d in DATES],'reviewer_tool_sha256':SHA(Path(__file__)),'input_bindings':bind(base_paths()),'limits':['Declaration metadata was written immediately after collector launch; its own note disclaims an earlier signed timestamp. Fixed catalogue/URL/parser bytes and actual response replay are checked separately.','Current plan may still be incomplete; this design receipt never grants source acceptance.']};write(R/'audit/independent_source_design_review.json',out);print(json.dumps({k:v for k,v in out.items()if k not in['input_bindings','dates']},indent=2));return
 no_collectors()
 if plan.get('status')!='all_requests_acquired_caps_resolved':raise ValueError('All required queries must succeed and caps resolve before physical/staged/final replay')
 fp=semantic_patterns()
 if args.reuse_physical:
  prior=READ(R/'audit/independent_physical_source_review.json');inventory.require_physical_ledger(prior,physical_review_only=True)
  a.ck(prior.get('reviewer_tool_sha256')==SHA(Path(__file__))and prior.get('independently_xml_reparsed_signatures')==len(plan['requests']),'current reviewer exact independent XML proof reusable','physical_reuse')
  physical={x['signature']:READ(R/x['cache_path'])for x in plan['requests']};refinement_replay(a,mapping,physical,plan)
 else:physical,prior=physical_stage(a,plan,mapping,fp,inventory)
 if args.physical_only:
  print(json.dumps({'status':prior['status'],'passed':prior['passed'],'physical_requests':prior['physical_requests'],'journaled_interrupted_attempts':prior['journaled_interrupted_attempts'],'recorded_missing_response_bodies':prior['recorded_missing_response_bodies'],'errors':a.errors},indent=2));return
 coverage=READ(R/'audit/news_coverage.json');a.ck(coverage['failed_requests']==0 and coverage['unresolved_capped_requests']==0 and coverage['query_plan_sha256']==SHA(R/'audit/news_query_plan.json'),'complete current coverage','coverage')
 a.ck(not any('up to16unloggedinflight'in x or 'Initial inherited HTTPError bodies were discarded'in x for x in coverage.get('limits',[])),'inherited capture boilerplate reconciled to actual April transport scope','coverage')
 dependency_names=['independent_april_guard_policy.py','april_guard_snapshot_origin.json','april_release_schedule.json','april_named_source_exclusions.json','april_observed_semantic_dispositions.json','april_source_tool_adaptation.json','acquisition_capture_limitation.json','news_catalogue_declaration.json']
 tools={p.name:SHA(p)for p in sorted((R/'tools').glob('*.py'))};contracts={name:SHA(R/name)for name in ['AUTHORING.md','BRIEF.md']};dependencies={name:SHA(R/'audit_work'/name)for name in dependency_names}
 core=base_paths()+[R/'audit/news_coverage.json',R/'audit/independent_physical_source_review.json',R/'audit_work/physical_source_inventory.json',R/'work/source_candidates/comparison_manifest.json',R/'source/lambda_function.py',R/'code_provenance.json']+[R/'tools'/name for name in tools]+[R/name for name in contracts]+[R/'audit_work'/name for name in dependencies]
 before=bind(core);dateproof,guard_count=semantic_projection(a,plan['requests'],physical,fp,args.stage_only)
 manifest=READ(R/'work/source_candidates/comparison_manifest.json');a.ck(manifest['status']=='all_22_compared_before_destination_write'and[x['date']for x in manifest['dates']]==[d.isoformat()for d in DATES],'all66 actual staged candidates compared','stage')
 a.ck(manifest['query_plan_sha256']==SHA(R/'audit/news_query_plan.json'),'candidate manifest current physical plan','stage')
 for name,digest in manifest['tool_sha256'].items():a.ck(SHA(R/'tools'/name)==digest,'candidate exact current pipeline code '+name,'stage')
 for row in manifest['dates']:
  for key,folder in [('raw_candidate_sha256','unreviewed_feeds'),('ready_candidate_sha256','feeds'),('provenance_candidate_sha256','news_provenance')]:a.ck(row[key]==SHA(R/'work/source_candidates'/folder/(row['date']+'.json.gz')),'actual staged candidate '+row['date']+'/'+folder,'stage')
 before.update(bind(staged_bindings(dateproof,args.stage_only)));card_hashes={}
 if not args.stage_only:
  card_hashes=verify_final(a,dateproof,inventory)
  finalpaths=[R/'audit/source_freeze.json',R/'audit_work/news_semantic_review.json',R/'audit/independent_release_guard_review.json',R/'audit/independent_market_review.json',R/'audit/additional_release_exclusions.json',R/inventory.PRIVATE_MANIFEST]
  for date in DATES:
   stamp=date.isoformat();finalpaths.extend([R/'cards'/(stamp+'.json'),R/'exclusions'/(stamp+'.json'),R/'audit'/('news_frozen_'+stamp+'.json')])
  finalpaths.extend(p for p in(R/'audit/source_amendments').rglob('*')if p.is_file()and '__pycache__'not in p.parts)
  late=READ(R/'audit/independent_release_guard_review.json');finalpaths.extend(a.safe(name)for name in late.get('input_bindings',{}))
  before.update(bind(finalpaths))
 for name,digest in before.items():a.ck(SHA(R/name)==digest,'stable through source replay '+name,'concurrency')
 counts={k:prior[k]for k in inventory.TRANSPORT_FIELDS if k in prior}
 counts.update({k:prior[k]for k in ['unattributed_error_body_objects','unattributed_error_body_manifest','unattributed_error_body_manifest_sha256']})
 out={'status':('staged_infrastructure_verified'if args.stage_only else'accepted_for_authoring_with_semantic_exclusions')if not a.errors else'failed','passed':not a.errors,'infrastructure_status':'accepted'if not a.errors else'failed','semantic_status':'requires_own_claim_review','authoring_acceptance':bool(args.accept and not args.stage_only and not a.errors),'checked_at_utc':dt.datetime.now(UTC).isoformat(),'scope':'Independent April request/XML/parser/cap/own-cutoff raw merge/IDs/provenance and explicit finite-policy snapshot projection replay. Root manual clock/semantic receipt remains required. No report-fact or original publisher-vintage approval.','checks':sum(a.counts.values()),'checks_by_scope':dict(a.counts),'errors':a.errors,'structural_errors':len(a.errors),'pending_dates':0 if not a.errors else 22,'dates':dateproof,**counts,'observed_capped_requests':sum(bool(x['possibly_capped'])for x in plan['requests']),'refinement_contexts':sum(c['kind']in{'daily_refinement','term_refinement'}for row in plan['requests']for c in row['contexts']),'remaining_daily_caps':0,'remaining_daily_cap_signatures':[],'failed_queries':sum(x['status']!='fetched'for x in physical.values()),'prior_physical_review_sha256':SHA(R/'audit/independent_physical_source_review.json'),'source_freeze_sha256':SHA(R/'audit/source_freeze.json')if not args.stage_only else None,'card_sha256':card_hashes,'independent_market_review_sha256':SHA(R/'audit/independent_market_review.json')if not args.stage_only else None,'tool_sha256':tools,'contract_sha256':contracts,'reviewer_dependency_sha256':dependencies,'reviewer_tool_sha256':SHA(Path(__file__)),'declared_release_guards_extracted':guard_count,'input_bindings':before,'limits':['Exact journaled interruptions and completed no-exposed-response failures remain in the capture disclosure. Canonical planned RSS success does not imply complete physical-attempt response retention.','Historical RSS/search bytes are retained, not original contemporaneous publisher or article-body vintages.','Finite policy snapshot is explicit reviewed implementation context; semantic facts, social claims and actual-versus-preview correctness still need own-date editorial review.','Raw private research originals remain outside ROOT; the public archive contains only exact hash commitments and separately reviewed compact clock metadata.']}
 target=R/'audit_work'/('independent_staged_source_review.json'if args.stage_only else'source_review_draft.json');write(target,out)
 if args.accept:
  if args.stage_only or a.errors:raise ValueError('Staged/failed replay cannot grant final authoring acceptance')
  inventory.require_ready_receipts(out);inventory.require_physical_ledger(out);inventory.require_code_provenance(out)
  write(R/'audit/independent_source_review.json',out)
 print(json.dumps({'status':out['status'],'passed':out['passed'],'authoring_acceptance':out['authoring_acceptance'],'dates':len(dateproof),'physical_requests':out.get('physical_requests'),'checks':out['checks'],'errors':a.errors},indent=2))
 if a.errors:raise SystemExit(1)
if __name__=='__main__':
 try:main()
 except (ValueError,AssertionError,KeyError,FileNotFoundError)as exc:
  print(json.dumps({'status':'source_replay_blocked','passed':False,'authoring_acceptance':False,'error_type':type(exc).__name__,'error':str(exc)},indent=2));raise SystemExit(1)
