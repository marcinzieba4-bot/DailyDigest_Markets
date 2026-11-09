"""Public export self-QA with real immutable bytes and in-memory negatives.

No ZIP/report is built. A test-only explicit option skips the independent
approval requirement; production export and artifact audit keep it mandatory.
"""
from pathlib import Path
import copy
import datetime as dt
import hashlib
import importlib.util
import json

ROOT = Path(__file__).resolve().parent.parent


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


def sha(blob): return hashlib.sha256(blob).hexdigest()


def main():
    tool_paths = ['tools/build_source_inventory.py', 'tools/build_artifacts.py', 'audit_work/review_final_artifacts.py',
                  'audit_work/test_public_research_export.py']
    tool_before = {name: sha((ROOT / name).read_bytes()) for name in tool_paths}
    policy = module('public_export_test_policy', ROOT / 'tools/build_source_inventory.py')
    auditor = module('public_export_test_auditor', ROOT / 'audit_work/review_final_artifacts.py')
    local_result = policy.public_research_export(require_review=False)
    source = json.loads((ROOT / 'audit/independent_source_review.json').read_bytes())
    freeze = json.loads((ROOT / 'audit/source_freeze.json').read_bytes())
    names = {path.relative_to(ROOT).as_posix() for path in policy.collect_paths()}
    names.update(source['input_bindings'])
    names.update(['tools/build_source_inventory.py', 'audit/independent_source_review.json', 'audit/independent_market_review.json',
                  'audit/source_freeze.json', 'audit_work/review_sources.py', 'audit_work/news_policy_lock.json',
                  'newest_lambda_function.py', 'code_provenance.json', 'checks/code_discovery.json'])
    for field, prefix in [('tool_sha256', 'tools/'), ('contract_sha256', ''), ('reviewer_dependency_sha256', 'audit_work/')]:
        names.update(prefix + name for name in source[field])
    for row in source['dates']: names.update([f"audit/news_ready_{row['date']}.json", f"work/unreviewed_feeds/{row['date']}.json.gz"])
    names.update(['audit/news_coverage.json', freeze['candidate_manifest'], 'audit_work/news_semantic_review.json'])
    names.update(json.loads((ROOT / 'audit_work/news_policy_lock.json').read_bytes())['files'])
    amendment = json.loads((ROOT / auditor.SOURCE_PHASE_AMENDMENT).read_bytes()); names.add(auditor.SOURCE_PHASE_AMENDMENT)
    for original in amendment['original_proofs_preserved'].values(): names.update([original['path'], original['backup_path']])
    names.add(amendment['phases'][-1]['current_auxiliary_backup_path'])
    public_names = names - policy.PRIVATE_RESEARCH_PATHS
    before = {name: sha((ROOT / name).read_bytes()) for name in policy.PRIVATE_RESEARCH_PATHS}
    class Archive:
        def __init__(self, members, overrides=None): self.members = set(members); self.overrides = overrides or {}
        def namelist(self): return sorted(self.members)
        def read(self, name):
            if name not in self.members: raise KeyError(name)
            return self.overrides[name] if name in self.overrides else auditor.local_member(name).read_bytes()
    public = Archive(public_names); cases = []
    def passed(name): cases.append({'case': name, 'passed': True})
    def rejected(name, action):
        try: action()
        except (ValueError, KeyError, TypeError): passed(name)
        else: raise AssertionError('Public export negative accepted: ' + name)
    strict = auditor.current_source_dependencies(Archive(names), source, freeze)
    assert strict['source_input_bindings'] == 144 and strict['original_research_bytes_checked'] is True
    passed('local_all144_original_source_bindings_remain_strict')
    wrapped = auditor.PublicResearchArchive(public, require_review=False)
    projected = auditor.current_source_dependencies(wrapped, source, freeze)
    assert projected['source_input_bindings'] == 144 and projected['original_research_bytes_checked'] is False
    assert projected['physical_attempts'] == strict['physical_attempts'] and projected['received_attempt_bodies'] == strict['received_attempt_bodies']
    passed('public_projection_checks_all144_original_hash_bindings_and_retains_every_physical_body')
    for name, row in local_result['commitments'].items(): wrapped.commitment(name, row['sha256'], row['bytes'])
    assert len(wrapped.checked_commitments) == 33
    passed('all33_private_hash_and_size_commitments_explicitly_checked')
    rejected('no_automatic_local_waiver_for_missing_private_originals', lambda: auditor.current_source_dependencies(public, source, freeze))
    bound_private = next(name for name in sorted(policy.PRIVATE_RESEARCH_PATHS) if name in source['input_bindings'])
    rejected('local_original_body_mutation_rejected', lambda: auditor.current_source_dependencies(Archive(names, {bound_private: b'changed original'}), source, freeze))
    rejected('private_original_cannot_enter_public_ZIP', lambda: auditor.PublicResearchArchive(Archive(public_names | {bound_private}), require_review=False))
    leaked = 'audit_work/copied_raw_research.json'
    rejected('unregistered_raw_MCP_copy_cannot_enter_public_ZIP', lambda: auditor.PublicResearchArchive(
        Archive(public_names | {leaked}, {leaked: (ROOT / bound_private).read_bytes()}), require_review=False))
    raw_object = json.loads((ROOT / bound_private).read_bytes())
    for name, payload in [('audit/unregistered_raw.json', raw_object),
                          ('audit/review_history/unregistered_raw.json', raw_object),
                          ('reference/unregistered_raw.txt', raw_object),
                          ('reference/unregistered_raw.csv', raw_object),
                          ('reference/unregistered_raw.jsonl', raw_object),
                          ('audit_work/wrapped_raw.json', {'request_metadata': 'harmless', 'response': raw_object}),
                          ('audit_work/extra_metadata_raw.json', {**raw_object, 'request_metadata': 'harmless'}),
                          ('reference/encoded_raw.txt', {'payload': json.dumps(raw_object)})]:
        blob = json.dumps(payload).encode()
        rejected('candidate_content_scan_' + name, lambda name=name, blob=blob:
                 policy.assert_no_raw_web_candidates(lambda _: blob, [name]))
    minimal = {'content': [{'type': 'text', 'text': 'Synthetic https://example.org/private 【turn000】 body.'}]}
    encoded = json.dumps({'saved_response_json': json.dumps(minimal, ensure_ascii=True)}).encode()
    rejected('nested_escaped_marker_without_wordlim_rejected', lambda:
             policy.assert_no_raw_web_candidates(lambda _: encoded, ['reference/raw_double_encoded.json']))
    manifest = json.loads((ROOT / policy.PUBLIC_RESEARCH_MANIFEST).read_bytes())
    evidence = json.loads((ROOT / policy.PUBLIC_CLOCK_EVIDENCE).read_bytes())
    attestation = json.loads((ROOT / policy.PUBLIC_RESEARCH_ATTESTATION).read_bytes())
    def mutated(manifest_change=None, evidence_change=None, attestation_change=None):
        m, e, a = copy.deepcopy(manifest), copy.deepcopy(evidence), copy.deepcopy(attestation)
        if evidence_change: evidence_change(e)
        evidence_bytes = (json.dumps(e, ensure_ascii=False, indent=2) + '\n').encode()
        m['evidence_sha256'] = sha(evidence_bytes)
        if manifest_change: manifest_change(m)
        manifest_bytes = (json.dumps(m, ensure_ascii=False, indent=2) + '\n').encode()
        a.update(manifest_sha256=sha(manifest_bytes), evidence_sha256=sha(evidence_bytes))
        if attestation_change: attestation_change(a)
        overrides = {policy.PUBLIC_RESEARCH_MANIFEST: manifest_bytes, policy.PUBLIC_CLOCK_EVIDENCE: evidence_bytes,
                     policy.PUBLIC_RESEARCH_ATTESTATION: (json.dumps(a, ensure_ascii=False, indent=2) + '\n').encode()}
        return Archive(public_names, overrides)
    def projection_reject(name, **changes):
        rejected(name, lambda: auditor.PublicResearchArchive(mutated(**changes), require_review=False))
    projection_reject('financial_RSS_cannot_be_declared_private', manifest_change=lambda value: value['private_files'][0].update(path='cache/rss_raw/synthetic.xml.gz'))
    projection_reject('guard_cannot_be_declared_private', manifest_change=lambda value: value['private_files'][0].update(path='audit_work/june_release_schedule.json'))
    projection_reject('proof_cannot_be_declared_private', manifest_change=lambda value: value['private_files'][0].update(path='audit/independent_source_review.json'))
    projection_reject('bound_private_original_SHA_cannot_be_changed', manifest_change=lambda value: next(row for row in value['private_files'] if row['path'] == bound_private).update(sha256='0' * 64))
    projection_reject('omitted_private_commitment_rejected', manifest_change=lambda value: value['private_files'].pop())
    projection_reject('projection_source_acceptance_hash_changed', manifest_change=lambda value: value.update(source_acceptance_sha256='0' * 64))
    projection_reject('article_body_field_rejected', evidence_change=lambda value: value.update(article_body='Copied article body is prohibited.'))
    projection_reject('article_body_source_field_rejected', evidence_change=lambda value: value['sources'][0].update(body='Copied article body is prohibited.'))
    projection_reject('over25word_title_rejected', evidence_change=lambda value: value['sources'][0].update(title=' '.join(['word'] * 26)))
    projection_reject('article_body_quotation_rejected', evidence_change=lambda value: value['sources'][0].update(quote=' '.join(['quote'] * 26)))
    projection_reject('duplicate_source_URL_quote_budget_bypass_rejected', evidence_change=lambda value: value['sources'].append(copy.deepcopy(value['sources'][0])))
    projection_reject('clock_fact_mutation_rejected', evidence_change=lambda value: value['clock_rows'][0].update(release_utc='2000-01-01T00:00:00Z'))
    projection_reject('missing_clock_guard_fact_rejected', evidence_change=lambda value: value['clock_rows'].pop())
    projection_reject('false_original_research_byte_replay_claim_rejected', attestation_change=lambda value: value.update(public_original_research_byte_replay=True))
    projection_reject('boolean_body_word_count_rejected', attestation_change=lambda value: value.update(copied_article_body_words=False))
    projection_reject('self_attestation_cannot_claim_independent_acceptance', attestation_change=lambda value: value.update(independent_acceptance=True))
    projection_reject('stale_export_validator_attestation_rejected', attestation_change=lambda value: value.update(validator_sha256='0' * 64))
    row = local_result['commitments'][bound_private]
    rejected('replay_inventory_private_size_mismatch_rejected', lambda: wrapped.commitment(bound_private, row['sha256'], row['bytes'] + 1))
    rejected('nonresearch_missing_file_never_waived', lambda: wrapped.commitment('audit/news_physical_requests.jsonl', '0' * 64))
    # Production must require a real separate review; this test writes none.
    if policy.PUBLIC_RESEARCH_REVIEW not in public_names:
        rejected('production_requires_separate_engineer_review', lambda: auditor.PublicResearchArchive(public))
    assert before == {name: sha((ROOT / name).read_bytes()) for name in before}
    assert tool_before == {name: sha((ROOT / name).read_bytes()) for name in tool_paths}, 'Public export tools changed during self-QA'
    result = {'status': 'public_research_export_self_QA_passed', 'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'cases': cases, 'case_count': len(cases), 'private_originals_unchanged': True,
              'local_source_bindings_verified': strict['source_input_bindings'], 'public_source_hash_bindings_verified': projected['source_input_bindings'],
              'private_response_count': 33, 'clock_rows': 92, 'document_URLs': local_result['public_document_URLs'],
              'public_original_research_byte_replay': False, 'independent_acceptance': False,
              'full20_report_artifacts_accepted': False, 'archive_built': False,
              'tool_sha256': tool_before}
    (ROOT / 'checks/public_research_export_self_QA.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ['status', 'case_count', 'local_source_bindings_verified', 'private_response_count', 'independent_acceptance']}))


if __name__ == '__main__': main()
