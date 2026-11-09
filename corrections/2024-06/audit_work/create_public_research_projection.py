"""Prepare compact public clock metadata; never change private research bytes."""
from pathlib import Path
import hashlib
import importlib.util
import json

ROOT = Path(__file__).resolve().parent.parent


def main():
    spec = importlib.util.spec_from_file_location('public_research_export_builder', ROOT / 'tools/build_source_inventory.py')
    policy = importlib.util.module_from_spec(spec); spec.loader.exec_module(policy)
    policy.scan_private_research()
    source_path = ROOT / 'audit/independent_source_review.json'; source = json.loads(source_path.read_bytes())
    schedule_path = ROOT / 'audit_work/june_release_schedule.json'; schedule = json.loads(schedule_path.read_bytes())
    before = {name: policy.sha(policy.safe_path(name)) for name in policy.PRIVATE_RESEARCH_PATHS}
    evidence = {'schema': 'june-public-clock-evidence-v1', 'clock_policy_sha256': policy.sha(schedule_path),
                'clock_rows': policy.public_clock_rows(schedule), 'sources': policy.public_document_headers(),
                'quote_word_limit_per_url': 25,
                'scope': 'Factual clock metadata from unchanged guards and document headings/URLs only; no article-body text or quotations.'}
    policy.write(ROOT / policy.PUBLIC_CLOCK_EVIDENCE, evidence)
    rows = [{'path': name, 'sha256': before[name], 'bytes': policy.safe_path(name).stat().st_size,
             'frozen_source_binding_sha256': source['input_bindings'].get(name)} for name in sorted(before)]
    manifest = {'schema': 'june-public-research-projection-v1',
                'status': 'public_projection_with_private_original_hash_commitments',
                'source_acceptance_sha256': policy.sha(source_path), 'clock_policy_path': schedule_path.relative_to(ROOT).as_posix(),
                'clock_policy_sha256': policy.sha(schedule_path), 'evidence_path': policy.PUBLIC_CLOCK_EVIDENCE,
                'evidence_sha256': policy.sha(ROOT / policy.PUBLIC_CLOCK_EVIDENCE),
                'private_files': rows, 'private_file_count': len(rows),
                'export_scope': 'Compact clock evidence; original full research responses are private and are not publicly byte-replayed.'}
    policy.write(ROOT / policy.PUBLIC_RESEARCH_MANIFEST, manifest)
    attestation = {'schema': 'june-public-research-export-attestation-v1', 'status': 'hash_and_scope_attestation',
                   'manifest_sha256': policy.sha(ROOT / policy.PUBLIC_RESEARCH_MANIFEST),
                   'evidence_sha256': policy.sha(ROOT / policy.PUBLIC_CLOCK_EVIDENCE),
                   'validator_sha256': policy.sha(ROOT / 'tools/build_source_inventory.py'),
                   'source_acceptance_sha256': manifest['source_acceptance_sha256'],
                   'private_originals_retained_locally': True, 'public_original_research_byte_replay': False,
                   'financial_RSS_market_feed_guard_or_proof_omitted': False, 'copied_article_body_words': 0,
                   'independent_acceptance': False}
    policy.write(ROOT / policy.PUBLIC_RESEARCH_ATTESTATION, attestation)
    result = policy.public_research_export(require_review=False)
    assert before == {name: policy.sha(policy.safe_path(name)) for name in before}
    print(json.dumps({key: value for key, value in result.items() if key != 'commitments'}))


if __name__ == '__main__': main()
