"""Read-only compatibility check of current source producer and artifact packaging.

No factual report or collection build, source mutation, remote access or delivery
claim. Uses the same replay collection function as the source inventory producer;
the archive consumer then verifies current bindings and exact physical body bytes.
"""
from pathlib import Path
import datetime as dt,hashlib,importlib.util,json,sys
ROOT=Path(__file__).resolve().parent.parent

def module(name,path):
 info=importlib.util.spec_from_file_location(name,path);obj=importlib.util.module_from_spec(info);sys.modules[name]=obj;info.loader.exec_module(obj);return obj

def main():
 inventory=module('july_integration_inventory',ROOT/'tools/build_source_inventory.py')
 auditor=module('july_integration_auditor',ROOT/'audit_work/review_final_artifacts.py')
 builder=module('july_integration_builder',ROOT/'tools/build_artifacts.py')
 paths=inventory.collect_paths()
 for folder,pattern in [('tools','*.py'),('data','*.json'),('audit','*.json'),('audit','*.jsonl'),('audit','*.json.gz'),('notes','*.json'),('reference','*.txt'),('reference','*.json')]:
  paths.update((ROOT/folder).glob(pattern))
 excluded={'source_archive_build.json','artifact_manifest.json','delivery_verification.json','final_artifact_review.json','publication.json','archive_index_reconciliation.json'}
 paths.update(p for p in (ROOT/'checks').rglob('*.json') if p.name not in excluded)
 for name in ('BRIEF.md','AUTHORING.md','README.md'):
  if (ROOT/name).is_file():paths.add(ROOT/name)
 for date in builder.DATES:
  for folder,suffix in [('specs','.json'),('cards','.json'),('feeds','.json.gz'),('nonretail_drafts','.json'),('retail_drafts','.json')]:
   p=ROOT/folder/(date+suffix)
   if p.is_file():paths.add(p)
 names={path.relative_to(ROOT).as_posix() for path in paths}
 class IntendedArchive:
  def __init__(self):self.cache={}
  def namelist(self):return list(names)
  def read(self,name):
   if name not in names:raise ValueError('Path outside intended package '+name)
   if name not in self.cache:self.cache[name]=auditor.local_member(name).read_bytes()
   return self.cache[name]
 archive=IntendedArchive()
 source=json.loads(archive.read('audit/independent_source_review.json'))
 freeze=json.loads(archive.read('audit/source_freeze.json'))
 result=auditor.current_source_dependencies(archive,source,freeze)
 market=json.loads(archive.read('audit/independent_market_review.json'))
 for name,digest in market['input_sha256'].items():
  if name not in names or auditor.sha(archive.read(name))!=digest:raise ValueError('Market replay input missing or changed '+name)
 schemas=['reference/retail_schema.json','reference/nonretail_schema.json']
 for name in schemas:
  if name not in names:raise ValueError('Missing schema '+name)
 sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
 root_patch=json.loads((ROOT/'audit/integration_patch_pending.json').read_text())
 tool_paths=['tools/render.py','tools/build_artifacts.py','tools/build_retail_page.py','tools/build_source_inventory.py','audit_work/review_final_artifacts.py','audit_work/preview_first_edition.py','audit_work/review_artifact_integration.py']
 result.update(status='current_source_packaging_compatible',reviewed_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
  month_artifacts_reviewed=False,public_delivery_reviewed=False,source_facts_or_authored_text_changed=False,
  intended_package_paths=len(names),market_input_bindings=len(market['input_sha256']),
  jsonl_physical_ledger_included='audit/news_physical_requests.jsonl' in names,
  reference_schema_sha256={name:sha(ROOT/name) for name in schemas},
  input_sha256={name:sha(ROOT/name) for name in ['audit/independent_source_review.json','audit/source_freeze.json','audit/independent_market_review.json','audit/news_physical_requests.jsonl','audit_work/physical_source_inventory.json','code_provenance.json','checks/code_discovery.json']},
  tool_sha256={name:sha(ROOT/name) for name in tool_paths},
  root_patch_receipt_sha256=sha(ROOT/'audit/integration_patch_pending.json'),
  reviewed_root_deltas=['JSONL safe-path allowlist and top-level audit inclusion preserve all prior path guards.','Reference JSON schemas are included as exact current template bytes.','Current source input_bindings, tool/contract/reviewer dependency maps, physical ledger/immutable attempts/canonical XML/cache hashes, policy lock, source freeze and newest-code source provenance are all checked by the final archive consumer.'],
  finalizer_scope='Not edited or reviewed here; writer_late owns the source-schema finalizer integration recheck.',
  code_provenance_limit='retrospective_tool_sha256 describes upstream toolkit bytes; adapted current tools have separate current hashes and are not asserted to equal upstream.')
 path=ROOT/'audit/artifact_runtime_integration.json';path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items() if k not in ['input_sha256','tool_sha256']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
