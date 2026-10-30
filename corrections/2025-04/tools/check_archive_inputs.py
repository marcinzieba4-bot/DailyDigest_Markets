"""Check source-export guards in temporary fixtures and current inputs read-only.

Does not render reports, create the real source ZIP or change frozen inputs.
"""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import datetime as dt
import gzip
import hashlib
import importlib.util
import json
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    spec = importlib.util.spec_from_file_location('apr_builder_archive_checks', ROOT/'tools/build_artifacts.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    stable = [ROOT/'audit/news_replay_inventory.json', ROOT/'checks/source_acquisition_independent_review.json']
    stable.extend(ROOT/'feeds'/f'{d}.json.gz' for d in builder.DATES)
    before = {str(p.relative_to(ROOT)): sha(p) for p in stable}
    passed = []
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        for directory in ['collection', 'feeds', 'audit', 'checks', 'tools', 'cache/news', 'work/recovery_batch1']:
            (root/directory).mkdir(parents=True, exist_ok=True)
        date = '2025-04-01'
        feed = root/'feeds'/f'{date}.json.gz'
        feed.write_bytes(gzip.compress(b'{"items":[]}', mtime=0))
        cache = root/'cache/news/query.json.gz'
        cache.write_bytes(gzip.compress(b'{"status":"fetched"}', mtime=0))
        inventory_path = root/'audit/news_replay_inventory.json'
        inventory = {'status': 'complete', 'complete': True, 'files': [
            {'path': str(p.relative_to(root)), 'sha256': sha(p), 'bytes': p.stat().st_size}
            for p in [feed, cache]]}
        inventory_path.write_text(json.dumps(inventory))
        required = ['market_prose_review.json', 'retail_editorial_review.json', 'cited_metadata_independent_review.json']
        for name in required:
            (root/'checks'/name).write_text('{}')
        capture = root/'work/recovery_batch1/payload.json'
        capture.write_text('{"bound":"capture"}')
        proof = {field: 'verified-'+field for field in [
            'commit_sha', 'input_sha256', 'output_sha256', 'payload_sha256',
            'workflow_run_id', 'workflow_job_id', 'job_log_sha256']}
        receipt_path = root/'audit/metadata_ci_ingestion_batch1.json'
        receipt = {'files': 'work/recovery_batch1', 'all_hash_checks_passed': True, **proof}
        receipt_path.write_text(json.dumps(receipt))
        fake_importer = SimpleNamespace(verify=lambda _: (None, proof, None, None))
        with patch.object(builder, 'ROOT', root), patch.object(builder, 'module', lambda _: fake_importer):
            record = builder.frozen_archive([date])
            archive_path = root/record['path']
            with zipfile.ZipFile(archive_path) as archive:
                names = archive.namelist()
                assert len(names) == len(set(names)) and archive.testzip() is None
                assert all(row['path'] in names for row in inventory['files'])
                assert all('checks/'+name in names for name in required)
                assert 'work/recovery_batch1/payload.json' in names
            passed.append('valid_replay_and_late_metadata_and_review_files_included_once')
            intact = sha(archive_path)

            def reject(name, expected):
                try:
                    builder.frozen_archive([date])
                except ValueError as error:
                    assert expected in str(error), str(error)
                else:
                    raise AssertionError('Accepted '+name)
                assert sha(archive_path) == intact
                assert not archive_path.with_suffix('.zip.tmp').exists()
                passed.append(name)

            changed = json.loads(json.dumps(inventory))
            changed['files'][1]['sha256'] = '0'*64
            inventory_path.write_text(json.dumps(changed))
            reject('changed_replay_hash_rejected_archive_preserved', 'Replay input changed')
            changed['files'][1]['path'] = '../outside'
            inventory_path.write_text(json.dumps(changed))
            reject('replay_path_escape_rejected_archive_preserved', 'out-of-scope replay input')
            inventory_path.write_text(json.dumps({'status': 'incomplete', 'files': []}))
            reject('incomplete_inventory_rejected_archive_preserved', 'Completed news replay inventory')
            inventory_path.write_text(json.dumps(inventory))
            retail_path = root/'checks/retail_editorial_review.json'
            retail_path.unlink()
            reject('missing_final_review_rejected_archive_preserved', 'Final source archive requires')
            retail_path.write_text('{}')
            changed = dict(receipt, commit_sha='changed')
            receipt_path.write_text(json.dumps(changed))
            reject('late_metadata_proof_drift_rejected', 'Metadata recovery proof changed')
            receipt_path.write_text(json.dumps(dict(receipt, all_hash_checks_passed=False)))
            reject('incomplete_metadata_proof_rejected', 'Incomplete metadata recovery proof')
            receipt_path.write_text(json.dumps(receipt))
            (root/'checks/market_prose_review.json').write_text(json.dumps({
                'numeric_diagnostic': {'path': 'work/recovery_batch1/payload.json', 'sha256': '0'*64}}))
            reject('changed_market_review_support_rejected', 'Market prose support changed')
            (root/'checks/market_prose_review.json').write_text('{}')
            (root/'audit/canonical_source_exceptions.json').write_text(json.dumps({'exceptions': [
                {'date': date, 'timing_proof_file': 'work/recovery_batch1/payload.json', 'timing_proof_sha256': '0'*64}]}))
            reject('changed_timing_proof_rejected', 'Timing proof changed')
            (root/'audit/canonical_source_exceptions.json').unlink()
            (root/'checks/source_input_acceptance.json').write_text(json.dumps({
                'source_review_gate_sha256': '0'*64,
                'acceptance_gate_snapshot': {'path': 'work/recovery_batch1/payload.json', 'sha256': '0'*64},
                'source_gate_rejection_checks_sha256': sha(capture),
                'acceptance_check_receipt_snapshot': {'path': 'work/recovery_batch1/payload.json', 'sha256': sha(capture)}}))
            reject('changed_initial_acceptance_snapshot_rejected', 'Initial author acceptance snapshot changed')
            (root/'checks/source_input_acceptance.json').unlink()
            portable = root/'audit/market_prose_inputs.json'
            portable.write_text(json.dumps({'files': [{'path': 'work/recovery_batch1/payload.json',
                                                     'sha256': '0'*64, 'bytes': capture.stat().st_size}]}))
            (root/'checks/market_prose_review.json').write_text(json.dumps({
                'portable_inputs': {'path': 'audit/market_prose_inputs.json', 'sha256': sha(portable)}}))
            reject('changed_portable_market_support_rejected', 'Market prose portable input changed')
            (root/'checks/market_prose_review.json').write_text('{}')
            retail_path.write_text(json.dumps({'proposals_sha256': '0'*64}))
            reject('missing_retail_proposal_support_rejected', 'Retail editorial proposal support changed')
            retail_path.write_text('{}')
    paths = builder.source_archive_inputs(builder.DATES)
    names = {str(path.relative_to(ROOT)) for path in paths}
    inventory = json.loads((ROOT/'audit/news_replay_inventory.json').read_text())
    assert {row['path'] for row in inventory['files']} <= names
    assert all(sha(ROOT/name) == digest for name, digest in before.items())
    final_names = ['checks/'+name for name in ['market_prose_review.json', 'retail_editorial_review.json',
                                              'cited_metadata_independent_review.json']]
    report = {'passed': True, 'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'scope': 'Temporary source-export corruption fixtures and current source member enumeration; final prose/review readiness is separate.',
              'checks': passed, 'builder_sha256': sha(ROOT/'tools/build_artifacts.py'),
              'checker_sha256': sha(Path(__file__)), 'frozen_inputs_unchanged': True,
              'frozen_inventory_sha256': sha(ROOT/'audit/news_replay_inventory.json'),
              'frozen_inventory_files': len(inventory['files']), 'current_source_members': len(paths),
              'current_source_member_bytes': sum(path.stat().st_size for path in paths),
              'final_review_files_not_yet_present': [name for name in final_names if name not in names],
              'real_exports_built': False, 'network_calls': 0}
    (ROOT/'checks/tooling_archive_integration.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
