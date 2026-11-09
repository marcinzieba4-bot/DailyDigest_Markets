"""Independent candidate/guard tests only; no actual Git command or repository write."""
from pathlib import Path
from unittest.mock import patch
import datetime as dt,gzip,hashlib,importlib.util,json,tempfile
ROOT=Path(__file__).resolve().parent.parent
script=ROOT/'work/prepare_git_checkpoint.py';spec=importlib.util.spec_from_file_location('independent_git_public_projection',script);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
raw={'content':[{'type':'text','text':'Synthetic document (https://example.org/private)\n【turn000】 [wordlim: 200] Total lines: 5\nSynthetic private body.'}]}
cases=[]
def record(name,passed):cases.append({'case':name,'passed':bool(passed)})
for relative,payload in [
 ('audit/leaked.json',raw),('audit/review_history/leaked.json',raw),('reference/leaked.json',raw),
 ('audit_work/leaked.json',raw),('audit/news_provenance/leaked.json.gz',raw),
 ('reference/leaked.txt',raw),('audit/treasury_retained.csv',raw),
 ('reference/nested.txt',{'wrapper':{'response':raw}}),
 ('reference/double_encoded.json',{'saved_response_json':json.dumps({'content':[{'type':'text','text':'Synthetic https://example.org/private 【turn000】 body.'}]},ensure_ascii=True)}),
 ('audit_work/extra_metadata.json',{**raw,'request_metadata':{'kind':'synthetic'}}),
]:
 with tempfile.TemporaryDirectory(prefix='independent-git-projection-') as t:
  root=Path(t);f=root/relative;f.parent.mkdir(parents=True);body=json.dumps(payload).encode();f.write_bytes(gzip.compress(body,mtime=0) if relative.endswith('.gz') else body)
  with patch.object(m,'ROOT',root),patch.object(m,'git',side_effect=AssertionError('Git commands forbidden in independent candidates test')):
   try:m.candidates();blocked=False
   except ValueError:blocked=True
   record('raw_MCP_candidate_rejected_'+relative,blocked)
with tempfile.TemporaryDirectory(prefix='independent-git-projection-') as t:
 root=Path(t);f=root/'reference/raw_jsonl.txt';f.parent.mkdir(parents=True);f.write_text(json.dumps({'metadata':'synthetic'})+'\n'+json.dumps(raw)+'\n')
 with patch.object(m,'ROOT',root),patch.object(m,'git',side_effect=AssertionError('Git commands forbidden')):
  try:m.candidates();blocked=False
  except ValueError:blocked=True
  record('raw_MCP_JSONL_in_text_candidate_rejected',blocked)
with tempfile.TemporaryDirectory(prefix='independent-git-projection-') as t:
 root=Path(t);relative='audit/ordinary_metadata.json';f=root/relative;f.parent.mkdir(parents=True);f.write_text(json.dumps({'status':'synthetic metadata','url':'https://example.org/data'}))
 private=next(iter(sorted(m.PRIVATE_RESEARCH)));p=root/private;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(raw))
 with patch.object(m,'ROOT',root),patch.object(m,'git',side_effect=AssertionError('Git commands forbidden')):
  rows,omitted,missing=m.candidates();record('ordinary_metadata_remains_selected',any(row['source']==relative for row in rows));record('exact_registered_private_original_explicitly_omitted',not any(row['source']==private for row in rows) and any(row['path']==private and row.get('private_research') is True for row in omitted))
  for name in ['../outside.json','/outside.json','CLAUDE.md','claude.md']:
   try:m.safe(name);blocked=False
   except ValueError:blocked=True
   record('unsafe_or_forbidden_path_rejected_'+name,blocked)
  target=root/'audit/target.json';target.write_text('{}');link=root/'audit/link.json';link.symlink_to(target)
  try:m.safe('audit/link.json');blocked=False
  except ValueError:blocked=True
  record('candidate_symlink_rejected',blocked)
  try:m.go(None);blocked=False
  except ValueError:blocked=True
  record('copy_requires_exact_reviewed_plan_before_any_Git',blocked)
# Synthetic credential values exercise gzip and JSON escaping without reading
# configured runtime values, secret files, or printing value snippets.
values={'AWS_KEY':'synthetic-key','AWS_SECRET':'synthetic"secret','GH_TOKEN':'synthetic-token'}
scan=m.scan([('proof.json.gz',gzip.compress(b'synthetic-key',mtime=0)),('proof.json',b'synthetic\\"secret')],values)
record('synthetic_configured_value_hits_detected_in_gzip_and_JSON',not scan['passed'] and len(scan['matches'])==2 and scan['values_printed_or_recorded'] is False)
record('exact_month_target_counts',len(m.DATES)==20 and m.DEST.as_posix()=='corrections/2024-06' and '2024-06-19' in m.DATES and len(m.PRIVATE_RESEARCH)==33)
projection_receipt=ROOT/'audit/independent_public_research_projection_review.json';accepted_projection=json.loads(projection_receipt.read_bytes()) if projection_receipt.exists() else {}
result={'status':'accepted' if all(row['passed'] for row in cases) and accepted_projection.get('passed') is True else 'pending_or_failed','passed':all(row['passed'] for row in cases) and accepted_projection.get('passed') is True,'fatal_or_major_remaining':0 if all(row['passed'] for row in cases) and accepted_projection.get('passed') is True else 1,'scope':'git_checkpoint_public_projection_engineering_only','checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'script_path':'work/prepare_git_checkpoint.py','script_sha256':hashlib.sha256(script.read_bytes()).hexdigest(),'validator_sha256':hashlib.sha256((ROOT/'tools/build_source_inventory.py').read_bytes()).hexdigest(),'public_projection_review_sha256':hashlib.sha256(projection_receipt.read_bytes()).hexdigest() if projection_receipt.exists() else None,'cases':cases,'case_count':len(cases),'actual_git_commands_executed':False,'repository_mutated':False,'plan_or_copy_executed':False,'configured_credentials_read':False,'commit_or_push_performed':False,'limits':['Candidate/path/plan-before-copy/secret-scanner engineering controls only.','Actual postdelivery plan, copy/stage and checkpoint commit/push remain root operations; no deployment or report acceptance.']}
(ROOT/'audit/independent_git_checkpoint_tool_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':result['status'],'cases':len(cases),'failures':[row['case'] for row in cases if not row['passed']],'public_projection_independent_review_present':projection_receipt.exists()}))
