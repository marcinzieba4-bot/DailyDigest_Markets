"""Require current chronology and independent selected-claim review receipts."""
import datetime as dt
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATES = [dt.date(2025, 5, n).isoformat() for n in range(1, 32)
         if dt.date(2025, 5, n).weekday() < 5]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text())


def require_expansion():
    """Bind final own-date feeds to the completed, independently checked repair."""
    expansion_path = ROOT/'audit/news_feed_expansion.json'
    qa_path = ROOT/'checks/source_expansion_independent_review.json'
    expansion = read_json(expansion_path)
    qa = read_json(qa_path)
    if (expansion.get('status') != 'expanded_verified'
            or expansion.get('complete_month') is not True
            or expansion.get('dates') != len(DATES)
            or any(expansion.get(key) != [] for key in
                   ['failed_daily_windows', 'failed_prefix_windows', 'failed_refinement_windows'])
            or expansion.get('unresolved_priority_metadata') != 0
            or expansion.get('missing_priority_mappings') != 0
            or any(expansion.get(key) is not True for key in
                   ['original_objects_unchanged', 'original_item_objects_unchanged',
                    'original_exclusions_not_resurrected'])):
        raise ValueError('Complete passing versioned news expansion required')
    if (qa.get('passed') is not True or qa.get('report_count') != len(DATES)
            or any(qa.get(key) is not True for key in
                   ['original_items_unchanged', 'all_original_raw_keys_absent_from_additions',
                    'original_exclusions_not_resurrected', 'new_unique_ids_above_initial_raw_max',
                    'daily_and_prefix_seed_ids_preserved', 'exclusive_cutoff_and_category_age_checks_passed',
                    'new_record_query_upper_not_after_own_cutoff', 'all_expected_topic_names_each_date'])
            or qa.get('unresolved_priority_occurrences') != 0):
        raise ValueError('Complete passing independent news expansion review required')
    if qa.get('expansion_receipt_sha256') != sha(expansion_path):
        raise ValueError('News expansion receipt changed after independent review')
    tools = {'tools/fetch_news.py', 'tools/ready_feeds.py', 'tools/expand_capped_news.py'}
    if (set(qa.get('tool_sha256', {})) != tools
            or any(qa['tool_sha256'][name] != sha(ROOT/name) for name in tools)):
        raise ValueError('News acquisition tool changed after independent expansion review')
    for field, directory in [('final_feed_sha256', 'feeds'), ('initial_feed_sha256', 'feeds_initial')]:
        if (sorted(expansion.get(field, {})) != DATES
                or qa.get(field) != expansion[field]):
            raise ValueError('Complete matching initial/final expansion feed inventories required')
        for date in DATES:
            if expansion[field][date] != sha(ROOT/directory/f'{date}.json.gz'):
                raise ValueError(date+' '+directory+' changed after expansion review')
    manifest_path = ROOT/'audit/news_expansion_snapshot_manifest.json'
    if qa.get('snapshot_manifest_sha256') != sha(manifest_path):
        raise ValueError('Expansion snapshot manifest changed after independent review')
    manifest = read_json(manifest_path)
    files = manifest.get('files', [])
    names = [row.get('path') for row in files]
    if (manifest.get('file_count') != 130 or len(files) != 130
            or len(set(names)) != 130 or qa.get('snapshot_manifest_files_verified') != 130
            or 'work/news_expansion/check_tools.py' not in names):
        raise ValueError('Complete 130-file expansion snapshot inventory required')
    for row in files:
        path = (ROOT/row['path']).resolve()
        if (not path.is_relative_to(ROOT) or not path.is_file()
                or path.stat().st_size != row.get('bytes') or sha(path) != row.get('sha256')):
            raise ValueError('Archived expansion input changed: '+row['path'])
    ready_path = ROOT/'audit/news_ready_audit.json'
    checks_path = ROOT/'audit/news_expansion_tool_checks.json'
    stability_path = ROOT/'audit/news_expansion_receipt_stability.json'
    for path, field in [(ready_path, 'news_ready_audit_sha256'),
                        (checks_path, 'news_expansion_tool_checks_sha256'),
                        (stability_path, 'receipt_stability_sha256')]:
        if qa.get(field) != sha(path):
            raise ValueError('Expansion supporting receipt changed: '+path.name)
    ready = read_json(ready_path)
    checks = read_json(checks_path)
    stability = read_json(stability_path)
    if (ready.get('status') != 'passed' or ready.get('report_dates') != len(DATES)
            or ready.get('missing_dates') != []
            or any(ready.get(key) != 0 for key in ['failed_query_windows', 'failed_prefix_windows',
                                                 'failed_refinement_windows', 'unresolved_priority_records'])
            or ready.get('ready_own_date_records') != expansion.get('final_ready_records')
            or qa.get('final_records') != expansion.get('final_ready_records')
            or checks.get('passed') is not True or checks.get('tool_sha256') != qa['tool_sha256']
            or checks.get('check_script_sha256') != sha(ROOT/'work/news_expansion/check_tools.py')
            or stability.get('passed') is not True or stability.get('checked_files') != 24
            or qa.get('receipt_stability_files_verified') != 24):
        raise ValueError('Complete matching readiness and expansion tool checks required')
    return {'news_expansion_sha256': sha(expansion_path),
            'news_expansion_independent_review_sha256': sha(qa_path)}


def require_manifest_review(proof):
    """Finalization/publication must use the review proof stored by the build."""
    manifest_path = ROOT/'checks/artifact_manifest.json'
    if (manifest_path.exists()
            and read_json(manifest_path).get('review_receipts') != proof):
        raise ValueError('Artifact manifest does not bind the current review receipts')


def require_review(*, check_manifest=True):
    expansion_proof = require_expansion()
    chronology = json.loads((ROOT/'audit/cited_source_dates.json').read_text())
    if (chronology.get('date_screen_passed') is not True
            or sorted(chronology.get('spec_sha256', {})) != DATES):
        raise ValueError('Complete passing cited-source date screen required')
    if (chronology.get('timing_exceptions_sha256') != sha(ROOT/'audit/canonical_source_exceptions.json')
            or chronology.get('auditor_sha256') != sha(ROOT/'tools/audit_source_dates.py')):
        raise ValueError('Timing exceptions or source auditor changed after screening')
    exceptions = json.loads((ROOT/'audit/canonical_source_exceptions.json').read_text())['exceptions']
    approved = {(x['date'], x['id']): x for x in exceptions}
    for used in chronology.get('timing_exceptions_used', []):
        row = approved.get((used['date'], used['id']))
        proof = (ROOT/row.get('timing_proof_file', '')).resolve() if row else None
        if (not proof or not proof.is_relative_to(ROOT) or not proof.is_file()
                or sha(proof) != row.get('timing_proof_sha256')):
            raise ValueError('Timing proof changed after source screening: '+str(used))
    independent = json.loads((ROOT/'checks/independent_selected_review.json').read_text())
    attributions = json.loads((ROOT/'checks/source_attribution_diagnostic.json').read_text())
    if (attributions.get('reports') != len(DATES) or attributions.get('flags') != []
            or sorted(attributions.get('spec_sha256', {})) != DATES
            or attributions.get('auditor_sha256') != sha(ROOT/'tools/audit_attributions.py')):
        raise ValueError('Complete current named-outlet attribution diagnostic required')
    if sorted(independent.get('reports', {})) != DATES:
        raise ValueError(f'Independent selected-claim review required for all {len(DATES)} dates')
    for date in DATES:
        spec_hash = sha(ROOT/'specs'/f'{date}.json')
        feed_hash = sha(ROOT/'feeds'/f'{date}.json.gz')
        card_hash = sha(ROOT/'cards'/f'{date}.json')
        row = independent['reports'][date]
        if (chronology['spec_sha256'].get(date) != spec_hash
                or attributions['spec_sha256'].get(date) != spec_hash
                or attributions.get('feed_sha256', {}).get(date) != feed_hash
                or chronology.get('feed_sha256', {}).get(date) != feed_hash
                or row.get('spec_sha256') != spec_hash
                or row.get('feed_sha256') != feed_hash
                or row.get('card_sha256') != card_hash):
            raise ValueError(date+' changed after source or independent review')
        if (row.get('selected_review_passed') is not True
                or not row.get('reviewer') or not row.get('notes')):
            raise ValueError(date+' incomplete independent review')
    proof = {'dates': DATES, 'chronology_sha256': sha(ROOT/'audit/cited_source_dates.json'),
             'selected_review_sha256': sha(ROOT/'checks/independent_selected_review.json'),
             **expansion_proof}
    if check_manifest:
        require_manifest_review(proof)
    return proof


if __name__ == '__main__':
    print(json.dumps(require_review(), indent=2))
