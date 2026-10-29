"""Offline version-bound publication tests. Run with the AWS-tools Python."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    import boto3
    from botocore.exceptions import ClientError, ReadTimeoutError
except ImportError:
    boto3 = None


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def error(code, status):
    return ClientError({'Error': {'Code': code}, 'ResponseMetadata': {'HTTPStatusCode': status}}, 'test')


@unittest.skipIf(boto3 is None, 'Run publisher tests with /workspace/.report-tools/bin/python (boto3 required)')
class PublishTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / 'publish_revisions.py'
        spec = importlib.util.spec_from_file_location('retail_publish_tested', path)
        self.p = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.p)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / 'repo'
        self.root = self.repo / 'corrections/retail-quality'
        (self.root / 'audit').mkdir(parents=True)
        (self.root / 'work').mkdir()
        self.p.ROOT = self.root
        self.p.RECEIPT = self.root / 'audit/publication.json'
        self.key = 'reports/archive/2025-09-01.html'
        self.original, self.desired = b'original report', b'reviewed revised report'
        (self.root / 'work/report.html').write_bytes(self.desired)
        self.target = {'key': self.key, 'path': 'work/report.html', 'sha256': digest(self.desired), 'bytes': len(self.desired), 'content_type': 'text/html', 'expected_original_sha256': digest(self.original)}
        self.latest = b'latest report unchanged'
        self.fake = FakeS3({self.key: self.original, 'reports/latest.html': self.latest})
        self.cf = FakeCloudFront()
        fake, cf = self.fake, self.cf
        class Session:
            def client(self, name, **kwargs):
                return fake if name == 's3' else cf
        self.patchers = [patch.object(self.p.boto3, 'Session', lambda **kw: Session()), patch.object(self.p.time, 'sleep', lambda _: None), patch.dict(self.p.os.environ, {'AWS_KEY': 'test-key', 'AWS_SECRET': 'test-secret'})]
        for item in self.patchers:
            item.start()
            self.addCleanup(item.stop)

    def receipt(self):
        return json.loads(self.p.RECEIPT.read_text())

    def manifest(self, target=None):
        (self.root / 'work/input.json').write_bytes(b'reviewed evidence')
        (self.root / 'audit/revision_artifacts.json').write_text(json.dumps({'reviewed': True, 'reviewed_inputs':{'work/input.json':digest(b'reviewed evidence')}, 'targets': [target or self.target]}))
        (self.root / 'audit/published_inventory.json').write_text(json.dumps([{'Key': self.key}, {'Key': 'reports/archive/2026-08-03.html'}]))
        (self.root / 'audit/retrospective_scope.json').write_text(json.dumps({'allowed_retrospective_dates': ['2025-09-01'], 'protected_live_dates': ['2026-08-03']}))

    def test_conditional_backup_put_and_exact_sha_gate(self):
        self.p.publish([self.target])
        out = self.receipt()
        state = out['objects'][self.key]
        self.assertEqual(out['stage'], 'published')
        self.assertEqual(self.fake.objects[state['backup_key']], self.original)
        self.assertEqual(state['current']['sha256'], digest(self.desired))
        self.assertTrue(state['backup_sha_verified'])
        self.assertEqual(self.fake.puts[0]['IfMatch'], self.fake.etag(self.original))
        self.assertEqual(self.fake.copies[0]['CopySourceIfMatch'], self.fake.etag(self.original))
        self.assertTrue(out['latest_unchanged'])
        self.assertFalse(out['latest_write_performed'])
        self.assertFalse(out['index_write_performed'])
        self.assertEqual([x['Key'] for x in self.fake.puts], [self.key])
        self.assertTrue(all('index.html' not in x['Key'] and 'latest.html' not in x['Key'] for x in self.fake.puts + self.fake.copies))
        self.assertTrue(all(body.closed for body in self.fake.streams))

    def test_lost_put_response_then412_accepts_only_full_desired_bytes(self):
        self.fake.put_mode = 'lost-response'
        self.p.publish([self.target])
        self.assertEqual(self.fake.objects[self.key], self.desired)
        self.assertTrue(self.receipt()['objects'][self.key]['verified'])
        self.assertEqual(self.fake.put_calls, 2)

    def test_unrelated_foreign_version_after412_is_rejected(self):
        self.fake.put_mode = 'foreign-412'
        with self.assertRaisesRegex(ValueError, 'failed SHA check'):
            self.p.publish([self.target])
        state = self.receipt()['objects'][self.key]
        self.assertNotIn('verified', state)
        self.assertEqual(self.fake.objects[state['backup_key']], self.original)
        self.assertEqual(self.fake.objects[self.key], b'foreign bytes')
        self.assertEqual(len(self.cf.calls), 0)

    def test_transport_interruption_preserves_backup_and_resumes(self):
        self.fake.put_mode = 'fail-before-write'
        with self.assertRaises(ReadTimeoutError):
            self.p.publish([self.target])
        first = self.receipt()
        backup = first['objects'][self.key]['backup_key']
        self.assertEqual(self.fake.objects[backup], self.original)
        self.assertEqual(self.fake.objects[self.key], self.original)
        self.fake.put_mode = None
        self.p.publish([self.target], resume=True)
        final = self.receipt()
        self.assertEqual(final['run'], first['run'])
        self.assertEqual(final['backup_prefix'], first['backup_prefix'])
        self.assertEqual(self.fake.objects[backup], self.original)
        self.assertEqual(len(self.fake.copies), 1)
        self.assertEqual(final['stage'], 'published')

    def test_resume_rejects_changed_targets_before_mutation(self):
        self.p.publish([self.target])
        changed = copy.deepcopy(self.target)
        changed['sha256'] = 'f' * 64
        counts = len(self.fake.puts), len(self.fake.copies), len(self.cf.calls)
        with self.assertRaisesRegex(ValueError, 'exact original targets'):
            self.p.publish([changed], resume=True)
        self.assertEqual(counts, (len(self.fake.puts), len(self.fake.copies), len(self.cf.calls)))

    def test_verified_receipt_proof_cannot_skip_a_changed_remote_version(self):
        self.p.publish([self.target])
        self.fake.objects[self.key] = b'foreign later version'
        with self.assertRaisesRegex(ValueError, 'before final gate'):
            self.p.publish([self.target], resume=True)

    def test_resume_revalidates_original_backup(self):
        self.p.publish([self.target])
        before = self.receipt()
        self.fake.objects[before['objects'][self.key]['backup_key']] = b'corrupted backup'
        with self.assertRaisesRegex(ValueError, 'Original backup changed'):
            self.p.publish([self.target], resume=True)

    def test_existing_partial_backup_is_never_overwritten(self):
        # Freeze the run clock indirectly by stopping after the receipt save.
        original_save = self.p.save
        def save_and_preseed(path, receipt):
            original_save(path, receipt)
            if not receipt['objects']:
                self.fake.objects[receipt['backup_prefix'] + self.key] = b'foreign backup'
        with patch.object(self.p, 'save', save_and_preseed):
            with self.assertRaisesRegex(ValueError, 'Existing backup differs'):
                self.p.publish([self.target])
        self.assertEqual(self.fake.copies, [])
        self.assertEqual(self.fake.puts, [])

    def test_reviewed_original_hash_blocks_intervening_change(self):
        self.fake.objects[self.key] = b'foreign changed before backup'
        with self.assertRaisesRegex(ValueError, 'Original changed since review'):
            self.p.publish([self.target])
        self.assertEqual(self.fake.copies, [])
        self.assertEqual(self.fake.puts, [])

    def test_plan_scope_hash_original_and_path_gates(self):
        self.manifest()
        self.assertEqual(self.p.plan(), [self.target])
        for key in ['reports/latest.html', 'reports/index.html', 'Strategies/2025-09-02_Market_Intelligence.pdf', 'reports/2025-09/Anything_2025_Weekday_Reports.zip']:
            bad = {**self.target, 'key': key}
            self.manifest(bad)
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'Out-of-scope'):
                self.p.plan()
        bad = {**self.target, 'sha256': '0' * 64}
        self.manifest(bad)
        with self.assertRaisesRegex(ValueError, 'Artifact changed'):
            self.p.plan()
        bad = dict(self.target)
        bad.pop('expected_original_sha256')
        self.manifest(bad)
        with self.assertRaisesRegex(ValueError, 'Reviewed original SHA256'):
            self.p.plan()
        outside = Path(self.tmp.name) / 'outside.html'
        outside.write_bytes(self.desired)
        self.manifest({**self.target, 'path': str(outside)})
        with self.assertRaisesRegex(ValueError, 'leaves repository'):
            self.p.plan()

    def test_resume_prefix_and_proof_fields_are_bound(self):
        self.p.publish([self.target])
        receipt = self.receipt()
        bad = copy.deepcopy(receipt)
        bad['backup_prefix'] = 'reports/_retrospective_backup/somewhere-else/'
        with self.assertRaisesRegex(ValueError, 'backup prefix'):
            self.p.validate_resume(bad, [self.target])
        bad = copy.deepcopy(receipt)
        bad['objects'][self.key]['current']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'current artifact proof'):
            self.p.validate_resume(bad, [self.target])

    def test_published_live_edition_is_protected_from_revision(self):
        self.manifest({**self.target, 'key': 'reports/archive/2026-08-03.html'})
        with self.assertRaisesRegex(ValueError, 'Out-of-scope'):
            self.p.plan()

    def test_reviewed_input_edit_invalidates_publication_gate(self):
        self.manifest()
        (self.root / 'work/input.json').write_bytes(b'changed after review')
        with self.assertRaisesRegex(ValueError, 'Reviewed input changed'):
            self.p.plan()


class FakeS3:
    def __init__(self, objects):
        self.objects = dict(objects)
        self.copies, self.puts, self.streams = [], [], []
        self.put_mode = None
        self.put_calls = 0

    @staticmethod
    def etag(blob):
        return '"' + hashlib.md5(blob).hexdigest() + '"'

    def get_object(self, **kwargs):
        key = kwargs['Key']
        if key not in self.objects:
            raise error('NoSuchKey', 404)
        body = io.BytesIO(self.objects[key])
        self.streams.append(body)
        return {'Body': body, 'ETag': self.etag(self.objects[key])}

    def head_object(self, **kwargs):
        blob = self.objects[kwargs['Key']]
        return {'ETag': self.etag(blob), 'ContentLength': len(blob)}

    def copy_object(self, **kwargs):
        source = self.objects[kwargs['CopySource']['Key']]
        if kwargs['CopySourceIfMatch'] != self.etag(source):
            raise error('PreconditionFailed', 412)
        self.copies.append(kwargs)
        self.objects[kwargs['Key']] = source

    def put_object(self, **kwargs):
        self.put_calls += 1
        if self.put_mode == 'fail-before-write':
            raise ReadTimeoutError(endpoint_url='https://test.invalid')
        if self.put_mode == 'foreign-412':
            self.objects[kwargs['Key']] = b'foreign bytes'
            raise error('PreconditionFailed', 412)
        old = self.objects[kwargs['Key']]
        if kwargs['IfMatch'] != self.etag(old):
            raise error('PreconditionFailed', 412)
        self.puts.append(kwargs)
        self.objects[kwargs['Key']] = kwargs['Body']
        if self.put_mode == 'lost-response':
            raise ReadTimeoutError(endpoint_url='https://test.invalid')


class FakeCloudFront:
    def __init__(self): self.calls = []
    def create_invalidation(self, **kwargs):
        self.calls.append(kwargs)
        return {'Invalidation': {'Id': 'offline-invalidation', 'Status': 'Completed'}}


if __name__ == '__main__':
    unittest.main()
