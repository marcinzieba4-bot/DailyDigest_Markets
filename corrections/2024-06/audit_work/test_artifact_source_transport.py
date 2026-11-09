"""Read-only actual physical source/consumer integration; never audit reports.

This checks the independently accepted acquisition receipt and retained actual
transport bytes. It reads no report specification, author prose or market card,
does not produce a ZIP, and does not imply final20-report acceptance.
"""
from pathlib import Path
import datetime as dt
import hashlib
import importlib.util
import json

ROOT = Path(__file__).resolve().parent.parent


def module(name, path):
    info = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(info); info.loader.exec_module(result)
    return result


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    inventory = module('actual_transport_inventory', ROOT / 'tools/build_source_inventory.py')
    reviewer = module('actual_transport_reviewer', ROOT / 'audit_work/review_final_artifacts.py')
    paths = [inventory.PHYSICAL_REVIEW, inventory.CAPTURE_LIMITATION, 'audit/news_physical_requests.jsonl',
             'audit/news_query_plan.json', 'audit_work/physical_source_inventory.json']
    before = {name: sha(ROOT / name) for name in paths}
    proof = json.loads((ROOT / inventory.PHYSICAL_REVIEW).read_bytes())
    source_path = ROOT / 'audit/independent_source_review.json'
    source = json.loads(source_path.read_bytes()) if source_path.exists() else None
    physical = json.loads((ROOT / 'audit_work/physical_source_inventory.json').read_bytes())
    names = set(paths) | set(proof['input_bindings'])
    for row in physical['files']:
        names.update([row['parsed_cache_path'], row['raw_xml_path']])
    names.update(path.relative_to(ROOT).as_posix() for path in (ROOT / 'cache/rss_raw/attempts').rglob('*') if path.is_file())
    if (ROOT / inventory.ATTEMPT_STARTS).exists(): names.add(inventory.ATTEMPT_STARTS)
    if source is not None:
        names.update(source['input_bindings'])
        for field, prefix in [('tool_sha256', 'tools/'), ('contract_sha256', ''), ('reviewer_dependency_sha256', 'audit_work/')]:
            names.update(prefix + name for name in source[field])
        names.update(['audit/independent_source_review.json', 'audit/independent_market_review.json', 'audit/source_freeze.json',
                      'audit_work/review_sources.py', 'audit_work/news_policy_lock.json',
                      'newest_lambda_function.py', 'code_provenance.json', 'checks/code_discovery.json'])
        for row in source['dates']:
            names.update([f"audit/news_ready_{row['date']}.json", f"work/unreviewed_feeds/{row['date']}.json.gz"])
        freeze = json.loads((ROOT / 'audit/source_freeze.json').read_bytes())
        names.update(['audit/news_coverage.json', freeze['candidate_manifest'], 'audit_work/news_semantic_review.json'])
        names.update(json.loads((ROOT / 'audit_work/news_policy_lock.json').read_bytes())['files'])
        amendment_path = ROOT / reviewer.SOURCE_PHASE_AMENDMENT
        if amendment_path.exists():
            amendment = json.loads(amendment_path.read_bytes()); names.add(reviewer.SOURCE_PHASE_AMENDMENT)
            for original in amendment['original_proofs_preserved'].values(): names.update([original['path'], original['backup_path']])
            names.add(amendment['phases'][-1]['current_auxiliary_backup_path'])
            before[reviewer.SOURCE_PHASE_AMENDMENT] = sha(amendment_path)
        before.update({name: sha(ROOT / name) for name in names if name in source['input_bindings']
                       or name in {'audit/independent_source_review.json', 'audit/independent_market_review.json', 'audit/source_freeze.json'}})
    class Archive:
        def namelist(self): return sorted(names)
        def read(self, name):
            if name not in names: raise KeyError(name)
            return reviewer.local_member(name).read_bytes()
    local = inventory.require_physical_ledger(source if source is not None else proof, physical_review_only=source is None)
    archive = (reviewer.current_source_dependencies(Archive(), source, freeze) if source is not None
               else reviewer.physical_source_dependencies(Archive(), proof, physical_review_only=True))
    for name in ['physical_attempts', 'received_attempt_bodies', 'canonical_physical_requests',
                 'recorded_missing_response_bodies', 'modern_attempt_ids', 'all_physical_network_attempts_complete',
                 'unlogged_interrupted_attempts_maximum', 'unlogged_interrupted_attempts_actual_count']:
        assert local[name] == archive[name], name
    assert before == {name: sha(ROOT / name) for name in before}, 'Accepted source inputs changed during read-only replay'
    tool_paths = ['tools/build_source_inventory.py', 'tools/build_artifacts.py', 'audit_work/review_final_artifacts.py',
                  'audit_work/test_artifact_source_transport.py']
    result = {'status': 'actual_physical_consumer_integration_passed',
              'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'scope': 'Actual accepted source transport bytes and current artifact consumers only; no report inputs or full-month artifact audit.',
              'runtime_full20_report_artifacts_accepted': False, 'report_facts_or_specs_read': False,
              'archive_built': False, 'publication_performed': False,
              'current_source_acceptance_checked': source is not None,
              'physical_proof_bindings': before, 'filesystem_consumer': local, 'archive_consumer': archive,
              'tool_sha256': {name: sha(ROOT / name) for name in tool_paths},
              'limits': proof['forensic_limits']}
    (ROOT / 'checks/artifact_source_transport_integration.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'physical_attempts': local['physical_attempts'],
                      'received_attempt_bodies': local['received_attempt_bodies'],
                      'canonical_physical_requests': local['canonical_physical_requests'],
                      'recorded_missing_response_bodies': local['recorded_missing_response_bodies'],
                      'runtime_full20_report_artifacts_accepted': False}))


if __name__ == '__main__':
    main()
