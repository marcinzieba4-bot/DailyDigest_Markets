"""Verify real source-proof acceptance and in-memory corruption rejection.

No fabricated receipt is written or substituted on disk. This runs after source
acquisition freezes and before narrative artifacts are built.
"""
from pathlib import Path
import datetime as dt
import copy
import hashlib
import importlib.util
import json
from unittest.mock import patch
ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('april_source_gate_check', ROOT/'tools/review_gate.py')
gate = importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    proof = gate.require_sources()
    qa_path = ROOT/'checks/source_acquisition_independent_review.json'
    inventory_path = ROOT/'audit/news_replay_inventory.json'
    qa = gate.read_json(qa_path)
    inventory = gate.read_json(inventory_path)
    paths = [ROOT/row['path'] for row in inventory['files']] + [qa_path, inventory_path,
        ROOT/'audit/news_ready_audit.json', ROOT/'audit/news_coverage.json', ROOT/'audit/news_query_plan.json']
    before = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    actual_sha = gate.sha
    cases = {
        'changed_final_feed': ROOT/'feeds/2025-04-01.json.gz',
        'changed_acquisition_tool': ROOT/'tools/fetch_news.py',
        'changed_raw_query_response': next(ROOT/r['path'] for r in inventory['files'] if r['path'].startswith('cache/news/')),
        'changed_ready_receipt': ROOT/'audit/news_ready_audit.json',
    }
    passed = []
    for name, target in cases.items():
        with patch.object(gate, 'sha', lambda p: '0'*64 if p.resolve() == target.resolve() else actual_sha(p)):
            try: gate.require_sources()
            except ValueError: pass
            else: raise AssertionError('Accepted '+name)
        passed.append(name)
    actual_read = gate.read_json
    invalid = copy.deepcopy(qa); invalid['request_catalog_complete'] = False
    with patch.object(gate, 'read_json', lambda p: invalid if p == qa_path else actual_read(p)):
        try: gate.require_sources()
        except ValueError: pass
        else: raise AssertionError('Accepted false independent coverage proof')
    passed.append('false_independent_coverage_proof')
    manifest_path = ROOT/'checks/artifact_manifest.json'
    with patch.object(gate, 'read_json', lambda p: {'review_receipts': {}} if p == manifest_path else actual_read(p)), patch.object(Path, 'exists', lambda p: True if p == manifest_path else p.is_file()):
        try: gate.require_manifest_review(proof)
        except ValueError: pass
        else: raise AssertionError('Accepted stale artifact source proof')
    passed.append('stale_artifact_source_proof')
    assert before == {str(p.relative_to(ROOT)): sha(p) for p in paths}
    result = {'passed': True, 'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'source_gate_sha256': sha(ROOT/'tools/review_gate.py'),
              'checker_sha256': sha(Path(__file__)), 'real_inputs_unchanged': True,
              'input_files_checked': len(paths), 'rejected': passed, 'source_proof': proof}
    (ROOT/'checks/tooling_source_gate.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='source_proof'}))

if __name__ == '__main__': main()
