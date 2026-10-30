"""Bind final report, review and delivery receipts to this exact June build."""
from pathlib import Path
import argparse
import datetime as dt
import hashlib
import importlib.util
import json

ROOT = Path(__file__).resolve().parent.parent
DATES = [dt.date(2025, 6, n).isoformat() for n in range(1, 31)
         if dt.date(2025, 6, n).weekday() < 5]


def read(path):
    return json.loads((ROOT/path).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def module(name, path):
    sp = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(obj)
    return obj


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--local-only', action='store_true')
    args = ap.parse_args()
    review = module('june_review', ROOT/'tools/review_gate.py').require_review()
    retail = module('retail_gate', ROOT.parent/'retail-quality/retail_quality.py')
    retail.require_review(ROOT)
    verify = module('june_verify', ROOT/'tools/verify.py')
    manifest = read('checks/artifact_manifest.json')
    if manifest.get('dates') != DATES or not manifest.get('complete_month'):
        raise ValueError('Incomplete month artifact manifest')
    if [r['date'] for r in manifest['reports']] != DATES:
        raise ValueError('Report inventory mismatch')
    if set(manifest.get('collection', {})) != {'2025-06.html', 'methodology.txt', 'June_2025_Weekday_Reports.zip'}:
        raise ValueError('June collection, methodology and full report ZIP required')
    for row in manifest['reports']:
        d = row['date']
        fails, warns, sources, words = verify.verify(d)
        if fails or sources != row['distinct_sources'] or words != row['words']:
            raise ValueError(d+' report verification changed')
        if row.get('mobile_overflow') or row.get('layout', {}).get('headings') != 9:
            raise ValueError(d+' unchecked responsive layout')
        for key, path in [('spec_sha256', ROOT/'specs'/f'{d}.json'),
                          ('feed_sha256', ROOT/'feeds'/f'{d}.json.gz'),
                          ('card_sha256', ROOT/'cards'/f'{d}.json'),
                          ('timing_exceptions_sha256', ROOT/'audit/canonical_source_exceptions.json'),
                          ('renderer_sha256', ROOT/'tools/render.py'),
                          ('builder_sha256', ROOT/'tools/build_artifacts.py')]:
            if row[key] != sha(path):
                raise ValueError(d+' artifact input changed: '+key)
        if set(row['files']) != {'html', 'pdf', 'json'}:
            raise ValueError(d+' incomplete format set')
        for artifact in row['files'].values():
            path = ROOT/artifact['path']
            if sha(path) != artifact['sha256'] or path.stat().st_size != artifact['bytes']:
                raise ValueError('Artifact modified: '+str(path))
    for artifact in manifest['collection'].values():
        path = ROOT/artifact['path']
        if sha(path) != artifact['sha256'] or path.stat().st_size != artifact['bytes']:
            raise ValueError('Collection modified: '+str(path))
    frozen = manifest['frozen_source_archive']
    if (frozen.get('key') != 'reports/2025-06/June_2025_Frozen_News_Feeds.zip'
            or frozen.get('dates') != len(DATES)
            or (ROOT/frozen['path']).stat().st_size != frozen['bytes']
            or sha(ROOT/frozen['path']) != frozen['sha256']):
        raise ValueError('Frozen source archive changed')
    publication = None
    delivery = None
    source_delivery = None
    if not args.local_only:
        publication = read('checks/publication.json')
        delivery = read('checks/live_verification.json')
        source_delivery = read('checks/source_archive_publication.json')
        expected = len(DATES)*3+3
        expected_targets = {}
        for row in manifest['reports']:
            d = row['date']
            for ext, artifact in row['files'].items():
                key = {'html': f'reports/archive/{d}.html',
                       'json': f'Strategies/json/{d}_Market_Intelligence.json',
                       'pdf': f'Strategies/{d}_Market_Intelligence.pdf'}[ext]
                expected_targets[key] = (artifact['sha256'], artifact['bytes'])
        for name, artifact in manifest['collection'].items():
            key = 'reports/'+name if name.endswith('.html') else 'reports/2025-06/'+name
            expected_targets[key] = (artifact['sha256'], artifact['bytes'])
        actual_targets = {x['key']: (x['sha256'], x['bytes']) for x in publication.get('targets', [])}
        confirmations = publication.get('confirmed_targets', {})
        if (publication.get('dates') != DATES or actual_targets != expected_targets
                or set(confirmations) != set(expected_targets)):
            raise ValueError('Origin publication does not bind this exact artifact manifest')
        for key, identity in expected_targets.items():
            proof = confirmations[key]
            if ((proof.get('sha256'), proof.get('bytes')) != identity
                    or not proof.get('etag') or not proof.get('sha_verified_at_utc')):
                raise ValueError('Missing exact origin SHA proof: '+key)
        if (publication.get('stage') != 'published'
                or publication.get('confirmed_count') != expected
                or len(publication.get('targets', [])) != expected
                or publication.get('latest_write_performed') is not False
                or publication.get('weekends_unchanged') is not True):
            raise ValueError('Complete origin publication/preservation proof required')
        if (delivery.get('passed') is not True or delivery.get('index_link_count') != len(DATES)
                or delivery.get('artifact_count') != len(DATES)+3):
            raise ValueError('Complete public delivery proof required')
        public_expected = {k: v for k, v in expected_targets.items() if k.startswith('reports/')}
        public_rows = delivery.get('artifacts', [])
        public_actual = {x['key']: (x['sha256'], x['bytes']) for x in public_rows}
        if (public_actual != public_expected or len(public_rows) != len(public_expected)
                or any(x.get('passed') is not True or x.get('status') != 200 for x in public_rows)
                or delivery.get('stored_artifacts_verified') != expected):
            raise ValueError('Public delivery proof does not bind this exact artifact manifest')
        if (source_delivery.get('published') is not True
                or source_delivery.get('origin_and_public_sha_verified') is not True
                or source_delivery.get('sha256') != frozen['sha256']
                or source_delivery.get('bytes') != frozen['bytes']
                or source_delivery.get('key') != frozen['key']):
            raise ValueError('Frozen-source delivery proof required')
    report = {'status': 'published_verified' if publication else 'local_complete_verified',
              'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'report_count': len(DATES), 'dates': DATES,
              'total_words': sum(x['words'] for x in manifest['reports']),
              'total_pdf_pages': sum(x['pdf_pages'] for x in manifest['reports']),
              'citations_per_report': {x['date']: x['distinct_sources'] for x in manifest['reports']},
              'artifact_manifest_sha256': sha(ROOT/'checks/artifact_manifest.json'),
              'review_receipts': review,
              'retail_review_sha256': sha(ROOT/'checks/retail_quality.json'),
              'frozen_source_sha256': frozen['sha256'],
              'origin_artifacts_verified': publication.get('confirmed_count') if publication else 0,
              'public_report_artifacts_verified': delivery.get('artifact_count') if delivery else 0,
              'source_archive_publicly_verified': bool(source_delivery),
              'latest_write_performed': publication.get('latest_write_performed') if publication else False,
              'latest_unchanged_at_publication_check': publication.get('latest_unchanged') if publication else None,
              'weekends_unchanged_at_publication_check': publication.get('weekends_unchanged') if publication else None,
              'limits': ['Canonical URL dates and RSS timestamps do not prove original publisher article-body vintages.',
                         'Independent factual review covers the selected clauses listed in its receipt, not all prose.',
                         'Historical quotes are current-vintage vendor data; displayed share units reverse later splits.']}
    (ROOT/'checks/final_validation.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({k: report[k] for k in ['status', 'report_count', 'total_words', 'total_pdf_pages',
                                          'origin_artifacts_verified', 'public_report_artifacts_verified']}, indent=2))


if __name__ == '__main__':
    main()
