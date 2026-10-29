"""Offline regression checks for resumable verification and proof ingestion."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


ingest = module('verified_proof_import_test', HERE / 'import_verified_proofs.py')
try:
    import boto3
except ImportError:
    boto3 = None


def proof_fixture():
    targets = [
        {'key': 'reports/archive/2025-09-01.html', 'sha256': sha(b'first'), 'bytes': 5},
        {'key': 'reports/archive/2025-09-02.html', 'sha256': sha(b'second'), 'bytes': 6},
        {'key': 'Strategies/2025-09-01.pdf', 'sha256': sha(b'private'), 'bytes': 7},
    ]
    receipt = {'run': '20261029T120000Z', 'targets': targets}
    checkpoint = {'run': receipt['run'], 'targets_sha256': ingest.fingerprint(targets), 'public': {}, 'protected': {}}
    manifest = json.dumps({'targets': targets}).encode()
    external = {
        'passed': True, 'source_manifest_sha256': sha(manifest), 'checked_count': 2, 'failed_count': 0,
        'source_commit': 'a' * 40, 'ci': {'artifact_zip_sha256_verified': True}, 'rows': [],
    }
    for item in targets[:2]:
        external['rows'].append(dict(item, passed=True, status=200,
            actual_sha256=item['sha256'], actual_bytes=item['bytes'], observed_at_utc='2026-10-29T12:01:00Z'))
    return checkpoint, receipt, manifest, external


class ProofImportTests(unittest.TestCase):
    def test_public_complete_body_proof_imports_with_provenance(self):
        checkpoint, receipt, manifest, external = proof_fixture()
        result = ingest.import_public(checkpoint, receipt, manifest, external, 'b' * 64)
        self.assertIs(result, checkpoint)
        self.assertEqual(set(result['public']), {x['key'] for x in receipt['targets'][:2]})
        row = result['public'][receipt['targets'][0]['key']]
        self.assertEqual(row['external_proof_sha256'], 'b' * 64)
        self.assertEqual(row['verified_at_utc'], external['rows'][0]['observed_at_utc'])
        self.assertEqual(result['external_public_provenance']['source_commit'], external['source_commit'])

    def test_public_rejects_invalid_observations_and_incomplete_sets(self):
        mutations = [
            lambda x: x.update(passed=False),
            lambda x: x.update(source_manifest_sha256='0' * 64),
            lambda x: x.update(checked_count=1),
            lambda x: x.update(failed_count=1),
            lambda x: x['ci'].update(artifact_zip_sha256_verified=False),
            lambda x: x['rows'][0].update(status=503),
            lambda x: x['rows'][0].update(passed=False),
            lambda x: x['rows'][0].update(sha256='0' * 64),
            lambda x: x['rows'][0].update(actual_sha256='0' * 64),
            lambda x: x['rows'][0].update(bytes=999),
            lambda x: x['rows'][0].update(actual_bytes=999),
            lambda x: x['rows'].pop(),
            lambda x: x['rows'].__setitem__(1, copy.deepcopy(x['rows'][0])),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                checkpoint, receipt, manifest, external = proof_fixture()
                untouched = copy.deepcopy(checkpoint)
                mutate(external)
                with self.assertRaises(ValueError):
                    ingest.import_public(checkpoint, receipt, manifest, external, 'b' * 64)
                self.assertEqual(checkpoint, untouched)

    def native_fixture(self):
        checkpoint, receipt, _, _ = proof_fixture()
        protected = [{'key': 'protected-one', 'sha256': '1' * 64, 'bytes': 12, 'etag': 'one'},
                     {'key': 'protected-two', 'sha256': '2' * 64, 'bytes': 34, 'etag': 'two'}]
        native = {'passed': True, 'run': receipt['run'], 'snapshot_sha256': ingest.fingerprint(protected), 'verified_count': 2, 'records': {}}
        for item in protected:
            native['records'][item['key']] = {
                'key': item['key'], 'passed': True, 'baseline_sha256': item['sha256'],
                'proof': 'unchanged ETag/size tied to original full SHA256 snapshot',
                'verified_at_utc': '2026-10-29T12:02:00Z',
            }
        return checkpoint, receipt, protected, native

    def test_native_complete_snapshot_proof_imports_with_provenance(self):
        checkpoint, receipt, protected, native = self.native_fixture()
        result = ingest.import_native(checkpoint, receipt, protected, native, 'c' * 64)
        self.assertEqual(result['protected_snapshot_sha256'], ingest.fingerprint(protected))
        self.assertEqual(result['protected'], native['records'])
        self.assertEqual(result['native_preservation_proof_sha256'], 'c' * 64)

    def test_native_rejects_wrong_run_snapshot_missing_keys_and_bad_baselines(self):
        mutations = [
            lambda x: x.update(passed=False),
            lambda x: x.update(run='different-run'),
            lambda x: x.update(snapshot_sha256='0' * 64),
            lambda x: x.update(verified_count=1),
            lambda x: x['records'].pop('protected-two'),
            lambda x: x['records']['protected-one'].update(key='different-key'),
            lambda x: x['records']['protected-one'].update(passed=False),
            lambda x: x['records']['protected-one'].update(baseline_sha256='0' * 64),
            lambda x: x['records']['protected-one'].update(proof='only an HTTP status'),
            lambda x: x['records']['protected-one'].pop('verified_at_utc'),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                checkpoint, receipt, protected, native = self.native_fixture()
                before = copy.deepcopy(checkpoint)
                mutate(native)
                with self.assertRaises(ValueError):
                    ingest.import_native(checkpoint, receipt, protected, native, 'c' * 64)
                self.assertEqual(checkpoint, before)

    def test_import_entrypoint_checks_manifest_targets_and_resets_wrong_checkpoint(self):
        checkpoint, receipt, manifest, external = proof_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'audit').mkdir()
            write = lambda name, x: (root / 'audit' / name).write_text(json.dumps(x))
            write('publication.json', receipt)
            write('revision_artifacts.json', json.loads(manifest))
            write('external_revised_public_verification.json', external)
            write('live_verification_checkpoint.json', {'run': 'stale', 'targets_sha256': 'stale', 'public': {'stale': {}}, 'protected': {'stale': {}}})
            with patch.object(ingest, 'ROOT', root):
                ingest.main()
            actual = json.loads((root / 'audit/live_verification_checkpoint.json').read_text())
            self.assertEqual(actual['run'], receipt['run'])
            self.assertEqual(actual['targets_sha256'], ingest.fingerprint(receipt['targets']))
            self.assertEqual(actual['protected'], {})
            changed = json.loads(manifest); changed['targets'][0]['bytes'] += 1
            write('revision_artifacts.json', changed)
            before = (root / 'audit/live_verification_checkpoint.json').read_bytes()
            with patch.object(ingest, 'ROOT', root), self.assertRaisesRegex(ValueError, 'targets differ'):
                ingest.main()
            self.assertEqual((root / 'audit/live_verification_checkpoint.json').read_bytes(), before)


class SequentialExecutor:
    def __init__(self, **kwargs): pass
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def map(self, function, iterable): return map(function, iterable)


@unittest.skipIf(boto3 is None, 'Run with /workspace/.report-tools/bin/python for boto3')
class VerificationCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.v = module('retail_verifier_offline_test', HERE / 'verify_revisions.py')
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); (self.root / 'audit').mkdir()
        self.v.ROOT = self.root
        self.targets = [{'key': f'reports/archive/2025-09-{i:02}.html', 'sha256': sha(f'body{i}'.encode()), 'bytes': len(f'body{i}')} for i in range(1, 7)]
        self.receipt = {'stage': 'published', 'run': '20261029T120000Z', 'invalidation_status': 'Completed', 'invalidation_id': 'offline-id', 'targets': self.targets, 'objects': {}, 'verified_count': len(self.targets)}
        for target in self.targets:
            self.receipt['objects'][target['key']] = {'verified': True, 'current': {'sha256': target['sha256'], 'bytes': target['bytes'], 'etag': 'stored'}}
        self.protected = []
        for day in range(1, 5):
            for suffix in ('html', 'json', 'pdf'):
                key = f'protected/{day}.{suffix}'; body = key.encode()
                self.protected.append({'date': f'2026-08-{day:02}', 'key': key, 'format': suffix, 'sha256': sha(body), 'bytes': len(body), 'etag': 'original-' + key})
        self.head_calls, self.public_calls, self.read_calls = [], [], []
        self.head_fail = False; self.public_fail = False
        self.head_override = {}; self.read_override = {}
        self.latest = b'unchanged latest'
        self.index = (' '.join(f'archive/2025-09-{i:02}.html' for i in range(1, 7))).encode()
        test = self
        class S3:
            def head_object(self, **kwargs):
                key = kwargs['Key']; test.head_calls.append(key)
                if test.head_fail and len(test.head_calls) > 1: raise OSError('offline gateway unavailable')
                if key in test.head_override: return test.head_override[key]
                item = next(x for x in test.protected if x['key'] == key)
                return {'ETag': item['etag'], 'ContentLength': item['bytes']}
        class CDN:
            calls = 0
            def get_invalidation(self, **kwargs):
                self.calls += 1
                return {'Invalidation': {'Status': 'Completed'}}
        self.cdn = CDN(); self.s3 = S3()
        class Session:
            def client(self, name, **kwargs): return test.s3 if name == 's3' else test.cdn
        def public(item):
            self.public_calls.append(item['key'])
            if self.public_fail and len(self.public_calls) > 1: raise OSError('offline gateway unavailable')
            return dict(item, status=200, passed=True)
        def read(s3, key):
            self.read_calls.append(key)
            if key in self.read_override: return self.read_override[key]
            body = self.latest if key == 'reports/latest.html' else self.index if key == 'reports/index.html' else key.encode()
            return {'sha256': sha(body), 'bytes': len(body), 'etag': 'read'}, body
        self.patchers = [patch.object(self.v.boto3, 'Session', lambda **kwargs: Session()), patch.object(self.v, 'public', public), patch.object(self.v, 'read', read), patch.object(self.v, 'request', lambda function: function()), patch.object(self.v.cf, 'ThreadPoolExecutor', SequentialExecutor), patch.dict(self.v.os.environ, {'AWS_KEY': 'offline-test', 'AWS_SECRET': 'offline-test'})]
        for p in self.patchers: p.start(); self.addCleanup(p.stop)
        self.write('publication.json', self.receipt)
        self.write('retrospective_scope.json', {'protected_live_dates': sorted({x['date'] for x in self.protected}), 'protected_count': 4})
        self.write('published_snapshots.json', [x for x in self.protected if x['format'] != 'pdf'])
        self.write('published_pdf_snapshots.json', [x for x in self.protected if x['format'] == 'pdf'])
        self.write('protected_specials.json', {'reports/latest.html': {'sha256': sha(self.latest)}, 'reports/index.html': {'sha256': sha(self.index)}})
        self.write('revision_artifacts.json', {'dates': [f'2025-09-{i:02}' for i in range(1, 7)]})
        self.write('final_validation.json', {'publication_status': 'ready'})

    def write(self, name, value):
        (self.root / 'audit' / name).write_text(json.dumps(value))

    def checkpoint(self):
        return json.loads((self.root / 'audit/live_verification_checkpoint.json').read_text())

    def test_complete_run_then_matching_checkpoint_reuses_all_observations(self):
        self.v.main()
        self.assertEqual(self.cdn.calls, 0)
        self.assertEqual(len(self.public_calls), 6)
        self.assertEqual(len(self.head_calls), 12)
        first = self.checkpoint()
        self.public_calls.clear(); self.head_calls.clear()
        self.v.main()
        self.assertEqual(self.public_calls, [])
        self.assertEqual(self.head_calls, [])
        self.assertEqual(self.checkpoint(), first)
        self.assertTrue(json.loads((self.root / 'audit/final_validation.json').read_text())['passed'])

    def test_full_verification_clears_a_previous_transport_limitation(self):
        self.write('final_validation.json', {'protected_live_variants_native_pending': 11,
            'native_preservation_complete': False, 'limitation': 'native checks pending'})
        self.v.main()
        final = json.loads((self.root / 'audit/final_validation.json').read_text())
        self.assertEqual(final['protected_live_variants_native_pending'], 0)
        self.assertTrue(final['native_preservation_complete'])
        self.assertIsNone(final['limitation'])

    def test_changed_run_or_target_fingerprint_drops_cached_proofs(self):
        for field in ('run', 'targets_sha256'):
            with self.subTest(field=field):
                self.v.main(); cached = self.checkpoint(); cached[field] = 'wrong'
                self.write('live_verification_checkpoint.json', cached)
                self.public_calls.clear(); self.head_calls.clear()
                self.v.main()
                self.assertEqual(len(self.public_calls), 6)
                self.assertEqual(len(self.head_calls), 12)

    def test_changed_snapshot_fingerprint_preserves_public_but_rechecks_protected(self):
        self.v.main(); self.public_calls.clear(); self.head_calls.clear()
        self.protected[0]['etag'] = 'new-baseline-metadata'
        self.write('published_snapshots.json', [x for x in self.protected if x['format'] != 'pdf'])
        self.v.main()
        self.assertEqual(self.public_calls, [])
        self.assertEqual(len(self.head_calls), 12)

    def test_public_circuit_retains_success_and_resume_only_fetches_missing(self):
        self.public_fail = True
        with self.assertRaisesRegex(ValueError, 'Public checks pending'):
            self.v.main()
        cached = self.checkpoint()
        self.assertEqual(len(self.public_calls), 4)
        self.assertEqual(set(cached['public']), {self.targets[0]['key']})
        self.assertFalse((self.root / 'audit/live_verification.json').exists())
        self.public_fail = False; self.public_calls.clear()
        self.v.main()
        self.assertEqual(len(self.public_calls), 5)
        self.assertNotIn(self.targets[0]['key'], self.public_calls)

    def test_protected_circuit_retains_success_and_resume_only_fetches_missing(self):
        self.head_fail = True
        with self.assertRaisesRegex(ValueError, 'Live preservation checks pending'):
            self.v.main()
        self.assertEqual(len(self.head_calls), 4)
        self.assertEqual(set(self.checkpoint()['protected']), {self.protected[0]['key']})
        self.head_fail = False; self.head_calls.clear(); self.public_calls.clear()
        self.v.main()
        self.assertEqual(self.public_calls, [])
        self.assertEqual(len(self.head_calls), 11)
        self.assertNotIn(self.protected[0]['key'], self.head_calls)

    def test_changed_etag_requires_atomic_body_proof(self):
        key = self.protected[0]['key']; self.head_override[key] = {'ETag': 'new-version', 'ContentLength': self.protected[0]['bytes']}
        self.v.main()
        row = self.checkpoint()['protected'][key]
        self.assertEqual(row['proof'], 'fresh atomic GET SHA256 equals original snapshot')
        self.assertIn(key, self.read_calls)

    def test_wrong_protected_bytes_never_become_a_success(self):
        key = self.protected[0]['key']; self.head_override[key] = {'ETag': 'foreign', 'ContentLength': 3}
        self.read_override[key] = ({'sha256': sha(b'bad'), 'bytes': 3}, b'bad')
        with self.assertRaisesRegex(ValueError, 'Live preservation checks pending'):
            self.v.main()
        self.assertNotIn(key, self.checkpoint()['protected'])
        self.assertFalse((self.root / 'audit/live_verification.json').exists())

    def test_incomplete_stored_receipt_rejected_before_network(self):
        self.receipt['verified_count'] -= 1; self.write('publication.json', self.receipt)
        with self.assertRaisesRegex(ValueError, 'Complete stored-artifact receipt'):
            self.v.main()
        self.assertEqual(self.public_calls, []); self.assertEqual(self.head_calls, [])

    def test_stored_wrong_hash_rejected_before_network(self):
        self.receipt['objects'][self.targets[0]['key']]['current']['sha256'] = '0' * 64; self.write('publication.json', self.receipt)
        with self.assertRaisesRegex(ValueError, 'Stored-artifact proof mismatch'):
            self.v.main()
        self.assertEqual(self.public_calls, []); self.assertEqual(self.head_calls, [])

    def test_latest_or_index_change_prevents_final_success(self):
        self.read_override['reports/latest.html'] = ({'sha256': sha(b'changed')}, b'changed')
        with self.assertRaisesRegex(ValueError, 'latest/index bytes changed'):
            self.v.main()
        self.assertFalse((self.root / 'audit/live_verification.json').exists())


if __name__ == '__main__':
    unittest.main()
