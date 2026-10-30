"""Screen and freeze April own-date feeds after complete prefix/daily acquisition.

Selected priority Reuters canonical URL dates and targeted high-risk release guards
are conservative filters. Publisher bodies and original historical vintages are not
asserted. Native metadata uses public news.google.com routes only; challenges stop
new requests. Unresolved transport failures block final freeze, rather than silently
shrinking coverage. Records with resolved but undated canonical URLs are omitted.
"""
from __future__ import annotations
import argparse, concurrent.futures as cf, datetime as dt,gzip,hashlib,importlib.util,json,re,sys,threading,time,urllib.parse
from pathlib import Path
from collections import Counter
from fetch_news import ROOT,WIN,atomic_json
from digest import rank
DATES=[dt.date(2025,4,n) for n in range(1,31) if dt.date(2025,4,n).weekday()<5]
META=ROOT/'audit/canonical_all_cited_urls.json'
RESOLVER=ROOT/'posthoc/resolve_news_url.py'
sp=importlib.util.spec_from_file_location('news_metadata_resolver',RESOLVER);resolver=importlib.util.module_from_spec(sp);sp.loader.exec_module(resolver)
CAPS={'us_macro':35,'us_data':35,'europe':35,'china':55,'japan':30,'australia':30,'poland_en':30,'poland_pl':55,'sectors':65,'earnings':65,'crypto':35,'flows':35,'retail':60,'geo':30,'calendar':15}
PREVIEW=re.compile(r'\b(?:preview|previews|ahead of|week ahead|what to expect|expected|expects?|forecast|forecasts|forecasting|will|would|might|could|may|should|likely|seen|set to|due|awaits?|waiting|on hold ahead|decision day|to (?:hold|cut|raise|leave|keep|release|report|meet))\b',re.I)
# First eligible 00:00 UTC report after the scheduled publication. Japanese
# 08:30/08:50 JST releases can precede UTC midnight and have no blanket same-day
# prohibition here. The cited-source audit still requires their intraday proof.
RELEASE_GUARDS=[
 ('RBA April minutes','2025-04-09','2025-04-16',r'(?=.*(?:RBA|Reserve Bank of Australia))(?=.*minutes)(?=.*(?:April|Apr\b|tariff|uncertain))'),
 ('Poland March wages and employment','2025-04-16','2025-04-23',r'(?=.*(?:Poland|Polish|Polsk|GUS|wynagrodz|zatrudn))(?=.*(?:wages|salary|employment|wynagrodz|zatrudn))(?=.*(?:March|marc))'),
 ('Poland March industry','2025-04-16','2025-04-23',r'(?=.*(?:Poland|Polish|Polsk|GUS|przemysł))(?=.*(?:industrial|industry|produkcj.*przemysł|przemysł.*produkcj))(?=.*(?:March|marc))'),
 ('Poland March retail sales','2025-04-17','2025-04-24',r'(?=.*(?:Poland|Polish|Polsk|GUS|sprzedaż|sprzedaz))(?=.*(?:retail sales|sprzedaż detal|sprzedaz detal))(?=.*(?:March|marc))'),
 ('Nvidia H20 license and expected charge','2025-04-09','2025-04-16',r'(?=.*Nvidia)(?=.*H20)(?=.*(?:licen[cs]e|5[.,]5|charge))'),
 ('April electronics tariff clarification','2025-04-09','2025-04-14',r'(?=.*(?:Trump|U\.?S\.?))(?=.*(?:tariff))(?=.*(?:smartphone|computer|electronics))(?=.*(?:exempts?|exemptions?|excluded|exclusions?))'),
 ('RBA April decision','2025-03-27','2025-04-02',r'(?=.*(?:RBA|Reserve Bank of Australia))(?=.*(?:holds?|held|keeps?|kept|leaves?|left|decision|rates steady|unchanged))'),
 ('US March ISM manufacturing','2025-03-27','2025-04-02',r'(?=.*(?:ISM|Institute for Supply Management))(?=.*(?:manufactur|factory))(?=.*(?:March|Mar\b|contract|49[.,]0))'),
 ('US February JOLTS','2025-03-27','2025-04-02',r'(?=.*(?:JOLTS|job openings))(?=.*(?:February|Feb\b|7[.,]568|7[.,]57))'),
 ('April reciprocal tariff announcement','2025-03-30','2025-04-03',r'(?=.*(?:Trump|U\.?S\.?))(?=.*(?:tariff))(?=.*(?:10% baseline|10 percent baseline|34%|34 percent|20%.*EU|20 percent.*EU|unveils reciprocal|announces reciprocal))'),
 ('NBP April decision','2025-03-28','2025-04-03',r'(?=.*(?:NBP|RPP|Poland|Polish|Glapiński))(?=.*(?:(?:holds?|held) rates|(?:keeps?|kept) rates|(?:leaves?|left) rates|unchanged|bez zmian|utrzyma))'),
 ('US March ADP','2025-03-28','2025-04-03',r'(?=.*ADP)(?=.*(?:March|Mar\b|155,000|155000))'),
 ('US March ISM services','2025-03-28','2025-04-04',r'(?=.*(?:ISM|Institute for Supply Management))(?=.*services)(?=.*(?:March|Mar\b|50[.,]8))'),
 ('US March payrolls','2025-03-30','2025-04-07',r'(?=.*(?:U\.?S\.?|American|nonfarm|payroll|jobs report))(?=.*(?:jobs|payroll|unemployment|hiring))(?=.*(?:March|Mar\b|228,000|228000))'),
 ('China March inflation','2025-04-04','2025-04-11',r'(?=.*China)(?=.*(?:CPI|PPI|inflation|deflation|consumer prices|producer prices))(?=.*(?:March|Mar\b))'),
 ('US March CPI','2025-04-04','2025-04-11',r'(?=.*(?:U\.?S\.?|American|Fed))(?=.*(?:CPI|inflation|consumer prices))(?=.*(?:March|Mar\b))'),
 ('US March PPI','2025-04-05','2025-04-14',r'(?=.*(?:U\.?S\.?|American|PPI))(?=.*(?:PPI|producer prices|wholesale prices))(?=.*(?:March|Mar\b))'),
 ('April ninety-day reciprocal pause','2025-04-03','2025-04-10',r'(?=.*(?:Trump|U\.?S\.?))(?=.*tariff)(?=.*(?:90.day pause|90.day suspension|pauses.*90|pause.*90.days))'),
 ('China March trade','2025-04-08','2025-04-15',r'(?=.*China)(?=.*(?:exports|imports|trade surplus|trade data))(?=.*(?:March|Mar\b|12[.,]4))'),
 ('China Q1 GDP','2025-04-10','2025-04-17',r'(?=.*China)(?=.*(?:GDP|gross domestic product|economy|growth))(?=.*(?:Q1|first.quarter|1st.quarter))'),
 ('China March activity','2025-04-10','2025-04-17',r'(?=.*China)(?=.*(?:retail sales|industrial (?:output|production)|fixed.asset|home prices))(?=.*(?:March|Mar\b))'),
 ('US March retail sales','2025-04-10','2025-04-17',r'(?=.*(?:U\.?S\.?|American))(?=.*retail sales)(?=.*(?:March|Mar\b))'),
 ('ECB April decision','2025-04-11','2025-04-18',r'(?=.*(?:ECB|European Central Bank))(?=.*(?:cuts?|cut|holds?|held|keeps?|kept|leaves?|left|decision|interest rates))'),
 ('Australia March employment','2025-04-11','2025-04-18',r'(?=.*Australia)(?=.*(?:jobs|employment|unemployment|hiring))(?=.*(?:March|Mar\b))'),
 ('China April LPR','2025-04-15','2025-04-22',r'(?=.*(?:China|PBOC))(?=.*(?:loan prime|benchmark lending|LPR))(?=.*(?:April|unchanged|holds?|keeps?))'),
 ('April flash PMIs','2025-04-17','2025-04-24',r'(?=.*(?:PMI|purchasing managers|business activity))(?=.*(?:April|flash))(?=.*(?:euro\s?zone|Germany|German|France|French|Britain|British|UK|U\.?S\.?|S&P Global))'),
 ('US Q1 GDP advance','2025-04-24','2025-05-01',r'(?=.*(?:U\.?S\.?|American))(?=.*(?:GDP|gross domestic product|economy|growth))(?=.*(?:Q1|first.quarter|1st.quarter))(?=.*(?:shrinks?|contract|negative|0[.,]3|advance|first estimate))'),
 ('US March PCE','2025-04-24','2025-05-01',r'(?=.*(?:PCE|personal consumption expenditure))(?=.*(?:March|Mar\b))'),
 ('Australia Q1 CPI','2025-04-24','2025-05-01',r'(?=.*Australia)(?=.*(?:CPI|inflation|consumer prices))(?=.*(?:Q1|quarter|March|Mar\b))'),
 ('China April official PMI','2025-04-24','2025-05-01',r'(?=.*China)(?=.*(?:PMI|purchasing manager|factory activity))(?=.*(?:April|Apr\b|49[.,]0))'),
 ('Poland April flash CPI','2025-04-24','2025-05-01',r'(?=.*(?:Poland|Polish|Polsce|Polski|inflacja|inflacji))(?=.*(?:CPI|inflation|consumer prices|inflacja|inflacji))(?=.*(?:April|kwiet))'),
]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
 raw=p.read_bytes();return json.loads(gzip.decompress(raw)if p.suffix=='.gz'else raw)
def is_reuters(x):return x['src'].casefold().strip()in('reuters','reuters.com')or x['title'].casefold().endswith(' - reuters')
def selected(items):
 ids=set()
 for topic,cap in CAPS.items():ids.update(x['id']for x in sorted([x for x in items if x['topics'][0]==topic],key=rank)[:cap])
 return[x for x in items if x['id']in ids and is_reuters(x)]
def completed_action(label,title):
 """A later clause's modal does not turn an already completed release into a preview.

 Only a completed subject/action pair with no prospective qualifier before that
 action overrides the global preview marker. Uncertain clauses stay previews.
 """
 if label=='RBA April minutes':
  subject=r'minutes';action=r'shows?|showed|reveals?|revealed|says?|said|signals?|indicates?|indicated|suggests?|suggested|released|published'
 elif label.startswith('RBA'):subject=r'RBA|Reserve Bank of Australia';action=None
 elif label.startswith('ECB'):subject=r'ECB|European Central Bank';action=None
 elif label.startswith('NBP'):subject=r'NBP|RPP|Glapiński|central bank';action=None
 elif 'ISM'in label:subject=r'ISM|Institute for Supply Management';action=None
 elif 'JOLTS'in label:subject=r'JOLTS|job openings';action=None
 elif 'ADP'in label:subject=r'ADP|private payrolls|private employment';action=None
 elif 'payrolls'in label:subject=r'payrolls?|nonfarm|employment|jobs report|hiring';action=None
 elif 'CPI'in label or'inflation'in label:subject=r'CPI|inflation|consumer prices|PPI|producer prices';action=None
 elif 'PPI'in label:subject=r'PPI|producer prices|wholesale prices';action=None
 elif 'GDP'in label:subject=r'GDP|gross domestic product|economy';action=None
 elif 'PCE'in label:subject=r'PCE|personal consumption expenditure|personal spending|personal income';action=None
 elif 'retail sales'in label:subject=r'retail sales|sprzeda[żz] detal\w*';action=None
 elif label=='China March trade':subject=r'exports?|imports?|trade surplus|trade data';action=None
 elif label=='China March activity':subject=r'retail sales|industrial output|industrial production|fixed.asset investment|home prices';action=None
 elif 'LPR'in label:subject=r'LPR|loan prime rates?|benchmark lending rates?';action=None
 elif 'PMI'in label:subject=r'PMI|purchasing managers|factory activity|business activity';action=None
 elif 'wages'in label:subject=r'wages|salary|employment|wynagrodz\w*|zatrudn\w*';action=None
 elif 'industry'in label:subject=r'industrial output|industrial production|industry|produkcj\w*|przemysł\w*';action=None
 elif 'employment'in label:subject=r'jobs|employment|unemployment|hiring';action=None
 elif 'tariff'in label.lower()or'electronics'in label.lower():subject=r'Trump|U\.?S\.?';action=None
 else:return False
 if action is None:action=r'holds?|held|keeps?|kept|leaves?|left|cuts?|raises?|raised|maintains?|maintained|falls?|fell|falling|rises?|rose|rising|cools?|cooled|grows?|grew|contracts?|contracted|shrinks?|shrank|surges?|surged|slows?|slowed|drops?|dropped|jumps?|jumped|pauses?|paused|announces?|announced|unveils?|unveiled|exempts?|exempted|down|up|wzrosł\w*|spadł\w*|utrzyma\w*|pozostawi\w*'
 pattern=re.compile(r'\b(?:'+subject+r')\b(?P<before>(?:(?!\b(?:but|while|whereas|although|yet|and)\b)[^.;:]){0,100}?)\b(?:'+action+r')\b',re.I)
 for match in pattern.finditer(title):
  # Include qualifiers before the subject in its own clause (e.g. analysts
  # expect US CPI to fall), while discarding unrelated earlier clauses.
  prefix=re.split(r'[;,:]|\b(?:but|while|whereas|although|yet)\b',title[:match.end('before')],flags=re.I)[-1]
  country={'US':r'\b(?:U\.?S\.?|American)\b','China':r'\b(?:China|Chinese)\b','Australia':r'\b(?:Australia|Australian|ABS)\b','Poland':r'\b(?:Poland|Polish|Polsk\w*|GUS)\b'}
  group=next((name for name in country if label.startswith(name)),None)
  implicit_us=any(word in label for word in ['ISM','JOLTS','ADP','payrolls'])
  if group and not(group=='US'and implicit_us)and not re.search(country[group],prefix,re.I):continue
  if PREVIEW.search(prefix)or re.search(r'\b(?:to|will|would|could|should|may|might)\s*$',prefix,re.I):continue
  if re.search(r'\b(?:prognoz|oczekuj|oczekiw|może|moze|mogą|moga|mają|maja|powinn|będ|beda|wzrosn|spadn|spodziew|prawdopodob|zapowied|szacuj)',prefix,re.I):continue
  return True
 return False

def release_guard_reason(item,stamp):
 title=item['title'];published=item['published_at'][:10]
 # The expected expense is prospective, but the issuer disclosure is completed.
 if '2025-04-09'<=published<'2025-04-16'and stamp<'2025-04-16'and re.search(r'(?=.*Nvidia)(?=.*5[.,]5)(?=.*charge)',title,re.I):
  disclosure=re.search(r'\bNvidia\b(?P<before>[^,;:.]{0,60}?)\b(?:expects?|discloses?|reports?|flags?|warns?)\b',title,re.I)
  if disclosure:
   prefix=re.split(r'[;,:]|\b(?:but|while|whereas|although|yet)\b',title[:disclosure.end('before')],flags=re.I)[-1]
   if not PREVIEW.search(prefix)and not re.search(r'\bto\s*$',prefix,re.I):return 'Nvidia expected $5.5 billion charge disclosure unavailable until 2025-04-16 report'
 preview_title=re.sub(r'\b(?:better|worse|more|less|higher|lower|stronger|weaker|faster|slower)\s+than\s+expected\b|\bas\s+expected\b','',title,flags=re.I)
 preview_title=re.sub(r'\b(?:mocniej|słabiej|lepiej|gorzej|więcej|mniej|wyżej|niżej)\s+(?:od|niż)\s+(?:oczekiwań|oczekiwano|prognoz(?:owano)?)','',preview_title,flags=re.I)
 preview=bool(PREVIEW.search(preview_title)or re.search(r'\b(?:prognoz|oczekuj|oczekiw|może|moze|mogą|moga|mają|maja|powinn|będ|beda|wzrosn|spadn|spodziew|prawdopodob|zapowied|szacuj)',preview_title,re.I))
 for label,start,eligible,pattern in RELEASE_GUARDS:
  if start<=published<eligible and stamp<eligible and re.search(pattern,title,re.I):
   if preview and not completed_action(label,preview_title):continue
   return label+' actual may precede scheduled release; excluded until '+eligible+' report'
 return None

def metadata_plan():
 rows=[];urls=set()
 for date in DATES:
  stamp=date.isoformat();path=ROOT/'work/unreviewed_feeds'/(stamp+'.json.gz');feed=read(path);priority=selected(feed['items']);urls.update(x['url']for x in priority)
  rows.append({'date':stamp,'raw_feed_sha256':sha(path),'raw_items':len(feed['items']),'priority_reuters_records':len(priority),'priority_ids':[x['id']for x in priority]})
 out={'version':'apr-priority-metadata-v2-full-timestamp','urls':sorted(urls),'url_count':len(urls),'dates':rows,'ranking_helper_sha256':sha(ROOT/'tools/digest.py'),'scope':'Selected priority Reuters URL-date screen only. No publisher bodies or exact original article publication times.'}
 atomic_json(ROOT/'audit/news_metadata_request_plan.json',out);return out

STOP=threading.Event()
def metadata(url):
 if STOP.is_set():return url,None
 try:
  canonical=resolver.resolve(url);match=re.search(r'(\d{4}-\d{2}-\d{2})/?$',urllib.parse.urlparse(canonical).path)
  return url,{'canonical_url':canonical,'canonical_date':match.group(1)if match else None,'observed_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'publisher_body_fetched':False,'transport':'native_google_news_metadata'}
 except Exception as exc:
  if isinstance(exc,resolver.CanonicalRedirect):
   parsed=urllib.parse.urlsplit(exc.url);error=f'{type(exc).__name__}: {parsed.scheme}://{parsed.hostname}{parsed.path} (query omitted)'
  else:error=f'{type(exc).__name__}: {exc}'
  # A challenge is a service-side control, not a signal to change proxy/TLS or
  # repeatedly probe signing routes. Remaining URLs are left for reviewed recovery.
  STOP.set();return url,{'error':error,'observed_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'publisher_body_fetched':False}

def resolve_metadata(workers):
 plan=metadata_plan();cache=read(META)if META.exists()else{}
 missing=[u for u in plan['urls']if u not in cache or cache[u].get('error')]
 print('priority unique URLs',len(plan['urls']),'missing',len(missing),'workers',workers,flush=True)
 preflight_path=ROOT/'audit/metadata_native_preflight.json'
 if preflight_path.exists()and read(preflight_path).get('result',{}).get('error'):STOP.set()
 with cf.ThreadPoolExecutor(max_workers=workers)as pool:
  for n,(url,result)in enumerate(pool.map(metadata,missing),1):
   if result is not None:cache[url]=result
   if n%20==0:atomic_json(META,cache);print(n,'/',len(missing),'cache',len(cache),'stopped',STOP.is_set(),flush=True)
 atomic_json(META,cache)
 unresolved=[u for u in plan['urls']if u not in cache or cache[u].get('error')]
 out={'observed_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'requested_priority_urls':len(plan['urls']),'unresolved_urls':unresolved,'unresolved_count':len(unresolved),'native_stop_on_first_error':True,'metadata_plan_sha256':sha(ROOT/'audit/news_metadata_request_plan.json'),'scope':'Public canonical metadata; transport errors block freeze and require reviewed recovery.'}
 atomic_json(ROOT/'audit/news_metadata_transport.json',out);print('metadata unresolved',len(unresolved),flush=True)
 return out

def freeze():
 coverage=read(ROOT/'audit/news_coverage.json');assert coverage['status']=='acquired_verified'and coverage['failed_requests']==0
 plan=metadata_plan();cache=read(META)if META.exists()else{}
 unresolved=[u for u in plan['urls']if u not in cache or cache[u].get('error')]
 if unresolved:raise SystemExit(str(len(unresolved))+' priority canonical URLs unresolved; final freeze blocked')
 priority_snapshot={u:cache[u]for u in plan['urls']}
 snapshot_path=ROOT/'audit/canonical_priority_urls.json'
 atomic_json(snapshot_path,priority_snapshot)
 rows=[]
 for date in DATES:
  stamp=date.isoformat();rawpath=ROOT/'work/unreviewed_feeds'/(stamp+'.json.gz');feed=read(rawpath);cutoff=dt.datetime.combine(date,dt.time(),dt.timezone.utc)
  assert feed['date']==stamp and dt.datetime.fromisoformat(feed['cutoff_utc'])==cutoff and feed['query_upper_bound_enforced']and not feed['fails']
  prioritized={x['id']for x in selected(feed['items'])};ready=[];excluded=[]
  for item in feed['items']:
   pub=dt.datetime.fromisoformat(item['published_at']);assert cutoff-dt.timedelta(days=WIN[item['cat']])<=pub<cutoff
   result=priority_snapshot.get(item['url'],{})if is_reuters(item)else{};day=result.get('canonical_date');reason=release_guard_reason(item,stamp)
   if day and day>=stamp:reason='canonical_date_at_or_after_report; original pre-cutoff availability unverified; conservatively excluded'
   elif item['id']in prioritized and not day:reason='resolved priority canonical URL has no publication date; conservatively excluded'
   if reason:excluded.append({**item,'reason':reason,'metadata':result});continue
   if day:item={**item,'canonical_url':result['canonical_url'],'canonical_date':day}
   ready.append(item)
  feed['items']=ready;feed['canonical_screening']='Selected priority Reuters canonical dates and conservative April release guards. Every priority transport lookup resolved before freeze. No original body or original publication-vintage guarantee; all cited claims require own-date editorial review.'
  target=ROOT/'feeds'/(stamp+'.json.gz');atomic_json(target,feed,True)
  receipt={'date':stamp,'status':'ready','unreviewed_items':len(ready)+len(excluded),'items':len(ready),'ready_items':len(ready),'unreviewed_path':str(rawpath.relative_to(ROOT)),'unreviewed_sha256':sha(rawpath),'ready_path':str(target.relative_to(ROOT)),'feed_sha256':sha(target),'ready_sha256':sha(target),'priority_reuters_records':len(prioritized),'metadata_lookup_failures':0,'unresolved_priority_ids':[],'excluded_items':excluded,'excluded_count':len(excluded),'surviving_ids_preserved':True,'query_upper_bound_enforced':True,'release_guard_version':'April2025scheduled-actuals-v1','scope':'Selected Reuters canonical-date screen plus conservative targeted actual-release calendar; not exhaustive publication-time or article-body vintage verification.'}
  atomic_json(ROOT/'audit'/('news_ready_'+stamp+'.json'),receipt);rows.append({k:v for k,v in receipt.items()if k!='excluded_items'})
  print(stamp,'READY',len(ready),'excluded',len(excluded),flush=True)
 out={'version':'apr-final-screened-v1','status':'passed','report_dates':len(rows),'missing_dates':[],'failed_query_windows':0,'unresolved_priority_records':0,'ready_own_date_records':sum(r['items']for r in rows),'raw_own_date_records':sum(r['unreviewed_items']for r in rows),'excluded_records':sum(r['excluded_count']for r in rows),'failed_requests':0,'unresolved_priority_urls':0,'canonical_cache_path':str(snapshot_path.relative_to(ROOT)),'canonical_cache_sha256':sha(snapshot_path),'metadata_plan_sha256':sha(ROOT/'audit/news_metadata_request_plan.json'),'coverage_sha256':sha(ROOT/'audit/news_coverage.json'),'screening_tool_sha256':sha(ROOT/'tools/ready_feeds.py'),'rows':rows,'limits':coverage['limits']}
 atomic_json(ROOT/'audit/news_ready_audit.json',out);return out

def inventory():
 ready=read(ROOT/'audit/news_ready_audit.json');assert ready['status']=='passed'
 plan=read(ROOT/'audit/news_query_plan.json');paths={ROOT/row['cache_path']for row in plan['requests']}
 paths.update((ROOT/'work/unreviewed_feeds').glob('*.json.gz'));paths.update((ROOT/'feeds').glob('*.json.gz'));paths.update((ROOT/'audit/news_provenance').glob('*.json.gz'))
 paths.update((ROOT/'audit').glob('news_*.json'));paths.add(ROOT/'audit/canonical_priority_urls.json')
 for receipt in (ROOT/'audit').glob('news_public_rss_ingestion_*.json'):
  batch=ROOT/read(receipt)['batch'];paths.update(p for p in batch.rglob('*')if p.is_file())
 for receipt in (ROOT/'audit').glob('metadata_ci_ingestion_*.json'):
  paths.add(receipt);batch=ROOT/read(receipt)['files'];paths.update(p for p in batch.rglob('*')if p.is_file())
 paths.update([ROOT/'tools/import_public_metadata.py',ROOT/'tools/import_public_rss.py',ROOT/'tools/fetch_news.py',ROOT/'tools/expand_capped_news.py',ROOT/'tools/ready_feeds.py',ROOT/'tools/topics.py',ROOT/'tools/digest.py',ROOT/'posthoc/resolve_news_url.py'])
 if (ROOT/'tools/check_news_acquisition.py').exists():paths.add(ROOT/'tools/check_news_acquisition.py')
 paths.discard(ROOT/'audit/news_replay_inventory.json')
 files=[{'path':str(p.relative_to(ROOT)),'sha256':sha(p),'bytes':p.stat().st_size,'kind':'cached_query_response'if p.parent.name=='news'else'own_date_raw'if'unreviewed_feeds'in str(p)else'own_date_final'if p.parent.name=='feeds'else'provenance'if p.parent.name=='news_provenance'else'source_code'if p.suffix=='.py'else'audit_receipt'}for p in sorted(paths)]
 out={'status':'complete','complete':True,'files':files,'file_count':len(files),'total_bytes':sum(r['bytes']for r in files),'scope':'Exact retrieval-time parsed query caches, context inventory, own-date raw/final snapshots, provenance ledgers and acquisition/readiness code/receipts needed offline replay. Publisher bodies and original historical RSS server snapshots not available.'}
 atomic_json(ROOT/'audit/news_replay_inventory.json',out);print('replay inventory',len(files),'files',out['total_bytes'],'bytes',flush=True);return out

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--plan-metadata',action='store_true');ap.add_argument('--resolve-metadata',action='store_true');ap.add_argument('--inventory',action='store_true');ap.add_argument('--workers',type=int,default=3);args=ap.parse_args()
 if args.plan_metadata:out=metadata_plan();print(out['url_count'],'priority unique URLs')
 elif args.resolve_metadata:resolve_metadata(args.workers)
 elif args.inventory:inventory()
 else:freeze()
if __name__=='__main__':main()
