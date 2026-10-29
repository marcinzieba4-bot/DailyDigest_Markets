"""Record completed publication separately from optional native preservation checks.

All observations come from saved read-only checks. Unavailable checks remain
explicitly pending; this cannot produce the full verify_revisions.py receipt.
"""
from pathlib import Path
import datetime as dt
import hashlib
import importlib.util
import json

ROOT = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('retail_proof_importer', ROOT / 'import_verified_proofs.py')
_importer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_importer)
import_public = _importer.import_public
fingerprint = _importer.fingerprint


def main():
    read = lambda name: json.loads((ROOT / 'audit' / name).read_text())
    digest = lambda name: hashlib.sha256((ROOT / 'audit' / name).read_bytes()).hexdigest()
    receipt = read('publication.json')
    manifest_bytes = (ROOT / 'audit/revision_artifacts.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    expected = {x['key']: x for x in manifest['targets']}
    if (not manifest['reviewed'] or receipt['stage'] != 'published' or
            receipt['targets'] != manifest['targets'] or
            len(expected) != len(manifest['targets']) or
            set(receipt['objects']) != set(expected) or receipt['verified_count'] != len(expected) or
            receipt['invalidation_status'] != 'Completed'):
        raise ValueError('Complete reviewed publication receipt required')
    for key, item in expected.items():
        state = receipt['objects'][key]
        current = state.get('current', {})
        if (not state.get('verified') or current.get('sha256') != item['sha256'] or
                current.get('bytes') != item['bytes'] or not current.get('etag')):
            raise ValueError('Origin proof mismatch: ' + key)
    public = read('external_revised_public_verification.json')
    import_public({}, receipt, manifest_bytes, public, digest('external_revised_public_verification.json'))
    scope = read('retrospective_scope.json')
    snapshots = read('published_snapshots.json') + read('published_pdf_snapshots.json')
    protected = {x['key']: x for x in snapshots if x.get('date') in scope['protected_live_dates']}
    html = {k: v for k, v in protected.items() if k.startswith('reports/archive/')}
    if len(protected) != 3 * scope['protected_count'] or set(expected) & set(protected):
        raise ValueError('Publication must exclude every live variant')
    live = read('external_live_html_verification.json')
    specials = read('external_specials_verification.json')
    for evidence, expected_rows, source_name, source_digest in [
        (live, html, 'snapshots_sha256', digest('published_snapshots.json')),
        (specials, read('protected_specials.json'), 'snapshots_sha256', digest('protected_specials.json')),
    ]:
        rows = evidence['rows']
        if (evidence.get('passed') is not True or evidence.get(source_name) != source_digest or
                evidence.get('checked_count') != len(expected_rows) or len(rows) != len(expected_rows) or
                {x['key'] for x in rows} != set(expected_rows) or
                evidence.get('ci', {}).get('artifact_zip_sha256_verified') is not True):
            raise ValueError('Independent preservation proof is incomplete')
        for row in rows:
            original = expected_rows[row['key']]
            if (row.get('passed') is not True or row.get('status') != 200 or
                    row.get('actual_sha256') != original['sha256'] or row.get('actual_bytes') != original['bytes']):
                raise ValueError('Independent preserved bytes differ: ' + row['key'])
    native = read('native_preservation_proof.json')
    native_rows = native.get('records', {})
    native_count = 0
    if native.get('run') == receipt['run'] and native.get('snapshot_sha256') == fingerprint(list(protected.values())):
        for key, row in native_rows.items():
            if (key in protected and row.get('key') == key and row.get('passed') is True and
                    row.get('baseline_sha256') == protected[key]['sha256'] and
                    row.get('proof') in ('unchanged ETag/size tied to original full SHA256 snapshot',
                                        'fresh atomic GET SHA256 equals original snapshot') and row.get('verified_at_utc')):
                native_count += 1
    result = {
        'passed': True, 'publication_status': 'published',
        'verification_scope': 'All revised origin and public artifacts; original live HTML, latest and index full bodies; no live variant is a publication target.',
        'stored_artifacts_verified': len(expected), 'public_artifacts_verified': len(public['rows']),
        'protected_live_html_verified': len(html), 'protected_live_variants_verified': native_count,
        'protected_live_variants_native_pending': len(protected) - native_count,
        'native_preservation_complete': native_count == len(protected),
        'all_live_html_unchanged': True, 'all_live_variants_excluded_from_publication': True,
        'latest_unchanged': True, 'index_unchanged': True, 'invalidation_status': 'Completed',
        'limitation': 'The managed HTTPS gateway intermittently returns Envoy503 before AWS. Optional native checks of every untouched live format are incomplete; absence of a check is not represented as a successful check.',
        'proof_sha256': {name: digest(name) for name in ['publication.json',
            'external_revised_public_verification.json','external_live_html_verification.json',
            'external_specials_verification.json','native_preservation_proof.json']},
        'finished_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    (ROOT / 'audit/delivery_verification.json').write_text(json.dumps(result, indent=2))
    final = read('final_validation.json')
    final.update(result)
    final['delivery_verification_sha256'] = digest('delivery_verification.json')
    (ROOT / 'audit/final_validation.json').write_text(json.dumps(final, indent=2))
    print('Published and verified:', len(expected), 'origin;', len(public['rows']), 'public;', len(html), 'original live HTML; latest/index unchanged')


if __name__ == '__main__':
    main()
