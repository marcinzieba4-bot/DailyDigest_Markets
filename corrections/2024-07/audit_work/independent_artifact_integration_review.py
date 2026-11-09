"""Independent current-input transport and existing July1 preview verification.
No factual research, report generation, month build, publication or external send.
"""
from pathlib import Path,PurePosixPath
import hashlib,json,gzip,datetime as dt,importlib.util,sys,re
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'work/artifact_dependencies'))
from bs4 import BeautifulSoup
from pypdf import PdfReader
from playwright.sync_api import sync_playwright

def module(name,path):
 info=importlib.util.spec_from_file_location(name,path);obj=importlib.util.module_from_spec(info);sys.modules[name]=obj;info.loader.exec_module(obj);return obj
sha=lambda blob:hashlib.sha256(blob).hexdigest()
def safe(name):
 rel=PurePosixPath(name)
 if rel.is_absolute() or '..' in rel.parts or str(rel)!=name or '\\' in name or any(v.startswith('.') for v in rel.parts):raise ValueError('Unsafe bound path '+name)
 path=ROOT/rel
 if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(ROOT) or any(v.is_symlink() for v in path.parents if v.is_relative_to(ROOT)):raise ValueError('Missing/unsafe local path '+name)
 return path
checks=0

def ck(ok,message):
 global checks
 checks+=1
 if not ok:raise ValueError(message)
def bound(name,digest):
 blob=safe(name).read_bytes();ck(sha(blob)==digest,'Changed bound file '+name);return blob

def main():
 source=json.loads(safe('audit/independent_source_review.json').read_bytes());market=json.loads(safe('audit/independent_market_review.json').read_bytes());freeze=json.loads(safe('audit/source_freeze.json').read_bytes())
 ck(source['passed'] is True and not source['errors'] and market['passed'] is True and not market['errors'],'Independent input acceptance not current')
 freeze_digest=sha(safe('audit/source_freeze.json').read_bytes());ck(source['source_freeze_sha256']==market['source_freeze_sha256']==freeze_digest,'Freeze binding differs')
 for name,digest in source['input_bindings'].items():bound(name,digest)
 for name,digest in market['input_sha256'].items():bound(name,digest)
 for field,prefix in [('tool_sha256','tools/'),('contract_sha256',''),('reviewer_dependency_sha256','audit_work/')]:
  for name,digest in source[field].items():bound(prefix+name,digest)
 bound('audit_work/review_sources.py',source['reviewer_tool_sha256'])
 ledger_blob=bound('audit/news_physical_requests.jsonl',source['ledger_sha256']);ledger=[json.loads(row) for row in ledger_blob.decode().splitlines() if row.strip()]
 ck(len(ledger)==source['physical_attempts'],'Physical ledger count differs')
 identities=set();bodies=set();per_signature={}
 for row in ledger:
  identity=(row['signature'],row['attempt']);ck(identity not in identities,'Duplicate attempt identity');identities.add(identity);per_signature[row['signature']]=per_signature.get(row['signature'],0)+1
  name=row.get('raw_response_path')
  if name:
   ck(name.startswith('cache/rss_raw/attempts/') and name not in bodies,'Attempt body not immutable/unique');blob=bound(name,row['raw_compressed_sha256']);ck(sha(gzip.decompress(blob))==row['raw_sha256'],'Physical body uncompressed hash differs');bodies.add(name)
  if row.get('status')=='fetched':ck(bool(name),'Fetched request lacks body')
 ck(len(bodies)==source['received_attempt_bodies'],'Received body count differs')
 actual={p.relative_to(ROOT).as_posix() for p in (ROOT/'cache/rss_raw/attempts').rglob('*') if p.is_file()};ck(actual==bodies,'Attempt directory differs from ledger')
 physical=json.loads(bound('audit_work/physical_source_inventory.json',source['physical_source_inventory_sha256']))
 ck(len(physical['files'])==source['physical_requests'],'Canonical inventory count differs')
 for row in physical['files']:
  ck(per_signature[row['signature']]==row['physical_attempts'],'Per-signature attempt count differs');bound(row['parsed_cache_path'],row['parsed_cache_sha256']);blob=bound(row['raw_xml_path'],row['raw_xml_compressed_sha256']);ck(sha(gzip.decompress(blob))==row['raw_xml_uncompressed_sha256'],'Canonical XML differs')
 ck('audit_work/news_policy_lock.json' in source['input_bindings'],'Source acceptance does not bind policy lock itself')
 policy=json.loads(safe('audit_work/news_policy_lock.json').read_bytes())
 for name,digest in policy['files'].items():bound(name,digest)
 provenance=json.loads(safe('code_provenance.json').read_bytes());discovery=json.loads(safe('checks/code_discovery.json').read_bytes());bound('newest_lambda_function.py',provenance['source_sha256']);ck(discovery['source_sha256']==provenance['source_sha256'],'Selected newest-code digest differs')
 # Existing accepted single-date artifacts only; do not call render/build/preview main.
 receipt_path='work/first_edition_preview/preview_receipt.json';preview=json.loads(safe(receipt_path).read_bytes());ck(preview['status']=='accepted_single_edition_preview' and preview['report_date']=='2024-07-01','Preview scope differs')
 for name,digest in preview['input_sha256'].items():bound(name,digest)
 for name,digest in preview['files'].items():bound(name,digest)
 builder=module('independent_preview_builder',ROOT/'tools/build_artifacts.py');auditor=module('independent_preview_auditor',ROOT/'audit_work/review_final_artifacts.py');renderer=module('independent_layout_renderer',ROOT/'tools/render.py')
 builder.accepted_components(['2024-07-01'])
 # Independent renderer transport checks retain source characters, using synthetic strings.
 for value in ['Date 2024-06-28T07:00:00+00:00 stays exact.','A total-return-tracker needs no spelling change.','Łódź −3.2% & <tag> on 2024-13-99.','ISO 2024-07-01T00:00:00.123456-04:00 and non‑breaking compound.']:
  ck(BeautifulSoup(renderer.esc(value),'html.parser').get_text()==value,'Renderer changed literal token text')
 for normalize in (builder.prose_key,auditor.normal):
  ck(normalize('Risk [100] remains.')!=normalize('Risk remains.'),'Normalizer erased numeric literal');ck(normalize('Now here')!=normalize('Nowhere'),'Normalizer erased word boundary')
 date='2024-07-01';payload=json.loads(safe(f'json/{date}_Market_Intelligence.json').read_bytes());spec=json.loads(safe(f'specs/{date}.json').read_bytes());ck(payload['spec']==spec,'Preview JSON spec differs from current accepted spec')
 feed=json.loads(gzip.decompress(safe(f'feeds/{date}.json.gz').read_bytes()));exceptions_path=ROOT/'audit/canonical_source_exceptions.json';exceptions=json.loads(exceptions_path.read_bytes()).get('exceptions',[]) if exceptions_path.exists() else [];auditor.validate_evidence(payload['evidence'],spec,feed,exceptions,date)
 html_path=safe(f'html/{date}.html');page=BeautifulSoup(html_path.read_bytes(),'html.parser');html_count=auditor.html_preservation(page,spec,payload['evidence'],date)
 pdf=PdfReader(safe(f'work/first_edition_preview/{date}.pdf'));preservation=builder.check_pdf_prose(date,pdf,spec,payload['evidence']);footer=re.compile(r'(?m)^'+re.escape(date)+r'\s*·\s*Market Intelligence Briefing\s*·\s*\d+\s*/\s*\d+\s*$');text='\n'.join(footer.sub('',p.extract_text() or '') for p in pdf.pages);pdf_count=auditor.pdf_preservation(date,text,spec,payload['evidence'])
 ck(html_count==pdf_count==preservation['paragraphs_preserved']==149,'July1 ordered paragraph count differs');ck(preservation['ledger_headlines_preserved']==len(payload['evidence'])==129,'July1 ordered ledger count differs');ck(len(pdf.pages)==29,'July1 PDF page count differs')
 layouts=[]
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox']);tab=browser.new_page()
  for width,height in [(1440,1000),(390,844)]:
   tab.set_viewport_size({'width':width,'height':height});tab.set_content(html_path.read_text(),wait_until='load');measurement=tab.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth,headings:document.querySelectorAll("h2[id]").length})');ck(measurement['scroll']<=width and measurement['headings']==9,'Existing preview overflow/section failure');layouts.append(measurement)
  browser.close()
 integration=json.loads(safe('audit/artifact_runtime_integration.json').read_bytes());ck(integration['source_input_bindings']==len(source['input_bindings']) and integration['market_input_bindings']==len(market['input_sha256']),'Owner integration coverage differs');ck(integration['received_attempt_bodies']==len(bodies),'Owner integration body count differs')
 for name,digest in integration['input_sha256'].items():bound(name,digest)
 for name,digest in integration['tool_sha256'].items():bound(name,digest)
 tool_names=['tools/render.py','tools/build_artifacts.py','tools/build_retail_page.py','tools/build_source_inventory.py','audit_work/review_final_artifacts.py','audit_work/review_artifact_integration.py','audit_work/preview_first_edition.py']
 tool_hashes={name:sha(safe(name).read_bytes()) for name in tool_names}
 own_static=json.loads(safe('audit/independent_artifact_tool_review.json').read_bytes());ck(own_static['status']=='accepted' and own_static['fatal_or_major_remaining']==0,'Own static review not accepted')
 for name,digest in own_static['tool_sha256'].items():bound(name,digest)
 inputs={name:sha(safe(name).read_bytes()) for name in ['audit/independent_source_review.json','audit/source_freeze.json','audit/independent_market_review.json','audit/independent_artifact_tool_review.json','audit/artifact_runtime_integration.json','checks/artifact_tool_review.json',receipt_path]}
 result={'status':'accepted','reviewed_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'scope':'Independent static-delta/input-transport and existing accepted July1 presentation replay. No factual/editorial reinterpretation and no report generation.','fatal_or_major_remaining':0,'independent_assertions':checks,'source_input_bindings':len(source['input_bindings']),'market_input_bindings':len(market['input_sha256']),'physical_attempts':len(ledger),'received_immutable_attempt_bodies':len(bodies),'canonical_physical_requests':len(physical['files']),'owner_source_hash_checks_replayed':integration['source_dependency_hash_checks'],'source_freeze_sha256':freeze_digest,'input_sha256':inputs,'tool_sha256':tool_hashes,'reviewer_script_sha256':sha(Path(__file__).read_bytes()),'single_edition_preview':{'date':date,'ordered_paragraphs':pdf_count,'ordered_complete_ledger_records':len(payload['evidence']),'PDF_pages':len(pdf.pages),'layout':layouts,'existing_preview_files_sha256':preview['files'],'new_artifacts_generated':False},'month_artifacts_reviewed':False,'public_delivery_reviewed':False,'cloud_writes_performed':False,'source_or_report_mutations_performed':False,'reviewed_deltas':['ISO date/timestamp and written hyphenated token protection preserves exact characters and HTML escaping; strict Unicode/literal/word-boundary normalizers remain unchanged.','JSONL ledger and reference JSON schema packaging use producer collect_paths and keep canonical, hidden-path, symlink, repository and credential guards.','Final archive checker verifies current source input_bindings and tool/contract/reviewer dependencies, policy/freeze/newest-code identity, all immutable physical bodies and canonical XML/cache bytes.','Existing July1 HTML/JSON/PDF and screenshots match accepted preview receipt hashes; both strict ordered PDF tests and exact HTML/evidence checks replay successfully.'],'limits':['This accepts engineering and July1 presentation only. All23 actual report artifacts, source/report ZIP members, monthly retail collection and public delivery still need final runtime checks.','Authored July1 prose was loaded programmatically only for exact preservation checks; no source claim or financial interpretation was reviewed or changed here.','The finalizer is outside this review and remains writer_late/root responsibility.','The integration snapshot is not a final archive: author files can be added subsequently, requiring a fresh full inventory/build/final-artifact review.']}
 (ROOT/'audit/independent_artifact_integration_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({key:result[key] for key in ['status','independent_assertions','source_input_bindings','market_input_bindings','physical_attempts','canonical_physical_requests','month_artifacts_reviewed','public_delivery_reviewed']}));print('RECEIPT_SHA256',sha((ROOT/'audit/independent_artifact_integration_review.json').read_bytes()))
if __name__=='__main__':main()
