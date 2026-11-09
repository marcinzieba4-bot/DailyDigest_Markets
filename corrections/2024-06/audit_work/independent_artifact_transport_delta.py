"""Independent transport consumer delta review: schemas and retained bytes only.
No report specification/prose is opened; no archive is built or published.
"""
from pathlib import Path
from unittest.mock import patch
import copy,datetime as dt,hashlib,importlib.util,json,subprocess,sys
ROOT=Path(__file__).resolve().parent.parent
FILES=['tools/build_source_inventory.py','tools/build_artifacts.py','audit_work/review_final_artifacts.py']
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def module(relative):
 path=ROOT/relative;spec=importlib.util.spec_from_file_location('independent_transport_'+path.stem,path);obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj
policy=module(FILES[0]);reviewer=module(FILES[2]);mods={name:module('tools/'+name+'.py') for name in ['render','build_artifacts','build_retail_page','build_source_inventory']}
captured={};original=reviewer.replay_archive
def capture(archive):
 if not captured:captured.update(copy.deepcopy(archive.values))
 return original(archive)
with patch.object(reviewer,'replay_archive',side_effect=capture):assert len(reviewer.negative_fixtures(mods))==55
ledger=[json.loads(line) for line in captured['audit/news_physical_requests.jsonl'].decode().splitlines()]
proof=json.loads(captured[policy.PHYSICAL_REVIEW]);limitation=json.loads(captured[policy.CAPTURE_LIMITATION]);cases=[]
def reject(name,change):
 candidate=copy.deepcopy(proof);change(candidate)
 try:policy.transport_records(ledger,candidate,limitation,None);ok=False
 except (ValueError,TypeError,KeyError):ok=True
 cases.append({'case':name,'passed':ok})
policy.transport_records(ledger,proof,limitation,None)
cases.append({'case':'independently_captured_current_transport_positive','passed':True})
for name,key,value in [
 ('boolean_interrupted_bound','unlogged_interrupted_attempts_maximum',True),
 ('negative_interrupted_bound','unlogged_interrupted_attempts_maximum',-1),
 ('expanded_interrupted_bound','unlogged_interrupted_attempts_maximum',17),
 ('invented_exact_interrupted_count','unlogged_interrupted_attempts_actual_count',0),
 ('false_completeness_claim','all_physical_network_attempts_complete',True),
 ('boolean_attempt_count','physical_attempts',True),
 ('boolean_body_count','received_attempt_bodies',True),
 ('fabricated_positive_authoring_acceptance','authoring_acceptance',True),
 ('unresolved_physical_errors','errors',['Synthetic unresolved issue']),
 ('incomplete_physical_date_scope','dates',proof['dates'][:-1]),
 ('missing_historical_collision_disclosure','legacy_signature_attempt_number_collisions',None),
]:reject(name,lambda candidate,key=key,value=value:candidate.__setitem__(key,value))
# Run the exact owner suites on current bytes, including actual read-only producer
# integration. A failing integration stays visible and blocks this delta receipt.
runs=[]
for relative in ['audit_work/test_artifact_transport_regressions.py','audit_work/test_artifact_source_transport.py']:
 run=subprocess.run([sys.executable,str(ROOT/relative)],text=True,capture_output=True)
 runs.append({'helper':relative,'helper_sha256':sha(ROOT/relative),'returncode':run.returncode,'stdout':run.stdout.strip(),'stderr':run.stderr.strip()})
actual_paths=['audit/independent_physical_source_review.json','audit_work/acquisition_capture_limitation.json','audit/news_physical_requests.jsonl','audit/news_query_plan.json','audit_work/physical_source_inventory.json','audit/independent_source_review.json','audit/independent_market_review.json','audit/source_freeze.json','audit/news_coverage.json','audit_work/news_policy_lock.json']
physical=json.loads((ROOT/policy.PHYSICAL_REVIEW).read_bytes());source=json.loads((ROOT/'audit/independent_source_review.json').read_bytes());freeze=json.loads((ROOT/'audit/source_freeze.json').read_bytes());lock=json.loads((ROOT/'audit_work/news_policy_lock.json').read_bytes());coverage='audit/news_coverage.json'
passed=all(row['passed'] for row in cases) and all(row['returncode']==0 for row in runs)
result={'status':'independent_transport_delta_passed' if passed else 'blocked_actual_transport_integration','checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'passed':passed,'tool_sha256':{name:sha(ROOT/name) for name in FILES},'reviewer_sha256':sha(Path(__file__)),'independent_cases':cases,'owner_runs':runs,'actual_immutable_boundary_sha256':{name:sha(ROOT/name) for name in actual_paths},'coverage_phase_bindings':{'original_physical_proof':physical['input_bindings'].get(coverage),'original_policy_lock':lock['files'].get(coverage),'current_final_source':source['input_bindings'].get(coverage),'current_source_freeze':freeze.get('coverage_sha256'),'retained_current_bytes':sha(ROOT/coverage)},'runtime_full20_report_artifacts_accepted':False,'facts_or_specs_read':False,'archive_built':False,'publication_performed':False,'limits':['Transport schema/actual retained-byte integration only; no report acceptance.','Original historical coverage phase bytes are not reconstructed or asserted retained.','The exact independent physical proof and source boundary hashes above remain authoritative.']}
(ROOT/'checks/independent_artifact_transport_delta_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':result['status'],'independent_cases':len(cases),'independent_passed':sum(row['passed'] for row in cases),'owner_suite_exitcodes':[row['returncode'] for row in runs]}))
