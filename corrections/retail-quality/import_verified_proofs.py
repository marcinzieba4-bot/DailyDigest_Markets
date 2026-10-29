"""Import independently observed read-only checks, bound to exact inputs.

This does not generate observations, contact AWS, or change published objects.
"""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def import_public(checkpoint, receipt, manifest_bytes, external, external_sha256):
    expected = {x['key']: x for x in receipt['targets'] if x['key'].startswith('reports/')}
    rows = external.get('rows', [])
    if (external.get('passed') is not True or
            external.get('source_manifest_sha256') != hashlib.sha256(manifest_bytes).hexdigest() or
            external.get('checked_count') != len(expected) or
            external.get('failed_count') != 0 or
            external.get('ci', {}).get('artifact_zip_sha256_verified') is not True or
            len(rows) != len(expected) or {x['key'] for x in rows} != set(expected)):
        raise ValueError('Independent public proof does not cover this manifest')
    imported = {}
    for row in rows:
        item = expected[row['key']]
        if (row.get('passed') is not True or row.get('status') != 200 or
                row.get('sha256') != item['sha256'] or row.get('bytes') != item['bytes'] or
                row.get('actual_sha256') != item['sha256'] or row.get('actual_bytes') != item['bytes']):
            raise ValueError('Independent public bytes differ: ' + row['key'])
        imported[row['key']] = dict(row, proof='independent CI full-body SHA256 and size',
            verified_at_utc=row['observed_at_utc'], external_proof_sha256=external_sha256)
    checkpoint['public'] = imported
    checkpoint['external_public_provenance'] = {
        'proof_file': 'external_revised_public_verification.json',
        'proof_sha256': external_sha256, 'ci': external['ci'],
        'source_commit': external['source_commit']}
    return checkpoint


def import_native(checkpoint, receipt, protected, native, native_sha256):
    expected = {x['key']: x for x in protected}
    records = native.get('records', {})
    if (native.get('passed') is not True or native.get('run') != receipt['run'] or
            native.get('snapshot_sha256') != fingerprint(protected) or
            native.get('verified_count') != len(expected) or set(records) != set(expected)):
        raise ValueError('Native preservation proof does not cover this snapshot')
    for key, row in records.items():
        if (row.get('key') != key or row.get('passed') is not True or
                row.get('baseline_sha256') != expected[key]['sha256'] or
                row.get('proof') not in (
                    'unchanged ETag/size tied to original full SHA256 snapshot',
                    'fresh atomic GET SHA256 equals original snapshot') or not row.get('verified_at_utc')):
            raise ValueError('Native preservation proof mismatch: ' + key)
    checkpoint['protected_snapshot_sha256'] = fingerprint(protected)
    checkpoint['protected'] = records
    checkpoint['native_preservation_proof_sha256'] = native_sha256
    return checkpoint


def main():
    read = lambda name: json.loads((ROOT / 'audit' / name).read_text())
    receipt = read('publication.json')
    manifest_bytes = (ROOT / 'audit/revision_artifacts.json').read_bytes()
    if json.loads(manifest_bytes)['targets'] != receipt['targets']:
        raise ValueError('Publication targets differ from the reviewed manifest')
    path = ROOT / 'audit/live_verification_checkpoint.json'
    checkpoint = json.loads(path.read_text()) if path.exists() else {}
    if checkpoint.get('run') != receipt['run'] or checkpoint.get('targets_sha256') != fingerprint(receipt['targets']):
        checkpoint = {'run': receipt['run'], 'targets_sha256': fingerprint(receipt['targets']),
                      'public': {}, 'protected': {}}
    external_path = ROOT / 'audit/external_revised_public_verification.json'
    import_public(checkpoint, receipt, manifest_bytes, json.loads(external_path.read_text()),
                  hashlib.sha256(external_path.read_bytes()).hexdigest())
    native_path = ROOT / 'audit/native_preservation_proof.json'
    if native_path.exists() and read(native_path.name).get('passed'):
        scope = read('retrospective_scope.json')
        snapshots = read('published_snapshots.json') + read('published_pdf_snapshots.json')
        protected = [x for x in snapshots if x.get('date') in scope['protected_live_dates']]
        import_native(checkpoint, receipt, protected, read(native_path.name),
                      hashlib.sha256(native_path.read_bytes()).hexdigest())
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(checkpoint, indent=2))
    temporary.replace(path)
    print('Imported observed checks:', len(checkpoint['public']), 'public;', len(checkpoint['protected']), 'protected')


if __name__ == '__main__':
    main()
