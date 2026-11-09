"""Read-only actual metadata amendment plus isolated negative overrides.

No physical/report data is changed and no full-month artifact acceptance occurs.
"""
from pathlib import Path
import copy
import datetime as dt
import hashlib
import importlib.util
import json

ROOT = Path(__file__).resolve().parent.parent


def sha(blob): return hashlib.sha256(blob).hexdigest()


def main():
    spec = importlib.util.spec_from_file_location('coverage_phase_consumer_test', ROOT / 'audit_work/review_final_artifacts.py')
    consumer = importlib.util.module_from_spec(spec); spec.loader.exec_module(consumer)
    amendment = json.loads((ROOT / consumer.SOURCE_PHASE_AMENDMENT).read_bytes())
    source = json.loads((ROOT / 'audit/independent_source_review.json').read_bytes())
    freeze = json.loads((ROOT / 'audit/source_freeze.json').read_bytes())
    policy = json.loads((ROOT / 'audit_work/news_policy_lock.json').read_bytes())
    names = set(source['input_bindings']) | {consumer.SOURCE_PHASE_AMENDMENT}
    for original in amendment['original_proofs_preserved'].values(): names.update([original['path'], original['backup_path']])
    names.add(amendment['phases'][-1]['current_auxiliary_backup_path'])
    before = {name: sha(consumer.local_member(name).read_bytes()) for name in names}
    class Archive:
        def __init__(self, overrides=None): self.overrides = overrides or {}
        def namelist(self): return sorted(names)
        def read(self, name):
            if name not in names: raise KeyError(name)
            return self.overrides[name] if name in self.overrides else consumer.local_member(name).read_bytes()
    positive = consumer.coverage_phase_binding(Archive(), source, freeze, policy)
    assert positive['amendment_sha256'] == consumer.SOURCE_PHASE_AMENDMENT_SHA256
    cases = [{'case': 'actual_independently_bound_three_phase_amendment', 'passed': True}]
    def rejected(name, archive, **kwargs):
        try: consumer.coverage_phase_binding(archive, source, freeze, policy, **kwargs)
        except (ValueError, KeyError, TypeError): cases.append({'case': name, 'passed': True})
        else: raise AssertionError('Coverage phase negative accepted: ' + name)
    # A changed digest always rejects at the production boundary. For schema
    # controls only, supply that in-memory override's digest to reach the named
    # invariant; the real amendment and its pinned default digest stay intact.
    for name, change in [
        ('wrong_amendment_status', lambda value: value.update(status='pending')),
        ('amendment_not_passed', lambda value: value.update(passed=False)),
        ('wrong_auxiliary_path', lambda value: value.update(affected_auxiliary_path='audit/news_query_plan.json')),
        ('wrong_historical_map_scope', lambda value: value['consumer_patch_contract']['allowed_historical_maps'].append('unrelated.input_bindings')),
        ('wrong_policy_phase_map', lambda value: value['phases'][1].update(map='input_bindings')),
        ('wrong_staged_phase_hash', lambda value: value['phases'][1].update(independent_stage_expected_sha256='0' * 64)),
        ('wrong_current_freeze_bind', lambda value: value['phases'][2].update(source_freeze_expected_sha256='0' * 64)),
        ('invented_old_coverage_bytes', lambda value: value['phases'][0].update(original_auxiliary_bytes_retained=True)),
        ('wrong_original_source_hash', lambda value: value['original_proofs_preserved']['source'].update(sha256='0' * 64)),
    ]:
        changed = copy.deepcopy(amendment); change(changed); blob = json.dumps(changed).encode()
        rejected(name, Archive({consumer.SOURCE_PHASE_AMENDMENT: blob}), expected_amendment_sha256=sha(blob))
    rejected('pinned_amendment_digest_changed', Archive({consumer.SOURCE_PHASE_AMENDMENT: b'{}'}))
    rejected('other_policy_dependency_changed', Archive({'tools/topics.py': b'synthetic corruption'}))
    rejected('other_physical_dependency_changed', Archive({'audit/news_query_plan.json': b'synthetic corruption'}))
    rejected('current_coverage_changed', Archive({'audit/news_coverage.json': b'synthetic corruption'}))
    backup = amendment['original_proofs_preserved']['policy_lock']['backup_path']
    rejected('original_proof_backup_changed', Archive({backup: b'synthetic corruption'}))
    rejected('original_passed_staged_receipt_changed', Archive({'audit_work/independent_staged_source_review.json': b'{}'}))
    rejected('passed_guard_evidence_changed', Archive({'audit/independent_release_guard_review.json': b'{}'}))
    rejected('completed_semantic_evidence_changed', Archive({'audit_work/news_semantic_review.json': b'{}'}))
    assert before == {name: sha(consumer.local_member(name).read_bytes()) for name in names}
    result = {'status': 'coverage_phase_binding_checks_passed', 'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'cases': cases, 'case_count': len(cases), 'amendment_sha256': positive['amendment_sha256'],
              'source_and_original_proofs_unchanged': True, 'runtime_full20_report_artifacts_accepted': False,
              'scope': 'Actual metadata proof binding and in-memory negative overrides only; no source/report/card/guard mutation or publication.',
              'tool_sha256': {name: sha((ROOT / name).read_bytes()) for name in
                             ['audit_work/review_final_artifacts.py', 'audit_work/test_coverage_phase_binding.py']}}
    (ROOT / 'checks/artifact_coverage_phase_regressions.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'case_count': len(cases)}))


if __name__ == '__main__': main()
