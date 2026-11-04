"""Build a packaging-only, offline inventory of the already frozen September sources.

This does not acquire news, execute replay scripts, regenerate feeds or write receipts
belonging to acquisition/review. The only outputs are exact replay-tool snapshots,
the snapshot mapping, this packaging inventory and its packaging build receipt.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
INVENTORY = 'audit/news_replay_inventory.json'
MAPPING = 'checks/replay_tool_snapshots.json'
BUILD_RECEIPT = 'checks/news_replay_inventory_build.json'
STAGE = ROOT / 'work/source_inventory_packaging_stage'
EXTERNAL_REPLAY = {
    '/workspace/work/sep2024/audit_work/review_sources.py': 'tools/replay_snapshots/review_sources.py',
    '/workspace/work/sep2024/audit_work/review_market.py': 'tools/replay_snapshots/review_market.py',
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe(relative: str, exists: bool = True) -> Path:
    require(isinstance(relative, str) and relative, 'Empty inventory path')
    pure = PurePosixPath(relative)
    require(not pure.is_absolute() and '..' not in pure.parts and str(pure) == relative,
            f'Unsafe or noncanonical relative path: {relative!r}')
    path = ROOT / relative
    require(path.resolve().is_relative_to(ROOT), f'Path escapes September root: {relative}')
    require(not any(p.is_symlink() for p in [path, *path.parents] if p != ROOT.parent),
            f'Symlink is not an inventory input: {relative}')
    if exists:
        require(path.is_file(), f'Missing referenced file: {relative}')
    return path


def load(relative):
    return json.loads(safe(relative).read_bytes())


def check_existing():
    inv = load(INVENTORY)
    rows = inv['files']
    require(rows == sorted(rows, key=lambda r: r['path']), 'Inventory is not sorted')
    require(len({r['path'] for r in rows}) == len(rows), 'Duplicate inventory paths')
    for row in rows:
        data = safe(row['path']).read_bytes()
        require(digest(data) == row['sha256'] and len(data) == row['bytes'],
                f'Inventory file changed: {row["path"]}')
    require(digest(encoded(rows)) == inv['file_list_sha256'], 'File-list hash mismatch')
    print(json.dumps({'status': 'verified_existing_inventory', 'inventory_sha256': digest(safe(INVENTORY).read_bytes()),
                      'files': len(rows), 'bytes': sum(r['bytes'] for r in rows)}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Validate inventory only; write no files')
    args = parser.parse_args()
    if args.check:
        check_existing()
        return

    rows = {}
    roles = {}
    pending = {}
    bindings = []
    preserved_replay_inputs = []
    not_applicable = []

    def add(relative, expected=None, role='metadata', data=None):
        require(relative not in {INVENTORY, BUILD_RECEIPT}, 'Self-referential inventory/receipt')
        if data is None:
            data = safe(relative).read_bytes()
        else:
            safe(relative, exists=False)
        actual = digest(data)
        if expected is not None:
            require(isinstance(expected, str) and len(expected) == 64 and actual == expected,
                    f'Declared hash mismatch: {relative}')
        row = {'path': relative, 'sha256': actual, 'bytes': len(data)}
        require(relative not in rows or rows[relative] == row, f'Conflicting binding: {relative}')
        rows[relative] = row
        roles.setdefault(role, set()).add(relative)
        return data

    def stage(relative, data, role):
        add(relative, role=role, data=data)
        pending[relative] = data

    # Bind metadata before reading any of its references.
    plan = json.loads(add('audit/news_query_plan.json', role='query_plan'))
    coverage = json.loads(add('audit/news_coverage.json', role='coverage'))
    freeze = json.loads(add('audit/source_freeze.json', role='freeze'))
    source = json.loads(add('audit/independent_source_review.json', role='acceptance_receipt'))
    market = json.loads(add('audit/independent_market_review.json', role='acceptance_receipt'))
    require(freeze['status'] == 'all_21_ready' and source['passed'] and market['passed'],
            'Source/market acceptance must already exist')
    plan_sha = rows['audit/news_query_plan.json']['sha256']
    freeze_sha = rows['audit/source_freeze.json']['sha256']
    coverage_sha = rows['audit/news_coverage.json']['sha256']
    require(coverage['query_plan_sha256'] == plan_sha == freeze['query_plan_sha256'] == source['query_plan_sha256'],
            'Plan anchor mismatch')
    require(freeze['coverage_sha256'] == coverage_sha, 'Freeze coverage anchor mismatch')
    for receipt in (source, market):
        require(receipt['source_freeze_sha256'] == freeze_sha, 'Acceptance freeze anchor mismatch')

    # Additional independently accepted proofs and offline replay inputs must
    # survive packaging with their exact receipt bindings. They already have
    # safe archive-relative locations; do not execute or rewrite any of them.
    for field in ('physical_source_inventory', 'stage_review', 'headline_exclusions',
                  'prefreeze_candidate_manifest', 'selected_boundary_checks'):
        add(source[field + '_path'], source[field + '_sha256'], 'independent_acceptance_reference')
    author_exclusions = source.get('author_exclusion_sha256', {})
    require(set(author_exclusions) == {f'audit/author_exclusions/{date}.json' for date in plan['dates']},
            'Own-date author-exclusion receipt set mismatch')
    for relative, expected in sorted(author_exclusions.items()):
        add(relative, expected, 'author_exclusion')
    for receipt_name, receipt in [('audit/independent_source_review.json', source),
                                  ('audit/independent_market_review.json', market)]:
        declared_inputs = receipt.get('replay_tool_sha256', {})
        require(bool(declared_inputs), f'Missing independent offline replay inputs: {receipt_name}')
        for relative, expected in sorted(declared_inputs.items()):
            require(relative.startswith('tools/replay_snapshots/'), f'Unexpected independent replay location: {relative}')
            data = add(relative, expected, 'independent_replay_input')
            preserved_replay_inputs.append({'path': relative, 'sha256': expected, 'bytes': len(data),
                                           'declared_by': receipt_name + ':replay_tool_sha256',
                                           'status': 'verified_existing_archive_relative_input'})

    requests = plan['requests']
    require(len(requests) > 0 and len(requests) == coverage['unique_query_urls'], 'Physical request count differs from accepted coverage')
    require(len({r['signature'] for r in requests}) == len(requests), 'Duplicate physical signatures')
    raw_uncompressed_bytes = 0
    for request in requests:
        parsed_bytes = add(request['cache_path'], request['cache_sha256'], 'parsed_response')
        raw_bytes = add(request['raw_response_path'], request['raw_response_compressed_sha256'], 'raw_response')
        raw_xml = gzip.decompress(raw_bytes)
        require(digest(raw_xml) == request['raw_sha256'], f'Uncompressed RSS mismatch: {request["signature"]}')
        raw_uncompressed_bytes += len(raw_xml)
        parsed = json.loads(gzip.decompress(parsed_bytes))
        for key in ('signature', 'request_url', 'raw_response_path', 'raw_response_compressed_sha256',
                    'raw_sha256', 'parser_schema', 'lower_date', 'upper_date_exclusive'):
            require(parsed[key] == request[key], f'Parsed cache/plan {key} mismatch: {request["signature"]}')
    require(len(roles['parsed_response']) == len(requests) == len(roles['raw_response']),
            'Physical cache paths must be unique')

    manifest_path = freeze['candidate_manifest']
    manifest = json.loads(add(manifest_path, freeze['candidate_manifest_sha256'], 'candidate_manifest'))
    require(manifest['query_plan_sha256'] == plan_sha, 'Candidate plan anchor mismatch')
    require(manifest['status'] == 'all_21_compared_before_destination_write', 'Incomplete candidate staging')
    frozen_dates = {r['date']: r for r in freeze['dates']}
    coverage_dates = {r['date']: r for r in coverage['dates']}
    source_dates = {r['date']: r for r in source['dates']}
    candidates = {r['date']: r for r in manifest['dates']}
    dates = sorted(frozen_dates)
    require(len(dates) == 21 and set(dates) == set(plan['dates']) == set(coverage_dates) == set(source_dates) == set(candidates),
            'September own-date set mismatch')
    for date in dates:
        frozen = frozen_dates[date]
        require(frozen == coverage_dates[date], f'Coverage/freeze row mismatch: {date}')
        original_sha = frozen['feed_sha256']
        ready_sha = frozen['screened_sha256']
        provenance_sha = frozen['provenance_sha256']
        add(f'work/unreviewed_feeds/{date}.json.gz', original_sha, 'unreviewed_feed')
        add(f'feeds/{date}.json.gz', ready_sha, 'ready_feed')
        add(frozen['provenance_path'], provenance_sha, 'provenance')
        ready_path = f'audit/news_ready_{date}.json'
        ready = json.loads(add(ready_path, source_dates[date]['ready_receipt_sha256'], 'ready_receipt'))
        frozen_receipt = json.loads(add(f'audit/news_frozen_{date}.json', role='frozen_receipt'))
        require(ready['ready_sha256'] == frozen_receipt['feed_sha256'] == source_dates[date]['feed_sha256'] == ready_sha,
                f'Ready receipt hash mismatch: {date}')
        require(ready['unreviewed_sha256'] == source_dates[date]['raw_sha256'] == original_sha,
                f'Unreviewed receipt hash mismatch: {date}')
        require(source_dates[date]['provenance_sha256'] == provenance_sha, f'Provenance receipt mismatch: {date}')
        require(frozen_receipt['query_plan_sha256'] == plan_sha and frozen_receipt['candidate_manifest'] == manifest_path,
                f'Frozen receipt anchor mismatch: {date}')
        candidate = candidates[date]
        require(candidate['all_stage_bytes_verified'], f'Candidate was not verified: {date}')
        for kind, field, expected in (
            ('unreviewed_feeds', 'raw_candidate_sha256', original_sha),
            ('news_provenance', 'provenance_candidate_sha256', provenance_sha),
            ('feeds', 'ready_candidate_sha256', ready_sha),
        ):
            require(candidate[field] == expected, f'Candidate/destination hash mismatch: {date}/{kind}')
            add(f'work/source_candidates/{kind}/{date}.json.gz', expected, 'staged_candidate')
        require(source['card_sha256'][date] == market['card_sha256'][date], f'Acceptance card mismatch: {date}')
        add(f'cards/{date}.json', source['card_sha256'][date], 'accepted_card')

    # Preserve only tools actually declared by existing execution/acceptance metadata.
    for relative, expected in coverage['acquisition_tool_sha256'].items():
        add(relative, expected, 'acquisition_tool')
    for filename, expected in source['tool_sha256'].items():
        add('tools/' + filename, expected, 'acquisition_tool')
    for receipt in (source, market):
        for relative, expected in receipt['contract_sha256'].items():
            add(relative, expected, 'accepted_contract')

    for declared_field in ('helper_tool_sha256', 'transport_tool_sha256'):
        for relative, expected in coverage.get(declared_field, {}).items():
            declared_by = f'audit/news_coverage.json:{declared_field}'
            if expected == 'not-applicable-september-2024':
                not_applicable.append({'original_declared_path': relative, 'declared_value': expected,
                                       'declared_by': declared_by, 'status': 'not_applicable_no_executed_bytes'})
                continue
            data = add(relative, expected, 'executed_helper')
            snapshot = 'tools/replay_snapshots/' + PurePosixPath(relative).name
            require(snapshot not in pending, f'Snapshot name collision: {snapshot}')
            stage(snapshot, data, 'replay_tool_snapshot')
            bindings.append({'original_declared_path': relative, 'snapshot_path': snapshot,
                             'sha256': expected, 'bytes': len(data), 'declared_by': declared_by,
                             'status': 'verified_exact_byte_snapshot'})
    for name, receipt in [('audit/independent_source_review.json', source), ('audit/independent_market_review.json', market)]:
        declared = receipt['independent_replay_tool']
        original = declared['path']
        require(original in EXTERNAL_REPLAY, f'Unapproved external snapshot path: {original}')
        original_path = Path(original)
        require(original_path.is_file() and not original_path.is_symlink(), f'Missing external replay: {original}')
        data = original_path.read_bytes()
        require(digest(data) == declared['sha256'], f'Executed external replay hash mismatch: {original}')
        snapshot = EXTERNAL_REPLAY[original]
        require(snapshot not in pending, f'Snapshot name collision: {snapshot}')
        stage(snapshot, data, 'replay_tool_snapshot')
        bindings.append({'original_declared_path': original, 'snapshot_path': snapshot,
                         'sha256': declared['sha256'], 'bytes': len(data),
                         'declared_by': name + ':independent_replay_tool', 'status': 'verified_exact_byte_snapshot'})

    # These market inputs are hash-bound by the preserved independent market receipt.
    for filename, expected in market.get('data_sha256', {}).items():
        add('data/' + filename, expected, 'accepted_market_data')
    for filename, expected in market.get('action_sha256', {}).items():
        add('audit/' + filename, expected, 'accepted_market_actions')

    mapping = {
        'version': 'september-2024-replay-tool-snapshots-v1',
        'status': 'verified_exact_byte_snapshots_no_tools_executed',
        'bindings': sorted(bindings, key=lambda r: r['original_declared_path']),
        'accepted_archive_relative_inputs': sorted(preserved_replay_inputs, key=lambda r: (r['path'], r['declared_by'])),
        'not_applicable': sorted(not_applicable, key=lambda r: r['original_declared_path']),
        'limitations': [
            'Snapshots retain the executed source bytes, including original absolute paths and write behavior; this packaging tool does not execute them.',
            'The resolver and RSS transport declared not applicable by September coverage have no executed bytes to snapshot.',
            'Original execution metadata and acceptance receipts remain unchanged; this mapping adds safe archive-relative locations.',
        ],
    }
    stage(MAPPING, encoded(mapping), 'snapshot_mapping')
    add('tools/build_source_inventory.py', role='packaging_tool')
    file_list = sorted(rows.values(), key=lambda row: row['path'])
    require(len(file_list) == len({row['path'] for row in file_list}), 'Duplicate final inventory paths')
    inventory = {
        'version': 'september-2024-news-replay-inventory-v1',
        'status': 'all_referenced_files_hash_verified_for_packaging',
        'scope': 'Exact frozen September source replay inputs, physical acquisition responses, staged comparison candidates, acceptance anchors and declared executed-tool snapshots; no report regeneration.',
        'dates': dates,
        'physical_requests': len(requests),
        'counts_by_role': {role: len(paths) for role, paths in sorted(roles.items())},
        'file_count': len(file_list),
        'file_bytes': sum(row['bytes'] for row in file_list),
        'raw_response_uncompressed_bytes_verified': raw_uncompressed_bytes,
        'file_list_sha256': digest(encoded(file_list)),
        'file_list_sha256_serialization': 'UTF-8 json.dumps(files,ensure_ascii=False,indent=2,sort_keys=True) plus LF',
        'anchors': {key: rows[key]['sha256'] for key in (
            'audit/news_query_plan.json', 'audit/news_coverage.json', 'audit/source_freeze.json',
            'audit/independent_source_review.json', 'audit/independent_market_review.json',
            manifest_path, MAPPING, 'tools/build_source_inventory.py')},
        'verification': {
            'every_inventory_file_hash_and_size_verified': True,
            'every_raw_xml_uncompressed_hash_verified_against_query_plan': True,
            'every_parsed_cache_plan_identity_and_raw_binding_verified': True,
            'all_21_unreviewed_provenance_ready_and_candidate_hashes_verified': True,
            'all_inputs_rechecked_unchanged_before_inventory_commit': True,
            'snapshots_verified_against_existing_execution_metadata': True,
            'external_replay_tools_executed_by_packaging': False,
            'report_source_or_acceptance_receipt_mutations': False,
        },
        'not_applicable_tools': mapping['not_applicable'],
        'limitations': [
            'This packaging receipt validates existing byte bindings. It does not reacquire sources, rerun editorial/market acceptance or certify new report content.',
            'Known semantic and timing exclusions remain in the unchanged independent source acceptance receipt.',
            'No unrelated scratch, credentials, CLAUDE files, non-plan cache responses or external filesystem files are archived by this inventory.',
            'Independent replay snapshots preserve original filesystem assumptions; the mapping records safe archive locations without altering executed bytes.',
            'The inventory excludes its own bytes and its build receipt to avoid a self-referential hash. The separate packaging build receipt records the exact inventory SHA-256.',
        ],
        'files': file_list,
    }
    inventory_bytes = encoded(inventory)
    receipt = {
        'version': 'september-2024-source-inventory-packaging-build-v1',
        'status': 'validated_and_committed',
        'inventory_path': INVENTORY,
        'inventory_sha256': digest(inventory_bytes),
        'inventory_bytes': len(inventory_bytes),
        'file_list_sha256': inventory['file_list_sha256'],
        'file_count': inventory['file_count'],
        'file_bytes': inventory['file_bytes'],
        'counts_by_role': inventory['counts_by_role'],
        'snapshot_mapping_path': MAPPING,
        'snapshot_mapping_sha256': digest(pending[MAPPING]),
        'packaging_tool_sha256': rows['tools/build_source_inventory.py']['sha256'],
        'scope': inventory['scope'],
        'limitations': inventory['limitations'],
        'archive_total_file_count_note': 'Inventory file_count is the explicitly preserved replay set; the source archive also includes reports and existing builder-selected artifacts.',
    }

    # Stage all proposed output bytes and compare them before any final output write.
    outputs = {**pending, INVENTORY: inventory_bytes, BUILD_RECEIPT: encoded(receipt)}
    STAGE.mkdir(parents=True, exist_ok=True)
    for relative, data in outputs.items():
        target = STAGE / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    for relative, data in outputs.items():
        require((STAGE / relative).read_bytes() == data, f'Packaging staging mismatch: {relative}')
    for row in file_list:
        if row['path'] in pending:
            data = (STAGE / row['path']).read_bytes()
        else:
            data = safe(row['path']).read_bytes()
        require(digest(data) == row['sha256'] and len(data) == row['bytes'],
                f'Input changed before inventory commit: {row["path"]}')
    # Commit only new packaging outputs. Existing identical outputs remain byte-for-byte.
    for relative, data in outputs.items():
        path = safe(relative, exists=False)
        if path.exists():
            require(path.is_file() and path.read_bytes() == data,
                    f'Refusing to replace differing packaging output: {relative}')
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    check_existing()
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
