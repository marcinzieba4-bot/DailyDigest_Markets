"""Plan by default. --go copies/stages only a new June checkpoint after delivery.

No network, Git commit/push, original-repository write or existing-checkpoint edit.
Configured credential values are compared only in process and never printed.
"""
from pathlib import Path, PurePosixPath
from collections import Counter
import argparse,datetime as dt,gzip,hashlib,importlib.metadata,io,json,os,re,shutil,subprocess,sys,tempfile,zipfile

ROOT=Path('/workspace/work/june2024')
sys.path.insert(0,str(ROOT/'tools'))
import build_source_inventory as source_export
PRIVATE_RESEARCH=source_export.PRIVATE_RESEARCH_PATHS
REPO=ROOT/'repo'
BASE='a519c5258cd14cd2cbe5bbf932e0828b423d5616'
BRANCH='codex/jun-2024-retrospective-20261109'
DEST=Path('corrections/2024-06')
PLAN=ROOT/'work/git_checkpoint_plan.json'
RECEIPT=ROOT/'work/git_checkpoint_copy_receipt.json'
DATES=[dt.date(2024,6,n).isoformat()for n in range(3,29)if dt.date(2024,6,n).weekday()<5]
MAX_TEXT_BYTES=1_000_000
REQUIRED_SECRET_NAMES={'AWS_KEY','AWS_SECRET','GH_TOKEN'}
ROOT_FILES={'AUTHORING.md','BRIEF.md','code_provenance.json','newest_lambda_function.py'}
DATE_FOLDERS={'cards':'.json','feeds':'.json.gz','specs':'.json','nonretail_drafts':'.json','retail_drafts':'.json','exclusions':'.json','html':'.html'}
COLLECTION_TEXT={'2024-06.html','methodology.txt','What_Retail_Is_Playing_2024-06.html'}
EXTERNAL_AUDIT={'news_base_query_plan.json','news_query_plan.json','news_physical_requests.jsonl','news_replay_inventory.json','source_inventory.json'}
FORBIDDEN_PARTS={'.git','.aws','.ssh','repo','git-store.git','cache','work','node_modules','__pycache__','pdf','market_raw','author_scratch','engineering_scratch'}
SHA=lambda body:hashlib.sha256(body).hexdigest()
JSON=lambda obj:(json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode()
def git(*args,check=True):
 p=subprocess.run(['git',*args],cwd=REPO,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if check and p.returncode:raise ValueError('Git read/check command failed: '+args[0])
 return p
def file_sha(path):
 h=hashlib.sha256()
 with path.open('rb')as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def package_version(name):
 try:return importlib.metadata.version(name)
 except importlib.metadata.PackageNotFoundError:return None
def safe(relative):
 p=PurePosixPath(relative)
 if p.is_absolute()or'..'in p.parts or'\\'in relative or str(p)!=relative or p.name.lower()=='claude.md':raise ValueError('Unsafe or forbidden checkpoint path')
 f=ROOT/p
 if not f.is_file()or f.is_symlink()or not f.resolve().is_relative_to(ROOT)or any(x.is_symlink()for x in f.parents if x.is_relative_to(ROOT)):raise ValueError('Unsafe checkpoint source: '+relative)
 return f
def row(relative):
 p=safe(relative);return {'source':relative,'destination':relative,'sha256':file_sha(p),'bytes':p.stat().st_size}
def repo_identity():
 top=Path(git('rev-parse','--show-toplevel').stdout.decode().strip()).resolve()
 branch=git('branch','--show-current').stdout.decode().strip();head=git('rev-parse','HEAD').stdout.decode().strip()
 common=Path(git('rev-parse','--git-common-dir').stdout.decode().strip());common=(REPO/common).resolve()
 if top!=REPO.resolve()or branch!=BRANCH or head!=BASE or common!=(ROOT/'git-store.git').resolve():raise ValueError('Unexpected isolated June worktree, branch, base or Git store')
 if git('status','--porcelain','-z').stdout or(REPO/DEST).exists():raise ValueError('A clean isolated worktree and absent June checkpoint are required')
 return {'path':str(REPO),'branch':branch,'base_commit':head,'git_common_dir':str(common)}
def credentials():
 # Read configured runtime values only here; no dumps, hashes or value snippets.
 found={k:v for k,v in os.environ.items()if v and re.search(r'(?:password|passwd|secret|token|api.?key|access.?key|private.?key|aws_key|telegram_chat)',k,re.I)}
 return found
def scan(blobs,values):
 hits=[]
 for name,body in blobs:
  batches=[body]
  if name.endswith('.gz'):
   try:batches.append(gzip.decompress(body))
   except Exception:raise ValueError('Invalid selected compressed source: '+name)
  for variable,value in values.items():
   variants={value.encode(),json.dumps(value,ensure_ascii=False)[1:-1].encode()}
   if any(v and v in batch for v in variants for batch in batches):hits.append({'path':name,'variable':variable})
 return {'passed':not hits,'actual_configured_values_compared':True,'variables':sorted(values),'mandatory_variables_present':REQUIRED_SECRET_NAMES<=set(values),'matches':hits,'values_printed_or_recorded':False}
def contains_raw_research(value):
 pending=[value]
 while pending:
  item=pending.pop()
  if source_export.is_raw_web_response(item):return True
  if isinstance(item,dict):pending.extend(v for v in item.values()if isinstance(v,(dict,list)))
  elif isinstance(item,list):pending.extend(v for v in item if isinstance(v,(dict,list)))
 return False
def candidates():
 paths=set(ROOT_FILES);omitted=[]
 for folder,suffix in DATE_FOLDERS.items():
  paths.update(folder+'/'+date+suffix for date in DATES)
 paths.update('json/'+date+'_Market_Intelligence.json'for date in DATES)
 paths.update('notes/retail_'+date+'.json'for date in DATES)
 paths.update('notes/'+date+'_nonretail.json'for date in DATES)
 paths.update('collection/'+name for name in COLLECTION_TEXT)
 paths.add('retail/What_Retail_Is_Playing_2024-06.html')
 for folder,allowed in [('tools',{'.py'}),('data',{'.json'}),('reference',{'.txt','.json'}),('audit',{'.json','.gz','.csv'}),('checks',{'.json'}),('audit_work',{'.py','.json','.csv','.txt'})]:
  base=ROOT/folder
  for p in base.rglob('*'):
   rel=p.relative_to(ROOT).as_posix()
   if not p.is_file()or p.name.lower()=='claude.md' or set(p.relative_to(ROOT).parts)&FORBIDDEN_PARTS:continue
   if any(x!='2024-06'for x in re.findall(r'20\d{2}-\d{2}(?=-\d{2}(?:\D|$))',rel)):raise ValueError('Other report-month checkpoint path: '+rel)
   if p.suffix not in allowed:continue
   if folder in{'tools','data','reference'}and p.parent!=base:continue
   if rel in PRIVATE_RESEARCH:
    omitted.append({'path':rel,'reason':'Private original fullresearch response; publiccompactclockevidence and exacthashcommitment retained','private_research':True});continue
   if(folder=='audit'and p.name in EXTERNAL_AUDIT)or p.stat().st_size>MAX_TEXT_BYTES:omitted.append({'path':rel,'reason':'Large replay/transport proof retained in external frozen-source ZIP'});continue
   if p.suffix=='.gz'and not rel.startswith('audit/news_provenance/'):continue
   if p.suffix=='.csv'and rel!='audit/treasury_retained.csv':continue
   paths.add(rel)
 rows=[];missing=[]
 for rel in sorted(paths):
  if not(ROOT/rel).is_file():missing.append(rel);continue
  p=safe(rel)
  if set(PurePosixPath(rel).parts)&FORBIDDEN_PARTS or p.suffix in{'.pdf','.zip','.png','.pyc'}:raise ValueError('Unapproved checkpoint selection: '+rel)
  payload=gzip.decompress(p.read_bytes())if p.suffix=='.gz'else p.read_bytes()
  source_export.assert_no_raw_web_candidates(lambda name:payload,[rel])
  try:payload.decode('utf-8')
  except UnicodeError:raise ValueError('Nontext checkpoint selection: '+rel)
  try:parsed=json.loads(payload)
  except (ValueError,UnicodeDecodeError):
   if rel.endswith(('.json','.json.gz')):raise ValueError('Invalid selected checkpoint JSON: '+rel)
  else:
   if contains_raw_research(parsed):raise ValueError('Unregistered raw research response selected for Git: '+rel)
  rows.append(row(rel))
 return rows,omitted,missing
def delivery():
 blocked=[];bindings={};manifest={};source_descriptor={'status':'awaiting_complete_delivery'}
 for name in ['artifact_manifest.json','publication.json','delivery_verification.json']:
  p=ROOT/'checks'/name
  if not p.is_file():blocked.append('Missing checks/'+name)
  else:bindings['checks/'+name]=file_sha(p)
 if blocked:return blocked,bindings,source_descriptor
 manifest=json.loads((ROOT/'checks/artifact_manifest.json').read_text());pub=json.loads((ROOT/'checks/publication.json').read_text());verified=json.loads((ROOT/'checks/delivery_verification.json').read_text())
 if not(manifest.get('dates')==DATES and manifest.get('complete_month')is True and [x['date']for x in manifest.get('reports',[])]==DATES and manifest.get('artifact_targets')==65 and manifest.get('report_zip_members')==63):blocked.append('Final20-date/65-target/63-member manifest required')
 if pub.get('manifest_sha256')!=bindings['checks/artifact_manifest.json']or pub.get('dates')!=DATES or pub.get('stage')!='origin_verified'or len(pub.get('confirmed',{}))!=65 or len(pub.get('targets',[]))!=65 or pub.get('latest_write_performed')is not False or pub.get('lambda_write_performed')is not False:blocked.append('Complete unchanged-live June publication receipt required')
 objects=verified.get('objects',[]);members=verified.get('public_report_zip_members',[])
 if not(verified.get('passed')is True and len(objects)==65 and all(x.get('origin_sha256_pass')and x.get('public_sha256_pass')for x in objects)and len(members)==60 and all(x.get('sha256_pass')for x in members)and verified.get('lambda_code_and_runtime_unchanged')is True and verified.get('invalidation_status')=='Completed'):blocked.append('Passing complete June delivery proof required')
 artifacts=[x for report in manifest.get('reports',[])for x in report.get('files',{}).values()]+list(manifest.get('collection',{}).values())
 for x in artifacts:
  p=safe(x['path'])
  if p.stat().st_size!=x['bytes']or file_sha(p)!=x['sha256']:blocked.append('Manifest artifact bytes changed: '+x['path'])
 source=manifest.get('frozen_source_archive',{});archive=source.get('archive',{})
 if not archive:blocked.append('Frozen-source ZIP manifest binding required');return blocked,bindings,source_descriptor
 p=safe(archive['path'])
 with zipfile.ZipFile(p)as z:
  names=z.namelist()
  if len(names)!=len(set(names))or any(PurePosixPath(n).is_absolute()or'..'in PurePosixPath(n).parts or'\\'in n for n in names):raise ValueError('Unsafe external source ZIP inventory')
  raw=z.read('source_inventory.json');inventory=json.loads(raw)
  if SHA(json.dumps(inventory,sort_keys=True).encode())!=source.get('inventory_sha256')or len(inventory)!=source.get('files')or set(names)!={x['path']for x in inventory}|{'source_inventory.json'}:raise ValueError('External frozen-source inventory differs from manifest')
 families=Counter();sizes=Counter()
 for x in inventory:
  group='/'.join(x['path'].split('/')[:2])if x['path'].startswith(('cache/','audit/market_raw/','work/'))else x['path'].split('/')[0]
  families[group]+=1;sizes[group]+=x['bytes']
 source_descriptor={'status':'external_complete_frozen_source_archive','archive':archive,'public_url':'https://zembihf.xyz/reports/2024-06/June_2024_Frozen_Sources.zip','inventory_member':'source_inventory.json','inventory_member_sha256':SHA(raw),'inventory_canonical_sha256':source['inventory_sha256'],'inventory_files':len(inventory),'member_families':[{'family':k,'files':families[k],'bytes':sizes[k]}for k in sorted(families)],'restore':'Verify archive and inventory digests before extracting the missing raw/replay families to an isolated working June ROOT. The Git checkpoint deliberately omits raw caches and binary delivery artifacts.','individual_inventory_rows':{x['path']:x for x in inventory}}
 return blocked,bindings,source_descriptor
def build():
 identity=repo_identity();projection=source_export.public_research_export();rows,omitted,missing=candidates();blocked,bindings,external=delivery();blocked+=['Missing required checkpoint source: '+p for p in missing]
 if set(x['source']for x in rows)&PRIVATE_RESEARCH:raise ValueError('Private fullresearch response selected for Git')
 omitted_rows=[];lookup=external.pop('individual_inventory_rows',{})
 for x in omitted:
  r=row(x['path']);proof=lookup.get(x['path']);private=projection['commitments'].get(x['path']);omitted_rows.append({**x,'sha256':r['sha256'],'bytes':r['bytes'],'external_inventory_match':bool(proof and proof['sha256']==r['sha256']and proof['bytes']==r['bytes']),'private_commitment_match':bool(private and private['sha256']==r['sha256']and private['bytes']==r['bytes'])})
  if x.get('private_research'):
   if not omitted_rows[-1]['private_commitment_match']or proof:blocked.append('Private fullresearch commitment missing/altered or response leaked into publicZIP: '+x['path'])
  elif external.get('status')=='external_complete_frozen_source_archive'and not omitted_rows[-1]['external_inventory_match']:blocked.append('Omitted proof not bound in external ZIP: '+x['path'])
 external['externalized_selected_proof']=omitted_rows
 external['public_research_scope']={'manifest':'audit/public_research_manifest.json','manifest_sha256':projection['manifest_sha256'],'private_response_count':projection['private_response_count'],'public_original_research_byte_replay':False,'original33_private_responses_omitted_from_Git_and_public_ZIP':True,'financial_source_replay':'All financial RSS/market/feeds/guards/proofs remain public and strict. Complete144-binding local replay additionally requires retained private original research responses; public metadata is not replacement source bytes.'}
 runtime={'checkpoint_interpreter':sys.executable,'python':sys.version.split()[0],'packages':{name:package_version(name)for name in ['boto3','botocore','beautifulsoup4','playwright','pymupdf']},'limit':'This is checkpoint-runner metadata. A null package is not installed in this interpreter. The retained artifact-runtime review describes the separately verified build runtime; no dependencies are bundled.'}
 reference={'commit':BASE,'path':'corrections/2024-08','tracked_files':1079,'tracked_bytes':57159334,'method':'June retains the completed August checkpoint families; raw request/transport/replay inventories and raw provider/tool caches remain external, with exact ZIP/inventory hash pointers. June explicit editorial exclusions are also retained.'}
 generated={'.gitignore':b'__pycache__/\ncache/\nwork/\npdf/\ncollection/*.zip\nchecks/*.png\n*.tmp\n*.log\n',
 'checkpoint/external_raw_sources.json':JSON(external),'checkpoint/runtime_versions.json':JSON(runtime),'checkpoint/august_whitelist_reference.json':JSON(reference),'checkpoint/prepare_git_checkpoint.py':Path(__file__).read_bytes()}
 generated['README.md']=('June2024 retrospective checkpoint\n\n20 Monday–Friday editions, including exchange holidays. This directory preserves exact final source/code, derived input, component-draft, selection-note, independent-review and HTML/JSON/collection-text bytes.\n\nPublic collection: https://zembihf.xyz/reports/2024-06.html\nReport/PDF download: https://zembihf.xyz/reports/2024-06/June_2024_Weekday_Reports.zip\nRaw replay bundle: https://zembihf.xyz/reports/2024-06/June_2024_Frozen_Sources.zip\n\nSee checkpoint/external_raw_sources.json for exact archive/inventory digests and omitted-proof bindings. Raw RSS/request caches, original market payloads, very large transport ledgers/inventories, scratch, dependency environments, PDFs and ZIPs are external. Original33fullresearch MCPresponses stay private and are absent from Git and the publicZIP. The publicprojection retains compact release-clock facts/document URLs and exact originalhashcommitments; it does not claim public original-research byte replay. Processed data/*.json, final feeds and cards remain here. Restore missing raw families from the verified frozen-source ZIP in an isolated working ROOT; do not acquire replacement historical data. Complete local144-binding replay additionally requires the retained33private original research responses; the publiccompactmetadata cannot substitute for their bytes.\n\nThe archived tools preserve their reviewed execution paths. To replay the original workspace workflow, restore this checkpoint and verified external raw families under /workspace/work/june2024, install the recorded runtime dependencies separately, and restore the exact shared retail gate from audit_work/shared_retail_quality_original.py under /workspace/work/retail-quality/retail_quality.py. Review BRIEF.md and AUTHORING.md first. No publication, Lambda invocation/deployment, email or Telegram occurs merely by restoring the checkpoint.\n\nchecks/artifact_manifest.json, publication.json and delivery_verification.json bind exact final delivery. Git excludes binary deliverables; PDF delivery is through the public report ZIP. No old checkpoint, live/latest report or repository root configuration is changed by this snapshot. The checkpoint preparation script only copies/stages after an explicit --go and never commits or pushes.\n').encode()
 generated['checkpoint/copied_source_inventory.json']=JSON({'source_root':str(ROOT),'files':rows,'generated_files':[{'path':name,'sha256':SHA(body),'bytes':len(body)}for name,body in sorted(generated.items())],'scope':'This inventory lists copied original inputs and generated provenance; its own digest is recorded in the external copy plan to avoid a circular hash.'})
 values=credentials();secret_scan=scan([(x['destination'],safe(x['source']).read_bytes())for x in rows]+list(generated.items()),values)
 if not secret_scan['mandatory_variables_present']:blocked.append('Actual AWS_KEY/AWS_SECRET/GH_TOKEN comparisons required')
 if not secret_scan['passed']:blocked.append('A configured credential value matched selected Git content; values were not recorded')
 generated_rows=[{'destination':name,'sha256':SHA(body),'bytes':len(body),'generated':True}for name,body in sorted(generated.items())]
 plan={'version':'june2024-reviewed-copy-plan-v1','ready_for_copy_after_delivery':not blocked,'blocked':blocked,'repo':identity,'destination':DEST.as_posix(),'source_root':str(ROOT),'source_files':rows,'generated_files':generated_rows,'source_file_count':len(rows),'total_file_count':len(rows)+len(generated),'total_bytes':sum(x['bytes']for x in rows+generated_rows),'files_by_top_level':dict(sorted(Counter(x['destination'].split('/')[0]for x in rows+generated_rows).items())),'omitted_proof_files':len(omitted_rows),'delivery_bindings':bindings,'credential_scan':secret_scan,'whitespace_command':['git','-c','core.whitespace=cr-at-eol','diff','--cached','--check','--','corrections/2024-06'],'commit_performed':False,'push_performed':False,'repo_mutation_in_plan_mode':False,'script_sha256':file_sha(Path(__file__))}
 return plan,generated
def go(expected):
 if not expected or not PLAN.is_file()or file_sha(PLAN)!=expected:raise ValueError('Exact reviewed copy-plan SHA256 required')
 approved=json.loads(PLAN.read_text());current,generated=build()
 if current!=approved or not current['ready_for_copy_after_delivery']:raise ValueError('Reviewed plan changed or final delivery preconditions remain incomplete')
 staging=Path(tempfile.mkdtemp(prefix='june-git-copy-',dir=ROOT/'work'))
 try:
  for x in current['source_files']:
   p=staging/x['destination'];p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(safe(x['source']),p)
   if p.stat().st_size!=x['bytes']or file_sha(p)!=x['sha256']:raise ValueError('Copied source bytes differ: '+x['destination'])
  for name,body in generated.items():
   p=staging/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(body)
  scan_result=scan([(p.relative_to(staging).as_posix(),p.read_bytes())for p in staging.rglob('*')if p.is_file()],credentials())
  if not scan_result['passed']or not scan_result['mandatory_variables_present']:raise ValueError('Final staged copy credential scan failed')
  repo_identity();os.rename(staging,REPO/DEST)
  git('add','--',DEST.as_posix())
  names=[x.decode()for x in git('diff','--cached','--name-only','-z').stdout.split(b'\0')if x]
  if any(not x.startswith(DEST.as_posix()+'/')for x in names)or len(names)!=current['total_file_count']:raise ValueError('Unexpected staged Git scope')
  checked=git('-c','core.whitespace=cr-at-eol','diff','--cached','--check','--',DEST.as_posix(),check=False)
  errors=sorted(set(re.findall(rb'corrections/2024-06/[^:\r\n]+:\d+',checked.stdout+checked.stderr)))
  receipt={'status':'copied_and_staged_for_root_review'if checked.returncode==0 else'copied_and_staged_but_whitespace_check_failed','plan_sha256':expected,'script_sha256':file_sha(Path(__file__)),'files':len(names),'bytes':current['total_bytes'],'credential_scan':scan_result,'git_diff_check_passed':checked.returncode==0,'whitespace_error_locations':[x.decode('utf-8','replace')for x in errors],'staged_paths_sha256':SHA(JSON(names)),'branch':BRANCH,'base_commit':BASE,'destination':DEST.as_posix(),'existing_checkpoints_modified':False,'commit_performed':False,'push_performed':False}
  RECEIPT.write_bytes(JSON(receipt));print(json.dumps({k:v for k,v in receipt.items()if k!='credential_scan'},indent=2));return 0 if checked.returncode==0 else 1
 finally:
  if staging.exists():shutil.rmtree(staging)
def main():
 p=argparse.ArgumentParser();p.add_argument('--go',action='store_true');p.add_argument('--plan-sha256');args=p.parse_args()
 if args.go:return go(args.plan_sha256)
 plan,_=build();PLAN.write_bytes(JSON(plan));print(json.dumps({'plan':str(PLAN),'sha256':file_sha(PLAN),'ready':plan['ready_for_copy_after_delivery'],'files':plan['total_file_count'],'bytes':plan['total_bytes'],'blocked':plan['blocked'],'credential_scan':{k:v for k,v in plan['credential_scan'].items()if k!='matches'},'repo_mutation':False},indent=2));return 0
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as exc:print(json.dumps({'status':'blocked','error_type':type(exc).__name__,'error':str(exc)},ensure_ascii=False));raise SystemExit(1)
