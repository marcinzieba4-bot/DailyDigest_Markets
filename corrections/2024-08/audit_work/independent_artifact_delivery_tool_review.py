"""Read-only static and predicate review; no builder, publisher or delivery entrypoint runs."""
from pathlib import Path,PurePosixPath
import ast,datetime as dt,hashlib,json,re,unicodedata,zipfile
from bs4 import BeautifulSoup
from pypdf import PdfReader
R=Path('/workspace/work/august2024');errors=[];checks=[]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def ck(ok,name,detail=None):
 checks.append({'check':name,'passed':bool(ok),**({'detail':detail} if detail is not None else {})})
 if not ok:errors.append(name)
names=['build_artifacts.py','build_source_inventory.py','verify_delivery.py','render.py','build_retail_page.py','publish.py'];sources={n:(R/'tools'/n).read_text() for n in names};hashes={n:sha(R/'tools'/n) for n in names};trees={n:ast.parse(sources[n]) for n in names};ck(len(trees)==6,'six tools parse as Python')
dates=[dt.date(2024,8,n).isoformat() for n in range(1,32) if dt.date(2024,8,n).weekday()<5];ck(len(dates)==22 and dates[0]=='2024-08-01' and dates[-1]=='2024-08-30','22 correct weekday dates');ck('manifest[\'artifact_targets\']!=71' in sources['build_artifacts.py'] and "manifest['report_zip_members']!=69" in sources['build_artifacts.py'],'builder asserts full-month71 targets and69 ZIP members');ck("if dates!=sorted(set(dates)) or any(d not in DATES for d in dates)" in sources['build_artifacts.py'],'builder rejects invalid/duplicate/unsorted dates');ck("if manifest.get('dates') != DATES or not manifest.get('complete_month')" in sources['publish.py'] and "len(targets) != 71" in sources['publish.py'],'publisher rejects partial local preview and requires71 unique targets');ck("set(row['files']) != {'html', 'json', 'pdf'}" in sources['publish.py'],'publisher requires all three formats per report')
# Execute only the newly inspected exact-set predicates with synthetic objects.
main=next(n for n in trees['verify_delivery.py'].body if isinstance(n,ast.FunctionDef) and n.name=='main')
assign=lambda n,name:isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets)
update=lambda n,name:isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute) and isinstance(n.value.func.value,ast.Name) and n.value.func.value.id==name and n.value.func.attr=='update'
target_nodes=[n for n in main.body if assign(n,'dates') or assign(n,'expected_targets') or update(n,'expected_targets') or (isinstance(n,ast.If) and 'receipt.get(\'dates\')' in ast.unparse(n.test))]
ck(len(target_nodes)==4,'isolate exact delivery-receipt predicate without network code')
expected_targets={k for d in dates for k in (f'reports/archive/{d}.html',f'Strategies/json/{d}_Market_Intelligence.json',f'Strategies/{d}_Market_Intelligence.pdf')};expected_targets.update({'reports/2024-08.html','reports/2024-08/August_2024_Weekday_Reports.zip','reports/2024-08/August_2024_Frozen_Sources.zip','reports/2024-08/What_Retail_Is_Playing_2024-08.html','reports/2024-08/methodology.txt'})
def run(nodes,env):exec(compile(ast.Module(body=nodes,type_ignores=[]),'<isolated-read-only-predicate>','exec'),env)
def allowed(nodes,env):
 try:run(nodes,env);return True
 except ValueError:return False
base={'dates':dates,'targets':[{'key':k} for k in sorted(expected_targets)]}
cases={'valid':(base,True),'missing_target':({'dates':dates,'targets':base['targets'][:-1]},False),'duplicate_target':({'dates':dates,'targets':base['targets'][:-1]+base['targets'][:1]},False),'foreign_target':({'dates':dates,'targets':base['targets'][:-1]+[{'key':'reports/archive/2024-09-02.html'}]},False),'extra_target':({'dates':dates,'targets':base['targets']+base['targets'][:1]},False),'wrong_dates':({'dates':dates[1:],'targets':base['targets']},False)}
for label,(receipt,want) in cases.items():ck(allowed(target_nodes,{'dt':dt,'receipt':receipt})==want,'delivery target predicate: '+label)
zip_nodes=[n for n in ast.walk(main) if assign(n,'expected_members') or update(n,'expected_members') or (isinstance(n,ast.If) and 'len(archive.namelist()) != 69' in ast.unparse(n.test))];ck(len(zip_nodes)==3,'isolate exact69 public ZIP predicate')
expected_members={p for d in dates for p in (f'html/{d}.html',f'json/{d}_Market_Intelligence.json',f'pdf/{d}_Market_Intelligence.pdf')};expected_members.update({'index.html','methodology.txt','What_Retail_Is_Playing_2024-08.html'})
class Archive:
 def __init__(self,names):self.names=names
 def namelist(self):return self.names
base_names=sorted(expected_members)
for label,names,want in [('valid',base_names,True),('missing',base_names[:-1],False),('duplicate',base_names[:-1]+base_names[:1],False),('foreign',base_names[:-1]+['../outside'],False),('extra',base_names+['extra'],False)]:ck(allowed(zip_nodes,{'dates':dates,'archive':Archive(names)})==want,'public ZIP membership predicate: '+label)
fn=next(n for n in trees['build_artifacts.py'].body if isinstance(n,ast.FunctionDef) and n.name=='source_archive');guard=next(n for n in fn.body if isinstance(n,ast.For) and isinstance(n.target,ast.Name) and n.target.id=='path' and isinstance(n.iter,ast.Name) and n.iter.id=='paths')
class Parent:
 def is_symlink(self):return True
 def is_relative_to(self,root):return True
class Entry:
 def __init__(self,resolve=None,file=True,symbolic=False,parent=False):self.target=resolve or R/'tools/render.py';self.file=file;self.symbolic=symbolic;self.parents=[Parent()] if parent else []
 def resolve(self):return self.target
 def is_file(self):return self.file
 def is_symlink(self):return self.symbolic
 def __str__(self):return 'isolated synthetic source candidate'
for label,path,want in [('valid',Entry(),True),('outside_root',Entry(resolve=R.parent/'outside.py'),False),('missing_file',Entry(file=False),False),('symlink_file',Entry(symbolic=True),False),('symlink_parent',Entry(parent=True),False)]:ck(allowed([guard],{'ROOT':R,'paths':[path]})==want,'all-source archive path predicate: '+label)
ck('1–30 August 2024' in sources['build_retail_page.py'] and '2–30 August 2024' not in sources['build_retail_page.py'],'retail collection subtitle startsAug1')
ck("page.evaluate(\"document.querySelectorAll('details').forEach(x=>x.open=true)\")" in sources['build_artifacts.py'],'all source-ledger details opened before PDF');ck("'Dated evidence'" in sources['build_artifacts.py'] and 'PDF missing' in sources['build_artifacts.py'],'builder extracts PDF text and checks ledger marker');ck("for key,num in doc.used.items()" in sources['render.py'] and "'evidence':{k:doc.evidence[k] for k in doc.used}" in sources['render.py'],'renderer emits every used source in HTML ledger and JSON evidence');ck("len(members)==66" in sources['verify_delivery.py'] and "archive.testzip()" in sources['verify_delivery.py'],'delivery checks all66 report bodies and public ZIP CRC');ck("obj['sha256']==item['sha256'] and obj['bytes']==item['bytes']" in sources['verify_delivery.py'] and "hashlib.sha256(body).hexdigest()==item['sha256']" in sources['verify_delivery.py'],'delivery compares origin and public full-body SHA/size');ck("if item['key'].startswith('Strategies/')" in sources['verify_delivery.py'] and "row['public_bundle_member']=artifact['path']" in sources['verify_delivery.py'],'PDF/JSON public delivery verified through canonical report ZIP rather than fallback route');ck("protected==receipt['protected_before']" in sources['verify_delivery.py'] and "archive_links_preserved" in sources['verify_delivery.py'] and "lambda_unchanged" in sources['verify_delivery.py'],'delivery checks protected bodies/index links and live Lambda metadata')
# Existing local preview is evidence about pipeline behavior only, not a final month.
m_path=R/'checks/artifact_manifest.json';m=json.load(open(m_path));preview={'dates':m['dates'],'complete_month':m['complete_month'],'artifact_targets':m['artifact_targets'],'report_zip_members':m['report_zip_members'],'manifest_sha256':sha(m_path)};ck(m['complete_month'] is False and len(m['dates'])==1,'existing build is explicitly partial preview')
inv_path=R/'audit/news_replay_inventory.json';inv=json.load(open(inv_path));inv_errors=[]
for row in inv['files']:
 p=PurePosixPath(row['path']);f=R/p
 if p.is_absolute() or '..' in p.parts or str(p)!=row['path'] or f.is_symlink() or not f.resolve().is_relative_to(R) or not f.is_file():inv_errors.append(row['path']+':unsafe');continue
 if sha(f)!=row['sha256'] or f.stat().st_size!=row['bytes']:inv_errors.append(row['path']+':hash/bytes')
ck(not inv_errors,'all current replay-inventory paths/content hashes',{'files':len(inv['files']),'errors':inv_errors});ck(inv['source_acceptance_sha256']==sha(R/'audit/independent_source_review.json') and inv['market_acceptance_sha256']==sha(R/'audit/independent_market_review.json'),'replay inventory binds current source/market acceptances')
archive_meta=m['frozen_source_archive']['archive'];source_errors=[]
with zipfile.ZipFile(R/archive_meta['path']) as z:
 invrows=json.loads(z.read('source_inventory.json'));names=z.namelist()
 if len(names)!=len(set(names)) or set(names)!={row['path'] for row in invrows}|{'source_inventory.json'}:source_errors.append('membership')
 for name in names:
  p=PurePosixPath(name)
  if p.is_absolute() or '..' in p.parts or str(p)!=name:source_errors.append(name+':unsafe')
 for row in invrows:
  body=z.read(row['path'])
  if hashlib.sha256(body).hexdigest()!=row['sha256'] or len(body)!=row['bytes']:source_errors.append(row['path']+':hash/bytes')
ck(not source_errors and sha(R/archive_meta['path'])==archive_meta['sha256'],'preview frozen-source archive internal inventory/body hashes',{'members':len(names),'files':len(invrows),'errors':source_errors});preview['source_archive_members']=len(names);preview['source_archive_files']=len(invrows)
pdf_details=[]
for rep in m['reports']:
 soup=BeautifulSoup((R/rep['files']['html']['path']).read_text(),'html.parser');data=json.load(open(R/rep['files']['json']['path']));pdf=PdfReader(R/rep['files']['pdf']['path']);text=' '.join(p.extract_text() or '' for p in pdf.pages);norm=lambda t:' '.join(re.findall(r'\w+',unicodedata.normalize('NFKC',t).lower()));nt=norm(text);missing=[key for key,e in data['evidence'].items() if norm(e['title']) not in nt];count=len(data['evidence']);ck(count==len(soup.select('details.ledger ol li')) and not missing,'preview full cited-headline ledger present in PDF',{'date':rep['date'],'pages':len(pdf.pages),'sources':count,'missing_full_headlines':missing});ck(all(sha(R/x['path'])==x['sha256'] and (R/x['path']).stat().st_size==x['bytes'] for x in rep['files'].values()),'preview three artifact hashes match manifest');pdf_details.append({'date':rep['date'],'pdf_pages':len(pdf.pages),'ledger_sources':count,'all_full_headlines_found':not missing})
ck(all(sha(R/'tools'/n)==v for n,v in hashes.items()),'tool hashes stable over this final review pass')
result={'status':'reviewed_code_and_local_preview_only' if not errors else 'code_review_failed','passed':not errors,'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'scope':'Independent static code inspection and isolated exact-predicate tests of local artifact packaging and read-only delivery verification. No full-month artifact, prose, origin/public delivery or publication approval. No builder, acquisition/amendment or network/publication entrypoint executed.','checks':checks,'errors':errors,'tool_sha256':hashes,'reviewer_tool_sha256':sha(Path(__file__)),'full_month_expected':{'dates':dates,'reports':22,'daily_artifacts':66,'collection_artifacts':5,'targets':71,'report_zip_members':69},'preview':preview,'preview_pdf_ledger_checks':pdf_details,'replay_inventory_sha256':sha(inv_path),'source_amendment_review_sha256':sha(R/'audit/independent_source_amendment_review.json'),'resolved_findings':[{'finding':'retail collection subtitle beganAug2','resolution':'Current template starts1–30Aug2024.'},{'finding':'final source-archive glob inputs lacked all-path safety check','resolution':'Current builder rejects escape/missing/symlink-file/symlink-parent candidates; five isolated predicate cases tested.'},{'finding':'delivery relied on publisher counts rather than exact independent key/member sets','resolution':'Current delivery verifier independently requires71 exact August target keys and69 exact public ZIP member names; positive/negative fixtures tested.'}],'limitations':['Only the existing one-date local preview was opened; all22 final PDFs, ledgers, collections and final source archive must be rebuilt and checked after prose freezes.','Origin/public HTTPS, actual protected-object preservation, archive-index merge and invalidation completion were inspected in code but not executed here.','Native PDF/JSON public delivery is through the verified report ZIP; direct /Strategies fallback URLs are not treated as downloads.','Final replay inventory should include both independent review scripts under audit_work and be refreshed before the final source archive is built.']}
out=R/'checks/independent_artifact_delivery_tool_review.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'passed':not errors,'checks':len(checks),'errors':errors,'tool_sha256':hashes,'review_sha256':sha(out)},indent=2))
