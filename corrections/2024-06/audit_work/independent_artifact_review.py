"""Independent synthetic review of current artifact tools; no real report inputs."""
from pathlib import Path
import ast, copy, datetime as dt, difflib, gzip, hashlib, importlib.util, json, subprocess, sys, tempfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent.parent
FILES=['tools/render.py','tools/build_artifacts.py','tools/build_retail_page.py','tools/build_source_inventory.py','audit_work/review_final_artifacts.py']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def blobsha(value):return hashlib.sha256(value).hexdigest()
def module(path):
 spec=importlib.util.spec_from_file_location('independent_artifact_'+path.stem,path);out=importlib.util.module_from_spec(spec);spec.loader.exec_module(out);return out
mods={Path(name).stem:module(ROOT/name) for name in FILES}
a=mods['review_final_artifacts'];b=mods['build_artifacts'];i=mods['build_source_inventory']
results=[]
def test(name,call,reject=True):
 try:call();rejected=False;detail='accepted'
 except (ValueError,KeyError,TypeError,FileNotFoundError) as exc:rejected=True;detail=str(exc)
 results.append({'case':name,'expected_rejection':reject,'passed':rejected==reject,'observed':detail})
# Capture only the owner's in-memory synthetic fixture; use its positive pack to
# mutate dependency relations independently of the implementation under test.
real_replay=a.replay_archive;captured={}
def capture(archive):
 if not captured:captured.update(copy.deepcopy(archive.values))
 return real_replay(archive)
with patch.object(a,'replay_archive',side_effect=capture):baseline=a.negative_fixtures(mods)
assert len(baseline)==55
class Archive:
 def __init__(self,values):self.values=values
 def namelist(self):return list(self.values)
 def read(self,name):return self.values[name]
original_source=json.loads(captured['audit/independent_source_review.json'])
freeze=json.loads(captured['audit/source_freeze.json'])
date=a.DATES[0];ready_name=f'audit/news_ready_{date}.json'
def ready_mutation(change):
 files=copy.deepcopy(captured);source=copy.deepcopy(original_source)
 ready=json.loads(files[ready_name]);change(ready,source['dates'][0]);files[ready_name]=json.dumps(ready).encode()
 source['input_bindings'][ready_name]=source['dates'][0]['ready_receipt_sha256']=blobsha(files[ready_name])
 return files,source
def check_ready(name,change):
 files,source=ready_mutation(change)
 test('reviewer_'+name,lambda:a.current_source_dependencies(Archive(files),source,freeze))
 with tempfile.TemporaryDirectory(prefix='independent-june-ready-') as temporary:
  root=Path(temporary)
  for row in source['dates']:
   relative=f"audit/news_ready_{row['date']}.json";path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(files[relative])
  with patch.object(i,'ROOT',root):test('inventory_'+name,lambda:i.require_ready_receipts(source))
check_ready('canonical_exclusion_alias_rejected',lambda ready,row:ready['excluded'][0].__setitem__('id','ALIAS'))
def duplicate(ready,row):
 ready['excluded'].append(copy.deepcopy(ready['excluded'][0]));ready['input_items']=row['raw_items']=4;ready['excluded_items']=row['excluded']=2
check_ready('duplicate_excluded_ids_rejected',duplicate)
check_ready('empty_excluded_id_rejected',lambda ready,row:ready['excluded'][0].__setitem__('id',''))
# Construct complete generic component bindings, then mutate exactly one review.
with tempfile.TemporaryDirectory(prefix='independent-june-components-') as temporary:
 root=Path(temporary)
 for relative,data in captured.items():
  path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
 def save(relative,value):
  path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False)+'\n')
 for day in a.DATES:
  spec={'date':day,'geo':[],'retail_intro':'Synthetic introduction.','retail':[]};save(f'specs/{day}.json',spec)
  retail={key:spec[key] for key in ['date','retail_intro','retail']};save(f'retail_drafts/{day}.json',retail)
  save(f'exclusions/{day}.json',{'date':day,'exclusions':[]})
  nr={key:value for key,value in spec.items() if key not in {'retail','retail_intro'}}
  review={'date':day,'status':'accepted','fatal_or_major_remaining':0,'feed_sha256':sha(root/f'feeds/{day}.json.gz'),'card_sha256':sha(root/f'cards/{day}.json'),'exclusions_sha256':sha(root/f'exclusions/{day}.json')}
  save(f'audit/independent_nonretail_{day}.json',{**review,'nonretail_content_sha256':blobsha(json.dumps(nr,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode())})
  save(f'audit/independent_retail_{day}.json',{**review,'retail_draft_sha256':sha(root/f'retail_drafts/{day}.json')})
 with patch.object(b,'ROOT',root),patch.object(i,'ROOT',root),patch.object(b,'module',return_value=i):
  test('complete_current_generic_components_accepted',lambda:b.accepted_components(a.DATES),reject=False)
  for name,kind,change in [
   ('nonretail_pending_status_rejected','nonretail',lambda r:r.__setitem__('status','pending')),
   ('retail_rejected_status_rejected','retail',lambda r:r.__setitem__('status','rejected')),
   ('nonretail_stale_exclusions_rejected','nonretail',lambda r:r.__setitem__('exclusions_sha256','stale')),
   ('retail_missing_exclusions_rejected','retail',lambda r:r.pop('exclusions_sha256')),
   ('retail_legacy_hash_alias_rejected','retail',lambda r:r.__setitem__('draft_sha256',r.pop('retail_draft_sha256'))),
  ]:
   path=root/f'audit/independent_{kind}_{date}.json';saved=path.read_bytes();value=json.loads(saved);change(value);path.write_text(json.dumps(value))
   test('builder_'+name,lambda:b.accepted_components(a.DATES));path.write_bytes(saved)
# Every ledger signature must occur in the canonical request inventory, including
# a failed request with a received body; preserving orphan bytes is insufficient.
files=copy.deepcopy(captured);source=copy.deepcopy(original_source)
ledger=[json.loads(line) for line in files['audit/news_physical_requests.jsonl'].decode().splitlines()]
extra=copy.deepcopy(ledger[0]);extra.update(signature='orphan-signature',raw_response_path='cache/rss_raw/attempts/orphan.1.xml.gz')
files[extra['raw_response_path']]=files[ledger[0]['raw_response_path']];ledger.append(extra)
files['audit/news_physical_requests.jsonl']=(''.join(json.dumps(row)+'\n' for row in ledger)).encode()
source.update(ledger_sha256=blobsha(files['audit/news_physical_requests.jsonl']),physical_attempts=2,received_attempt_bodies=2)
changed_freeze=copy.deepcopy(freeze);changed_freeze['physical_request_ledger_sha256']=source['ledger_sha256']
test('physical_ledger_orphan_signature_rejected',lambda:a.current_source_dependencies(Archive(files),source,changed_freeze))
# Exception metadata is part of the displayed provenance, so it must survive
# HTML and PDF preservation alongside its headline/outlet/timestamp.
r=mods['render']
exception={'date':date,'id':'n0001','reason':'Synthetic release available before cutoff','known_before_utc':'2024-06-02T20:00:00Z','evidence_url':'https://example.org/timing'}
evidence={'n0001':{'id':'n0001','title':'Synthetic title','src':'Synthetic Outlet','published_at':'2024-06-02T12:00:00Z','url':'https://example.org/source','availability_review':exception}}
spec={'date':date,'geo':[],'sectors':[],'earnings_pattern':{'parts':[['Narrative','Synthetic prose. [[n0001]]']]},'underowned':[],'crypto':{'parts':[]},'flows':{'parts':[]},'anticipatory':[],'catalysts':[],'retail_intro':'Synthetic crowd.','retail':[]}
doc=r.Doc(evidence)
body=doc.parts(spec['earnings_pattern']['parts'])[0]+'<p class="retail-intro">'+doc.text(spec['retail_intro'])+'</p>'
core='Synthetic title — Synthetic Outlet · 2024-06-02T12:00:00Z'
note='Timing: '+exception['reason']+' Verified available before '+exception['known_before_utc']+'. '
ledger='<details class="ledger"><ol><li data-source-id="n0001"><a href="https://example.org/source">Synthetic title</a> — Synthetic Outlet · 2024-06-02T12:00:00Z<br><span>'+note+'<a href="https://example.org/timing">Timing evidence</a>.</span></li></ol></details>'
page=body+ledger
test('truthful_exception_metadata_positive',lambda:a.html_preservation(a.BeautifulSoup(page,'html.parser'),spec,evidence,date),reject=False)
test('HTML_exception_reason_mutation_rejected',lambda:a.html_preservation(a.BeautifulSoup(page.replace(exception['reason'],'Synthetic AFTER cutoff'),'html.parser'),spec,evidence,date))
test('HTML_exception_before_clock_mutation_rejected',lambda:a.html_preservation(a.BeautifulSoup(page.replace(exception['known_before_utc'],'2024-06-04T20:00:00Z'),'html.parser'),spec,evidence,date))

order=a.expected_order(spec)
pdf_body=' '.join((label+': ' if label else '')+a.displayed(text,order) for _,label,text in a.paragraphs(spec))
pdf_text=pdf_body+' Dated evidence · 1 sources '+core+' '+note+'Timing evidence.'
class Page:
 def __init__(self,text):self.text=text
 def extract_text(self):return self.text
class PDF:
 def __init__(self,text):self.pages=[Page(text)]
for name,checker in [('builder',lambda text:b.check_pdf_prose(date,PDF(text),spec,evidence)),('reviewer',lambda text:a.pdf_preservation(date,text,spec,evidence))]:
 test(name+'_PDF_exception_metadata_positive',lambda checker=checker:checker(pdf_text),reject=False)
 test(name+'_PDF_exception_reason_mutation_rejected',lambda checker=checker:checker(pdf_text.replace(exception['reason'],'Synthetic AFTER cutoff')))
 test(name+'_PDF_exception_before_clock_mutation_rejected',lambda checker=checker:checker(pdf_text.replace(exception['known_before_utc'],'2024-06-04T20:00:00Z')))

# The producer pre-packaging ledger guard must enforce the same set boundary.
with tempfile.TemporaryDirectory(prefix='independent-june-physical-') as temporary:
 root=Path(temporary)
 for relative,data in captured.items():
  path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
 physical_source=copy.deepcopy(original_source)
 with patch.object(i,'ROOT',root):
  test('inventory_physical_ledger_positive',lambda:i.require_physical_ledger(physical_source),reject=False)
  for name,change in [('boolean_attempt',lambda row:row.__setitem__('attempt',True)),('zero_attempt',lambda row:row.__setitem__('attempt',0)),('fetched_without_body',lambda row:row.pop('raw_response_path'))]:
   path=root/'audit/news_physical_requests.jsonl';original=path.read_bytes();row=json.loads(original);change(row);path.write_text(json.dumps(row)+'\n');modified=copy.deepcopy(physical_source);modified['ledger_sha256']=sha(path)
   test('inventory_physical_'+name+'_rejected',lambda:i.require_physical_ledger(modified));path.write_bytes(original)
  ghost=root/'cache/rss_raw/attempts/ghost.1.xml.gz';ghost.write_bytes(gzip.compress(b'Synthetic ghost body',mtime=0))
  test('inventory_physical_orphan_body_rejected',lambda:i.require_physical_ledger(physical_source));ghost.unlink()
  modified=copy.deepcopy(physical_source);modified['physical_requests']=True
  test('inventory_physical_boolean_request_count_rejected',lambda:i.require_physical_ledger(modified))

own_feed={'items':[{key:value for key,value in evidence['n0001'].items() if key!='availability_review'}]}
test('own_evidence_valid_timing_exception_positive',lambda:a.own_evidence(spec,own_feed,[exception],date),reject=False)
for name,clock in [('midnight',date+'T00:00:00Z'),('after_cutoff','2024-06-04T20:00:00Z'),('naive_clock','2024-06-02T20:00:00')]:
 changed=copy.deepcopy(exception);changed['known_before_utc']=clock
 test('own_evidence_'+name+'_exception_rejected',lambda changed=changed:a.own_evidence(spec,own_feed,[changed],date))

# Inspect selected-code deltas without opening any factual report artifacts.
deltas={}
for name in FILES:
 old=ROOT.parent/'july2024'/name;new=ROOT/name
 before=old.read_text();after=new.read_text()
 def functions(code):return {node.name:ast.dump(node,include_attributes=False) for node in ast.parse(code).body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}
 old_functions=functions(before);new_functions=functions(after)
 deltas[name]={'july_selected_sha256':sha(old),'june_current_sha256':sha(new),'changed_functions':[key for key in new_functions if old_functions.get(key)!=new_functions[key]],'added_functions':sorted(set(new_functions)-set(old_functions)),'removed_functions':sorted(set(old_functions)-set(new_functions)),'unified_delta_lines':sum(1 for row in difflib.unified_diff(before.splitlines(),after.splitlines()))}
for name,functions_to_keep in [('tools/build_artifacts.py',['prose_key','ordered_matches']),('audit_work/review_final_artifacts.py',['normal','monotonic'])]:
 old_functions=functions((ROOT.parent/'july2024'/name).read_text());new_functions=functions((ROOT/name).read_text())
 assert all(old_functions[key]==new_functions[key] for key in functions_to_keep),name
# Execute the complete current owner suites, then bind their actual receipts.
owner_runs=[]
for helper,args in [('audit_work/review_final_artifacts.py',['--static']),('audit_work/artifact_regression_groups.py',[]),('audit_work/test_artifact_unicode_layout.py',[])]:
 completed=subprocess.run([sys.executable,str(ROOT/helper),*args],text=True,capture_output=True)
 owner_runs.append({'helper':helper,'sha256':sha(ROOT/helper),'arguments':args,'returncode':completed.returncode,'stdout':completed.stdout.strip(),'stderr':completed.stderr.strip()})
 assert completed.returncode==0,(helper,completed.stderr,completed.stdout)
owner_static=json.loads((ROOT/'checks/artifact_tool_review.json').read_text());owner_groups=json.loads((ROOT/'checks/artifact_regression_groups.json').read_text())
assert owner_static['negative_fixture_count']==55 and len(owner_groups['synthetic_tests'])==24

receipt={'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'review_type':'independent_synthetic_artifact_engineering_review','tool_sha256':{name:sha(ROOT/name) for name in FILES},'reviewer_sha256':sha(Path(__file__)),'owner_preservation_cases_executed':len(baseline),'owner_complete_suite_runs':owner_runs,'owner_group_count':len(owner_groups['synthetic_tests']),'selected_July_code_delta_inspection':deltas,'independent_cases':results,'passed':all(row['passed'] for row in results),'failures':[row for row in results if not row['passed']],'runtime_full20_accepted':False,'facts_or_real_specs_read':False,'publication_performed':False,'limits':['Engineering code and synthetic fixtures only.','Real20report native/artifact/source archive acceptance remains pending.']}
(ROOT/'checks/independent_artifact_engineering_review.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'cases':len(results),'passed':sum(row['passed'] for row in results),'failures':[row['case'] for row in results if not row['passed']]}))
