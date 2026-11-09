"""Read-only independent June publication/delivery code and pure-predicate review; never calls either entrypoint."""
from pathlib import Path
import ast,datetime as dt,hashlib,json,re,copy,tempfile,threading
import concurrent.futures as futures
from types import SimpleNamespace
from bs4 import BeautifulSoup
R=Path(__file__).resolve().parent.parent;P=R/'tools/publish.py';V=R/'tools/verify_delivery.py';ps=P.read_text();vs=V.read_text();pt=ast.parse(ps);vt=ast.parse(vs);ph=hashlib.sha256(P.read_bytes()).hexdigest();vh=hashlib.sha256(V.read_bytes()).hexdigest();pc=[];vc=[];pe=[];ve=[]
def check(ok,name,checks,errors):
 checks.append({'check':name,'passed':bool(ok)})
 if not ok:errors.append(name)
def cp(ok,name):check(ok,name,pc,pe)
def cv(ok,name):check(ok,name,vc,ve)
def run(nodes,env):
 try:exec(compile(ast.Module(body=nodes,type_ignores=[]),'<isolated-read-only-predicate>','exec'),env);return True
 except ValueError:return False
# Compile only DATES and two pure helpers; no imports/SDK/main/plan is executed.
sel=[n for n in pt.body if (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='DATES' for t in n.targets)) or (isinstance(n,ast.FunctionDef) and n.name in ('protected_keys','merge_index'))];ns={'dt':dt,'BeautifulSoup':BeautifulSoup,'re':re};run(sel,ns);dates=[dt.date(2024,6,n).isoformat() for n in range(1,31) if dt.date(2024,6,n).weekday()<5]
cp(ns['DATES']==dates and len(dates)==20 and '2024-06-19' in dates,'exact20June weekdays including exchange holiday');protected=ns['protected_keys']();weekends=[dt.date(2024,6,n).isoformat() for n in range(1,31) if dt.date(2024,6,n).weekday()>4];expected_protected={'reports/latest.html'}
for m,last in [(7,31),(8,31),(9,30),(10,31),(11,30)]:
 ym=f'2024-{m:02}';expected_protected|={f'reports/{ym}.html',f'reports/{ym}/What_Retail_Is_Playing_{ym}.html'};expected_protected|={f'reports/archive/{ym}-{n:02}.html' for n in range(1,last+1) if dt.date(2024,m,n).weekday()<5}
expected_protected|={f'reports/archive/2026-08-{n:02}.html' for n in range(1,32)};expected_protected|={key for d in weekends for key in [f'reports/archive/{d}.html',f'Strategies/json/{d}_Market_Intelligence.json',f'Strategies/{d}_Market_Intelligence.pdf']};cp(set(protected)==expected_protected and len(protected)==len(set(protected))==182,'exact182 protected keys:latest,July–Nov2024HTML,Aug2026andJuneweekends')
old_links={'archive/2026-11-05.html','2024-08.html','2024-08/What_Retail_Is_Playing_2024-08.html','2024-09.html','2024-10.html','2024-11.html','some-unrelated-link'};fixture='<html><body><p><a href="some-unrelated-link">Other</a></p><ul>'+''.join(f'<li><a href="{h}">{h}</a></li>' for h in sorted(old_links-{'some-unrelated-link'}))+'</ul></body></html>';merged=ns['merge_index'](fixture);soup=BeautifulSoup(merged,'html.parser');hrefs={a.get('href') for a in soup.find_all('a')};new_expected={f'archive/{d}.html' for d in dates}|{'2024-06.html','2024-06/What_Retail_Is_Playing_2024-06.html'};cp(hrefs==old_links|new_expected,'index merge adds only20daily+2Junecollection links and preserves every old href');cp(all(len(soup.find_all('a',href=f'archive/{d}.html'))==1 for d in dates),'one June daily link each');cp(not any(f'archive/{d}.html' in hrefs for d in weekends),'no June weekend link created');cp('20 weekday briefings' in soup.get_text(' ',strip=True),'June collection label says20editions')
for name,fixture2,want in [('already-present June holiday','<ul><li><a href="archive/2024-06-04.html">Old</a></li></ul>',True),('duplicate June date','<ul><li><a href="archive/2024-06-04.html">One</a></li><li><a href="archive/2024-06-04.html">Two</a></li></ul>',False),('missing archive list','<html><p>No list</p></html>',False)]:
 try:ns['merge_index'](fixture2);allowed=True
 except (ValueError,TypeError):allowed=False
 cp(allowed==want,'index pure-function fixture: '+name)
cp("len(targets) != 65 or len({x['key'] for x in targets}) != 65" in ps,'publisher requires65unique targets');cp("set(row['files']) != {'html', 'json', 'pdf'}" in ps,'publisher requires60native format entries');cp("frozen.get('status') != 'all_20_ready'" in ps and 'Complete 20-date month required' in ps,'complete20 source/manifest gates');cp(all(x in ps for x in ['independent_source_review.json','independent_market_review.json','final_precision_review.json','final_editorial_review.json','retail.require_review(ROOT)']),'independent source/market/precision/editorial/retail gates');cp(all(x in ps for x in ['nonretail_content_sha256','retail_draft_sha256','feed_sha256','card_sha256','spec_sha256']),'final component and input hash bindings');cp("if len(blob) != item['bytes'] or sha(blob) != item['sha256']" in ps,'every local artifact hash/size checked before write');cp("if not path.is_relative_to(ROOT) or not path.is_file()" in ps,'artifact path confined to June root');cp("if '2024-06' not in item['key']" in ps and 'June_2024_(Weekday_Reports|Frozen_Sources)' in ps,'only June target names admitted')
main=next(n for n in pt.body if isinstance(n,ast.FunctionDef) and n.name=='main');puts=[n for n in ast.walk(main) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='put_object'];go_gate=next(n for n in main.body if isinstance(n,ast.If) and ast.unparse(n.test)=='not args.go');cp(len(puts)==3 and all(n.lineno>go_gate.end_lineno for n in puts),'default dry-run reaches no S3 writes; only backup,daily,index put paths');cp(sum(any(k.arg=='IfNoneMatch' and isinstance(k.value,ast.Constant) and k.value.value=='*' for k in n.keywords) for n in puts)==2,'backup and daily objects are create-only');cp(sum(any(k.arg=='IfMatch' for k in n.keywords) for n in puts)==1,'index write conditional on fresh ETag');cp('reports/_retrospective_backup/jun-2024-weekdays/' in ps,'June-specific index backup namespace');cp("if read(s3,key)['sha256'] != idx['sha256']" in ps and "Index body verification failed" in ps,'backup and merged index full-body hashes verified');cp("receipt['protected_before'] != receipt['protected_after']" in ps and "receipt['protected_before'] != snapshot(s3)" in ps,'strict protected preservation during publication and resume');cp("receipt['targets'] != targets or receipt['manifest_sha256'] != manifest_hash" in ps,'resume binds original exact artifact plan');cp(all(x in ps for x in ['/reports/index.html','/reports/archive/2024-06-*','/reports/2024-06*','/Strategies/json/2024-06-*','/Strategies/2024-06-*']),'invalidation scoped to index and June paths')
remote_forbidden={'invoke','update_function_code','update_function_configuration','send_email','send_raw_email','publish','send_message','delete_object','delete_objects'};calls={n.func.attr for n in ast.walk(pt) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)};cp(not remote_forbidden&calls,'no Lambda deployment/invocation,sends,or remote delete calls')
# Delivery guards are executed independently with synthetic receipts/ZIP name lists.
vm=next(n for n in vt.body if isinstance(n,ast.FunctionDef) and n.name=='main');assign=lambda n,name:isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets);update=lambda n,name:isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute) and isinstance(n.value.func.value,ast.Name) and n.value.func.value.id==name and n.value.func.attr=='update';nodes=[n for n in vm.body if assign(n,'dates') or assign(n,'expected_targets') or update(n,'expected_targets') or (isinstance(n,ast.If) and "receipt.get('dates')" in ast.unparse(n.test))];targets={k for d in dates for k in [f'reports/archive/{d}.html',f'Strategies/json/{d}_Market_Intelligence.json',f'Strategies/{d}_Market_Intelligence.pdf']};targets|={'reports/2024-06.html','reports/2024-06/June_2024_Weekday_Reports.zip','reports/2024-06/June_2024_Frozen_Sources.zip','reports/2024-06/What_Retail_Is_Playing_2024-06.html','reports/2024-06/methodology.txt'};base={'dates':dates,'targets':[{'key':x} for x in sorted(targets)]};cv(len(nodes)==4,'isolate65-target predicate without executing network entrypoint')
for name,rec,want in [('valid',base,True),('missing',{'dates':dates,'targets':base['targets'][:-1]},False),('duplicate',{'dates':dates,'targets':base['targets'][:-1]+base['targets'][:1]},False),('foreign August route',{'dates':dates,'targets':base['targets'][:-1]+[{'key':'reports/2024-08.html'}]},False),('wrong dates',{'dates':dates[:-1],'targets':base['targets']},False)]:cv(run(nodes,{'dt':dt,'receipt':rec})==want,'delivery exact-target fixture: '+name)
zipnodes=[n for n in ast.walk(vm) if assign(n,'expected_members') or update(n,'expected_members') or (isinstance(n,ast.If) and 'len(archive.namelist()) != 63' in ast.unparse(n.test))];members={x for d in dates for x in [f'html/{d}.html',f'json/{d}_Market_Intelligence.json',f'pdf/{d}_Market_Intelligence.pdf']}|{'index.html','methodology.txt','What_Retail_Is_Playing_2024-06.html'}
class Archive:
 def __init__(self,names):self.names=names
 def namelist(self):return self.names
lst=sorted(members);cv(len(zipnodes)==3,'isolate63-member publicZIP predicate')
for name,values,want in [('valid',lst,True),('missing',lst[:-1],False),('duplicate',lst[:-1]+lst[:1],False),('unsafe/foreign',lst[:-1]+['../outside'],False)]:cv(run(zipnodes,{'dates':dates,'archive':Archive(values)})==want,'publicZIP exact-members fixture: '+name)
cv("bundle_key='reports/2024-06/June_2024_Weekday_Reports.zip'" in vs,'canonical June public report ZIP route');cv("archive.testzip()" in vs and "len(members)==60" in vs,'ZIP CRC and all60native report members required');cv("obj['sha256']==item['sha256'] and obj['bytes']==item['bytes']" in vs and "hashlib.sha256(body).hexdigest()==item['sha256'] and len(body)==item['bytes']" in vs,'origin/public full body hash/size checks');cv("row['public_bundle_member']=artifact['path']" in vs and "if item['key'].startswith('Strategies/')" in vs,'40PDF/JSON public downloads verified through ZIP rather than fallback route');cv("unchanged=protected==receipt['protected_before']" in vs and not any(x in vs for x in ['independent_concurrent_update_review','reviewed_external_update','index_reconciliation','2026-11-04']),'strict preservation with no inherited Nov4 concurrency waiver');cv("idx['sha256']==receipt['index_sha256']" in vs and "old_hrefs <=" in vs and "index_public_pass=hashlib.sha256(response.read()).hexdigest()==idx['sha256']" in vs,'index origin/public hash and original href preservation');cv("('CodeSha256','LastModified','Runtime')" in vs,'live Lambda metadata unchanged requirement')
final=next(n for n in ast.walk(vm) if assign(n,'passed'));env={'rows':[{'origin_sha256_pass':True,'public_sha256_pass':True} for _ in range(65)],'members':[{'sha256_pass':True} for _ in range(60)],'unchanged':True,'lambda_unchanged':True,'links':{d:1 for d in dates},'inv':{'Status':'Completed'},'index_origin_pass':True,'index_public_pass':True,'archive_links_preserved':True}
def finalcase(change=None):
 e=copy.deepcopy(env)
 if change:change(e)
 run([final],e);return e['passed']
cv(finalcase(),'strict final delivery gate accepts all verified conditions')
for name,change in [('protected latest change',lambda e:e.update(unchanged=False)),('one origin mismatch',lambda e:e['rows'][0].update(origin_sha256_pass=False)),('one public mismatch',lambda e:e['rows'][0].update(public_sha256_pass=False)),('missing nativeZIP member',lambda e:e['members'].pop()),('archive href loss',lambda e:e.update(archive_links_preserved=False)),('Lambda change',lambda e:e.update(lambda_unchanged=False)),('index public mismatch',lambda e:e.update(index_public_pass=False)),('pending invalidation',lambda e:e['inv'].update(Status='InProgress'))]:cv(not finalcase(change),'final delivery gate rejects '+name)
vcalls={n.func.attr for n in ast.walk(vt) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)};cv(not (remote_forbidden|{'put_object','create_invalidation'})&vcalls,'delivery verifier has no remote mutation or send calls');cp(hashlib.sha256(P.read_bytes()).hexdigest()==ph,'publisher unchanged during review');cv(hashlib.sha256(V.read_bytes()).hexdigest()==vh,'delivery verifier unchanged during review')

# New runtime-artifact gate: compile the pure function only, without importing
# the publisher, constructing a session, calling plan(), or running main().
functions={node.name:node for node in pt.body if isinstance(node,ast.FunctionDef)}
gate_ns={'DATES':dates}
run([functions['require_artifact_review']],gate_ns)
tools={name:hashlib.sha256(name.encode()).hexdigest() for name in
       ['render.py','build_artifacts.py','build_retail_page.py','build_source_inventory.py','audit_work/review_final_artifacts.py']}
current={'status':'accepted','runtime_artifacts_reviewed':True,'fatal_or_major_remaining':0,
         'dates':dates,'reports':[{'date':date}for date in dates],
         'artifact_manifest_sha256':'a'*64,'tool_sha256':tools}
def runtime_gate(value):
 try:gate_ns['require_artifact_review'](value,'a'*64,tools);return True
 except (ValueError,TypeError,KeyError,AttributeError):return False
cp(runtime_gate(current),'current full20 runtime artifact audit accepted')
for name,change in [
 ('static-only receipt',lambda x:x.update(status='static_checks_passed',runtime_artifacts_reviewed=False)),
 ('missing runtime flag',lambda x:x.pop('runtime_artifacts_reviewed')),
 ('numeric runtime flag',lambda x:x.update(runtime_artifacts_reviewed=1)),
 ('boolean fatal count',lambda x:x.update(fatal_or_major_remaining=False)),
 ('missing fatal count',lambda x:x.pop('fatal_or_major_remaining')),
 ('remaining major issue',lambda x:x.update(fatal_or_major_remaining=1)),
 ('partial dates',lambda x:x.update(dates=dates[:-1])),
 ('reordered dates',lambda x:x.update(dates=list(reversed(dates)))),
 ('partial report rows',lambda x:x['reports'].pop()),
 ('duplicate report date',lambda x:x['reports'][-1].update(date=dates[0])),
 ('stale manifest hash',lambda x:x.update(artifact_manifest_sha256='b'*64)),
 ('missing reviewer hash',lambda x:x['tool_sha256'].pop('audit_work/review_final_artifacts.py')),
 ('changed renderer hash',lambda x:x['tool_sha256'].update({'render.py':'b'*64})),
 ('extra tool binding',lambda x:x['tool_sha256'].update({'unreviewed.py':'c'*64})),
]:
 changed=copy.deepcopy(current);change(changed);cp(not runtime_gate(changed),'runtime artifact gate rejects '+name)
plan_node=functions['plan']
plan_calls=[node for node in ast.walk(plan_node) if isinstance(node,ast.Call)]
cp(any(isinstance(node.func,ast.Name)and node.func.id=='require_artifact_review'for node in plan_calls),
   'publisher plan actually calls mandatory runtime artifact gate')
cp('Artifact manifest changed during publication planning' in ps,'publisher plan detects manifest changes before returning')
manifest_guard=next(node for node in plan_node.body if isinstance(node,ast.If)
                    and ast.unparse(node.test)=='sha(manifest_path.read_bytes()) != manifest_hash')
manifest_blob=b'{"synthetic_manifest":true}'
for label,blob,want in [('stable',manifest_blob,True),('changed',manifest_blob+b' ',False)]:
 cp(run([manifest_guard],{'manifest_path':SimpleNamespace(read_bytes=lambda blob=blob:blob),
                         'manifest_hash':hashlib.sha256(manifest_blob).hexdigest(),
                         'sha':lambda data:hashlib.sha256(data).hexdigest()})==want,
    'actual final manifest hash predicate '+label)
component_guard=next(node for node in ast.walk(plan_node)if isinstance(node,ast.If)
                     and "record.get('status')" in ast.unparse(node.test))
for label,record,want in [('accepted',{'date':dates[0],'status':'accepted','fatal_or_major_remaining':0},True),
 ('passed',{'date':dates[0],'status':'passed','fatal_or_major_remaining':0},True),
 ('missing status',{'date':dates[0],'fatal_or_major_remaining':0},False),
 ('pending status',{'date':dates[0],'status':'pending','fatal_or_major_remaining':0},False),
 ('boolean fatal',{'date':dates[0],'status':'accepted','fatal_or_major_remaining':False},False),
 ('string fatal',{'date':dates[0],'status':'accepted','fatal_or_major_remaining':'0'},False),
 ('nonzero fatal',{'date':dates[0],'status':'accepted','fatal_or_major_remaining':1},False)]:
 cp(run([component_guard],{'record':record,'date':dates[0]})==want,'current component predicate '+label)
cp("record.get('status') not in {'accepted', 'passed'}" in ps
   and "type(record.get('fatal_or_major_remaining')) is not int" in ps
   and "rr.get('retail_draft_sha256')" in ps and "rr.get('draft_sha256')" not in ps,
   'canonical component status integer-zero and retail hash remain mandatory')
cp("('exclusions_sha256', ROOT/'exclusions'/(date+'.json'))" in ps,
   'every current component independently binds exclusions bytes')

# Exercise the actual extracted snapshot body using a real eight-thread pool
# and a deterministic barrier. Reads return only synthetic object metadata.
# No SDK module or publisher entrypoint is imported or executed.
keys=list(protected)
sentinel_s3=object()
class SyntheticReadError(RuntimeError):pass
def concurrent_read(expected,existing=None,failure=None):
 lock=threading.Lock();seen=[];active=0;maximum=0;barrier=threading.Barrier(8)
 def fake_read(client,key):
  nonlocal active,maximum
  assert client is sentinel_s3
  with lock:
   ordinal=len(seen);seen.append(key);active+=1;maximum=max(maximum,active)
  try:
   if ordinal<8:barrier.wait(timeout=5)
   if key==failure:raise SyntheticReadError('Synthetic failed protected/target read')
   if existing is not None:return {'etag':'fixture','sha256':'a'*64,'bytes':1}if key in existing else None
   index=expected.index(key)
   return None if index%7==0 else {'body':b'synthetic','etag':'etag-'+str(index),
                                  'sha256':hashlib.sha256(key.encode()).hexdigest(),'bytes':len(key)}
  finally:
   with lock:active-=1
 return fake_read,seen,lambda:maximum
fake_read,seen,maximum=concurrent_read(keys)
snapshot_ns={'protected_keys':lambda:keys,'read':fake_read,'futures':futures}
run([functions['snapshot']],snapshot_ns)
actual=snapshot_ns['snapshot'](sentinel_s3)
expected={key:(None if index%7==0 else {'etag':'etag-'+str(index),
           'sha256':hashlib.sha256(key.encode()).hexdigest(),'bytes':len(key)})for index,key in enumerate(keys)}
cp(actual==expected and list(actual)==keys and len(seen)==len(set(seen))==182,
   'concurrent snapshot retains all182 ordered keys and exact absent/etag/hash/size metadata')
cp(maximum()==8,'protected snapshot actually overlaps eight independent reads')
fake_read,seen,maximum=concurrent_read(keys,failure=keys[9]);snapshot_ns['read']=fake_read
try:snapshot_ns['snapshot'](sentinel_s3);propagated=False
except SyntheticReadError:propagated=True
cp(propagated,'concurrent protected snapshot propagates worker read failure')

# Extract only the new target-absence read block and its refusal predicate.
# Reproduce complete results, existing targets, and a thrown worker error.
resume_branch=next(node for node in main.body if isinstance(node,ast.If)and ast.unparse(node.test)=='args.resume')
absence_nodes=[node for node in resume_branch.orelse if isinstance(node,(ast.With,ast.For))]
cp(len(absence_nodes)==2,'isolate only target absence reads and existing-target guard')
target_keys=sorted(targets);target_rows=[{'key':key}for key in target_keys]
for label,existing,failure,want in [('all absent',set(),None,True),
 ('first exists',{target_keys[0]},None,False),('last exists',{target_keys[-1]},None,False),
 ('worker read failed',set(),target_keys[13],False)]:
 fake_read,seen,maximum=concurrent_read(target_keys,existing=existing,failure=failure)
 env={'futures':futures,'read':fake_read,'s3':sentinel_s3,'targets':target_rows}
 try:exec(compile(ast.Module(body=absence_nodes,type_ignores=[]),'<synthetic-target-absence>','exec'),env);allowed=True
 except (ValueError,SyntheticReadError):allowed=False
 cp(allowed==want,'concurrent target absence fixture '+label)
 if label=='all absent':
  cp(env['present']==[False]*65 and set(seen)==set(target_keys)and len(seen)==65 and maximum()==8,
     'all65 target absence reads complete without dropped results and preserve input order')

# The optional registry predicate is tested with isolated bytes and a pure
# temporary filesystem, never by invoking the real SDK or reading real inputs.
# The extracted plan itself is deliberately not called: only its hash-binding
# loop is compiled, so no real or synthetic report set is built here.
precision_loop=next(node for node in plan_node.body if isinstance(node,ast.For)
                    and 'additional_release_exclusions_sha256' in ast.unparse(node))
def optional_case(registry,recorded,mandatory=True):
 with tempfile.TemporaryDirectory(prefix='independent-june-publication-registry-')as temporary:
  root=Path(temporary);(root/'audit').mkdir()
  blobs={'independent_source_review.json':b'synthetic source acceptance',
         'independent_market_review.json':b'synthetic market acceptance'}
  if mandatory:
   for name,blob in blobs.items():(root/'audit'/name).write_bytes(blob)
  if registry is not None:(root/'audit/additional_release_exclusions.json').write_bytes(registry)
  precision={'additional_release_exclusions_sha256':recorded,
             'source_acceptance_sha256':hashlib.sha256(blobs['independent_source_review.json']).hexdigest(),
             'market_acceptance_sha256':hashlib.sha256(blobs['independent_market_review.json']).hexdigest()}
  return run([precision_loop],{'ROOT':root,'precision':precision,'sha':lambda blob:hashlib.sha256(blob).hexdigest()})
registry=b'{"synthetic":true}';registry_hash=hashlib.sha256(registry).hexdigest()
cp(optional_case(None,None),'absent optional registry matches explicit null precision binding')
cp(optional_case(registry,registry_hash),'present optional registry matches exact precision hash')
cp(not optional_case(registry,None),'new registry after review rejects former null binding')
cp(not optional_case(None,registry_hash),'removed reviewed registry rejects old hash binding')
cp(not optional_case(registry,b'wrong'),'changed registry bytes/hash rejected')
cp(not optional_case(None,None,mandatory=False),'optional registry rule cannot waive source or market acceptance')

# Confirm selected July-to-June code differences and final unchanged bytes.
selected=Path('/workspace/work/july2024/tools')
delta={}
for name,current_text in [('publish.py',ps),('verify_delivery.py',vs)]:
 old=(selected/name).read_text();oldtree=ast.parse(old);newtree=ast.parse(current_text)
 oldfunc={node.name:node for node in oldtree.body if isinstance(node,ast.FunctionDef)}
 newfunc={node.name:node for node in newtree.body if isinstance(node,ast.FunctionDef)}
 delta[name]={'selected_July_code_sha256':hashlib.sha256(old.encode()).hexdigest(),
              'added_functions':sorted(set(newfunc)-set(oldfunc)),
              'changed_function_AST':[key for key in sorted(set(oldfunc)&set(newfunc))
                 if ast.dump(oldfunc[key],include_attributes=False)!=ast.dump(newfunc[key],include_attributes=False)]}
cp(hashlib.sha256(P.read_bytes()).hexdigest()==ph,'publisher bytes stable through all concurrency and gate fixtures')
cv(hashlib.sha256(V.read_bytes()).hexdigest()==vh,'delivery verifier bytes stable through final independent review')
common={'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
        'reviewer_tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'expected_scope':{'dates':dates,'editions':20,'native_artifacts':60,'collection_artifacts':5,
                          'targets':65,'reportZIP_members':63,'protected_objects':182},
        'selected_July_code_delta':delta,
        'limits':['Generic code inspection, extracted pure functions and synthetic predicates only. Neither SDK entrypoint nor the actual publication plan was executed.',
                  'No factual report input, real financial/source feed, AWS client, network read or remote mutation was used.',
                  'This review accepts code only; real20report inputs, final artifacts, publication and public delivery still require their current gates.',
                  'Protected changes remain strict failures with no inherited concurrency waiver.']}
for name,data in [
 ('independent_publication_code_review.json',{'passed':not pe,'script_sha256':ph,'publisher_sha256':ph,
   'delivery_verifier_sha256':vh,'checks':pc,'errors':pe,
   'scope':'June publisher code: exact65targets/182protected objects,20date gates, full current runtime artifact audit, optional registry hashes, conditional sequential writes, pure index merge and concurrent read fail propagation.'}),
 ('independent_delivery_tool_review.json',{'passed':not ve,'script_sha256':vh,'publisher_sha256':ph,
   'checks':vc,'errors':ve,
   'scope':'June delivery verifier code: exact65targets/63ZIP members/60native body checks,40PDFJSON bundle delivery, full-body origin/public hashes, strict182protected preservation/index hrefs/liveLambda metadata.'})]:
 (R/'audit'/name).write_text(json.dumps({**common,**data},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'publisher_passed':not pe,'publisher_checks':len(pc),'publisher_errors':pe,
                  'publisher_sha256':ph,'delivery_passed':not ve,'delivery_checks':len(vc),
                  'delivery_errors':ve,'delivery_sha256':vh},indent=2))
if pe or ve:raise SystemExit(1)
