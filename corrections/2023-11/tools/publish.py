"""Publish reviewed April 2024 editions; dry-run unless --go.

Creates scoped historical objects only, preserves latest/live reports, backs up
the archive index, uses conditional writes and verifies complete object bodies.
No Lambda invocation, code deployment, email or Telegram.
"""
from pathlib import Path
import argparse
import base64
import concurrent.futures as futures
import datetime as dt
import hashlib
import importlib.util
import json
import os
import re
import uuid

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
BUCKET = 's3bucketmz'
DIST = 'E15IJW4438D21G'
DATES = [dt.date(2024, 4, n).isoformat() for n in range(1, 31)
         if dt.date(2024, 4, n).weekday() < 5]
RECEIPT = ROOT / 'checks/publication.json'
PUBLICATION_REVIEW = 'checks/publication_engineering_review.json'


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def nonretail_sha(spec):
    component = {key: value for key, value in spec.items()
                 if key not in {'retail', 'retail_intro'}}
    return sha(json.dumps(component, sort_keys=True, ensure_ascii=False,
                          separators=(',', ':')).encode())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False))
    temp.replace(path)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def require_artifact_review(review, manifest_hash, tool_bindings):
    """Require the full current runtime audit, never a static-only receipt."""
    if (review.get('status') != 'accepted'
            or review.get('runtime_artifacts_reviewed') is not True
            or type(review.get('fatal_or_major_remaining')) is not int
            or review['fatal_or_major_remaining'] != 0
            or review.get('dates') != DATES
            or [row.get('date') for row in review.get('reports', [])] != DATES
            or review.get('artifact_manifest_sha256') != manifest_hash
            or review.get('tool_sha256') != tool_bindings):
        raise ValueError('Complete current runtime artifact audit required')


def deployment_baseline(source=None):
    """Validate original read-only metadata and bind its exact retained bytes."""
    if source is None:
        source = json.loads((ROOT/'audit/independent_source_review.json').read_bytes())
    policy = module('april_source_inventory', ROOT/'tools/build_source_inventory.py')
    proof = policy.require_code_provenance(source)
    provenance = json.loads((ROOT/'code_provenance.json').read_bytes())
    metadata = provenance.get('deployment_metadata_read_only', {})
    fields = ('CodeSha256', 'LastModified', 'Runtime')
    if any(not isinstance(metadata.get(key), str) or not metadata[key].strip() for key in fields):
        raise ValueError('Complete original read-only Lambda metadata required')
    try:
        digest = base64.b64decode(metadata['CodeSha256'], validate=True)
        modified = dt.datetime.fromisoformat(metadata['LastModified'].replace('Z', '+00:00'))
    except (ValueError, TypeError) as error:
        raise ValueError('Invalid original read-only Lambda metadata') from error
    if len(digest) != 32 or modified.utcoffset() is None:
        raise ValueError('Invalid original Lambda package digest or modification clock')
    return {'code_provenance_sha256': proof['code_provenance_sha256'],
        'retained_source_sha256': proof['source_sha256'],
        'lambda_metadata': {key: metadata[key] for key in fields}}


def require_publication_engineering_review():
    raw = (ROOT/PUBLICATION_REVIEW).read_bytes()
    review = json.loads(raw)
    expected = {name: sha((ROOT/'tools'/name).read_bytes())
                for name in ('publish.py', 'verify_delivery.py')}
    if (review.get('status') != 'accepted' or review.get('passed') is not True
            or type(review.get('fatal_or_major_remaining')) is not int
            or review['fatal_or_major_remaining'] != 0
            or review.get('tool_sha256') != expected):
        raise ValueError('Current independent publication engineering review required')
    return sha(raw)


def plan():
    require_publication_engineering_review()
    validator = module('sep_verify', ROOT / 'tools/verify.py')
    retail = module('sep_retail_gate', ROOT.parent / 'retail-quality/retail_quality.py')
    retail.require_review(ROOT)
    local_retail = module('april_retail_gate', ROOT / 'tools/retail_quality_snapshot.py')
    local_retail.require_review(ROOT)
    sources = json.loads((ROOT/'audit/independent_source_review.json').read_text())
    source_rows = sources.get('dates', [])
    if not all(isinstance(row, dict) and 'date' in row for row in source_rows):
        raise ValueError('Expected per-date independent source acceptance rows')
    source_dates = [row['date'] for row in source_rows]
    accepted_feeds = {row['date']: row.get('feed_sha256') for row in source_rows}
    frozen = json.loads((ROOT/'audit/source_freeze.json').read_text())
    if (sources.get('status') != 'accepted_for_authoring_with_semantic_exclusions'
            or sources.get('passed') is not True
            or sources.get('infrastructure_status') != 'accepted'
            or source_dates != DATES
            or sources.get('errors') or sources.get('structural_errors')
            or sources.get('pending_dates')
            or frozen.get('status') != 'all_22_ready'
            or sources.get('source_freeze_sha256') != sha((ROOT/'audit/source_freeze.json').read_bytes())):
        raise ValueError('Frozen source acceptance missing or changed')
    deployment_baseline(sources)
    market = json.loads((ROOT/'audit/independent_market_review.json').read_text())
    if (market.get('status') != 'accepted' or market.get('passed') is not True
            or market.get('dates') != DATES or market.get('errors')
            or market.get('source_freeze_sha256') != sources['source_freeze_sha256']):
        raise ValueError('Independent market review has unresolved errors')
    for date in DATES:
        if accepted_feeds.get(date) != sha((ROOT/'feeds'/(date+'.json.gz')).read_bytes()):
            raise ValueError('Feed changed after independent source acceptance: ' + date)
        card_hash = sha((ROOT/'cards'/(date+'.json')).read_bytes())
        if any(review.get('card_sha256', {}).get(date) != card_hash
               for review in (sources, market)):
            raise ValueError('Card changed after independent acceptance: ' + date)
    precision = json.loads((ROOT/'audit/final_precision_review.json').read_text())
    if not precision.get('passed') or precision.get('dates') != DATES:
        raise ValueError('Final market/timing precision review required')
    for field, name in [('additional_release_exclusions_sha256', 'additional_release_exclusions.json'),
                        ('source_acceptance_sha256', 'independent_source_review.json'),
                        ('market_acceptance_sha256', 'independent_market_review.json')]:
        path = ROOT/'audit'/name
        actual = sha(path.read_bytes()) if path.is_file() else None
        if name != 'additional_release_exclusions.json' and actual is None:
            raise ValueError('Missing independent acceptance: ' + name)
        if precision.get(field) != actual:
            raise ValueError('Acceptance or release exclusions changed after final review: ' + name)
    manifest_path = ROOT/'checks/artifact_manifest.json'
    manifest_bytes = manifest_path.read_bytes()
    manifest_hash = sha(manifest_bytes)
    manifest = json.loads(manifest_bytes)
    artifact_review = json.loads((ROOT/'checks/final_artifact_review.json').read_text())
    tool_paths = {name: 'tools/'+name for name in
                  ['render.py', 'build_artifacts.py', 'build_retail_page.py', 'build_source_inventory.py']}
    tool_paths['audit_work/review_final_artifacts.py'] = 'audit_work/review_final_artifacts.py'
    require_artifact_review(artifact_review, manifest_hash,
                            {name: sha((ROOT/path).read_bytes()) for name, path in tool_paths.items()})
    if manifest.get('dates') != DATES or not manifest.get('complete_month'):
        raise ValueError('Complete 22-date month required')
    if [x['date'] for x in manifest.get('reports', [])] != DATES:
        raise ValueError('Missing or duplicated reports')
    reviews = json.loads((ROOT / 'audit/final_editorial_review.json').read_text())
    if reviews.get('dates') != DATES or reviews.get('fatal_or_major_remaining') != 0:
        raise ValueError('Complete independent editorial review required')
    if [row.get('date') for row in reviews.get('reports', [])] != DATES:
        raise ValueError('Missing or duplicated editorial review date')
    reviewed = {x['date']: x for x in reviews['reports']}
    targets = []
    for row in manifest['reports']:
        date = row['date']
        sp = ROOT / 'specs' / (date + '.json')
        if sha(sp.read_bytes()) != row['spec_sha256']:
            raise ValueError('Spec changed after artifact build: ' + date)
        if reviewed[date]['spec_sha256'] != row['spec_sha256']:
            raise ValueError('Spec changed after independent review: ' + date)
        if precision['spec_sha256'].get(date) != row['spec_sha256']:
            raise ValueError('Spec changed after precision review: ' + date)
        component_paths = {
            'nonretail_review_sha256': ROOT/'audit'/('independent_nonretail_'+date+'.json'),
            'retail_review_sha256': ROOT/'audit'/('independent_retail_'+date+'.json'),
            'retail_draft_sha256': ROOT/'retail_drafts'/(date+'.json'),
            'exclusions_sha256': ROOT/'exclusions'/(date+'.json'),
        }
        for field, path in component_paths.items():
            if reviewed[date].get(field) != sha(path.read_bytes()):
                raise ValueError('Component changed after final editorial binding: ' + date + ' ' + field)
        spec_data = json.loads(sp.read_text())
        nr = json.loads(component_paths['nonretail_review_sha256'].read_text())
        rr = json.loads(component_paths['retail_review_sha256'].read_text())
        draft = json.loads(component_paths['retail_draft_sha256'].read_text())
        component_hash = nonretail_sha(spec_data)
        if any(record.get('nonretail_content_sha256') != component_hash
               for record in (reviewed[date], nr)):
            raise ValueError('Nonretail component differs from independent review: ' + date)
        if rr.get('retail_draft_sha256') != reviewed[date]['retail_draft_sha256']:
            raise ValueError('Retail draft differs from independent review: ' + date)
        if draft.get('date') != date or any(spec_data.get(key) != draft.get(key)
                                           for key in ('retail', 'retail_intro')):
            raise ValueError('Independently reviewed retail is not merged: ' + date)
        for record in (nr, rr):
            if (record.get('date') != date
                    or record.get('status') not in {'accepted', 'passed'}
                    or type(record.get('fatal_or_major_remaining')) is not int
                    or record['fatal_or_major_remaining'] != 0):
                raise ValueError('Current independent component review is unresolved: ' + date)
            for field, path in [('feed_sha256', ROOT/'feeds'/(date+'.json.gz')),
                                ('card_sha256', ROOT/'cards'/(date+'.json')),
                                ('exclusions_sha256', ROOT/'exclusions'/(date+'.json'))]:
                if record.get(field) != sha(path.read_bytes()):
                    raise ValueError('Independent review source changed: ' + date + ' ' + field)
        for field, path in [('feed_sha256', ROOT/'feeds'/(date+'.json.gz')),
                            ('card_sha256', ROOT/'cards'/(date+'.json'))]:
            if sha(path.read_bytes()) != row[field]:
                raise ValueError('Frozen source changed: ' + date)
        fails, *_ = validator.verify(date)
        if fails:
            raise ValueError('Validation fails: ' + date + ' ' + repr(fails))
        if set(row['files']) != {'html', 'json', 'pdf'}:
            raise ValueError('Each report needs HTML/JSON/PDF: ' + date)
        for ext, artifact in row['files'].items():
            key = {'html': f'reports/archive/{date}.html',
                   'json': f'Strategies/json/{date}_Market_Intelligence.json',
                   'pdf': f'Strategies/{date}_Market_Intelligence.pdf'}[ext]
            ctype = {'html': 'text/html; charset=utf-8', 'json': 'application/json',
                     'pdf': 'application/pdf'}[ext]
            targets.append(dict(artifact, key=key, content_type=ctype))
    for name, artifact in manifest['collection'].items():
        if not re.fullmatch(r'(2024-04\.html|April_2024_(Weekday_Reports|Frozen_Sources)\.zip|methodology\.txt|What_Retail_Is_Playing_2024-04\.html)', name):
            raise ValueError('Unexpected collection artifact: ' + name)
        key = 'reports/' + name if name == '2024-04.html' else 'reports/2024-04/' + name
        ctype = ('text/html; charset=utf-8' if name.endswith('.html') else
                 'application/zip' if name.endswith('.zip') else 'text/plain; charset=utf-8')
        targets.append(dict(artifact, key=key, content_type=ctype))
    if len(targets) != len(DATES)*3+5 or len({x['key'] for x in targets}) != len(DATES)*3+5:
        raise ValueError('Expected 66 daily files and five collection files')
    for item in targets:
        path = (ROOT / item['path']).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ValueError('Artifact path out of scope')
        blob = path.read_bytes()
        if len(blob) != item['bytes'] or sha(blob) != item['sha256']:
            raise ValueError('Artifact changed: ' + str(path))
        if '2024-04' not in item['key'] and item['key'] != 'reports/2024-04/methodology.txt':
            raise ValueError('Target outside April 2024')
    if sha(manifest_path.read_bytes()) != manifest_hash:
        raise ValueError('Artifact manifest changed during publication planning')
    return targets, manifest_hash


def read(s3, key):
    try:
        result = s3.get_object(Bucket=BUCKET, Key=key)
    except ClientError as error:
        if error.response['Error']['Code'] in ('404', 'NoSuchKey', 'NotFound'):
            return None
        raise
    try:
        blob = result['Body'].read()
    finally:
        result['Body'].close()
    return {'body': blob, 'etag': result['ETag'], 'sha256': sha(blob), 'bytes': len(blob)}


def protected_keys():
    weekends = [dt.date(2024, 4, n).isoformat() for n in range(1, 31)
                if dt.date(2024, 4, n).weekday() > 4]
    existing = ['reports/latest.html']
    for month, last in [(6, 30), (7, 31), (8, 31), (9, 30), (10, 31), (11, 30)]:
        ym = f'2024-{month:02}'
        existing += [f'reports/{ym}.html',
                     f'reports/{ym}/What_Retail_Is_Playing_{ym}.html']
        existing += [f'reports/archive/{ym}-{n:02}.html' for n in range(1,last+1)
                     if dt.date(2024,month,n).weekday() < 5]
    existing += [f'reports/archive/2026-08-{n:02}.html' for n in range(1,32)]
    existing += [key for date in weekends for key in
                 (f'reports/archive/{date}.html',
                  f'Strategies/json/{date}_Market_Intelligence.json',
                  f'Strategies/{date}_Market_Intelligence.pdf')]
    return existing


def snapshot(s3):
    """Read independent protected objects concurrently; propagate any failure."""
    def capture(key):
        obj = read(s3, key)
        return key, None if obj is None else {k: obj[k] for k in ('etag', 'sha256', 'bytes')}
    keys = protected_keys()
    with futures.ThreadPoolExecutor(max_workers=8) as pool:
        return dict(pool.map(capture, keys))


def merge_index(blob):
    soup = BeautifulSoup(blob, 'html.parser')
    candidates = []
    for candidate in soup.find_all('ul'):
        for li in candidate.find_all('li', recursive=False):
            if any(re.fullmatch(r'archive/\d{4}-\d{2}-\d{2}\.html', anchor.get('href', ''))
                   and anchor.find_parent('ul') is candidate for anchor in li.find_all('a')):
                candidates.append(candidate)
                break
    if len(candidates) != 1:
        raise ValueError('A single unambiguous daily archive list is required')
    ul = candidates[0]
    old = {a.get('href') for a in soup.find_all('a')}
    for date in DATES:
        href = f'archive/{date}.html'
        if href not in old:
            li = soup.new_tag('li')
            a = soup.new_tag('a', href=href)
            a.string = date
            li.append(a)
            ul.append(li)
    rows = []
    for li in ul.find_all('li', recursive=False):
        a = li.find('a')
        m = re.fullmatch(r'archive/(\d{4}-\d{2}-\d{2})\.html', a.get('href','')) if a else None
        if m:
            rows.append((m.group(1), li))
    for _, li in sorted(rows, reverse=True):
        li.extract()
        ul.append(li)
    for href, label in [('2024-04.html','April 2024 — 22 weekday briefings & download'),
        ('2024-04/What_Retail_Is_Playing_2024-04.html','April 2024 — What Retail Is Playing')]:
        if not soup.find('a', href=href):
            p = soup.new_tag('p')
            a = soup.new_tag('a', href=href)
            a.string = label
            p.append(a)
            ul.insert_before(p)
    if not old <= {a.get('href') for a in soup.find_all('a')}:
        raise ValueError('Merge would remove archive links')
    for date in DATES:
        if (len(soup.find_all('a', href=f'archive/{date}.html')) != 1
                or len(ul.find_all('a', href=f'archive/{date}.html')) != 1):
            raise ValueError('Missing/duplicate archive date: ' + date)
    return str(soup).encode()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--go', action='store_true')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    targets, manifest_hash = plan()
    baseline = deployment_baseline()
    publication_review_sha256 = require_publication_engineering_review()
    session = boto3.Session(aws_access_key_id=os.environ['AWS_KEY'],
        aws_secret_access_key=os.environ['AWS_SECRET'], region_name='eu-north-1')
    config = Config(connect_timeout=8, read_timeout=30,
                    retries={'mode':'standard','total_max_attempts':3},max_pool_connections=12)
    s3 = session.client('s3', config=config)
    if args.resume:
        receipt = json.loads(RECEIPT.read_text())
        if receipt['targets'] != targets or receipt['manifest_sha256'] != manifest_hash:
            raise ValueError('Resume requires original reviewed artifacts')
        if receipt.get('deployment_baseline') != baseline:
            raise ValueError('Resume requires original source-provenance metadata bytes')
        if receipt.get('publication_engineering_review_sha256') != publication_review_sha256:
            raise ValueError('Resume requires original publication engineering review')
        if receipt['protected_before'] != snapshot(s3):
            raise ValueError('Protected content changed; inspect before resuming')
    else:
        if RECEIPT.exists():
            raise ValueError('Existing run receipt: use --resume')
        # Independent reads may overlap; all writes below remain sequential.
        with futures.ThreadPoolExecutor(max_workers=8) as pool:
            present = list(pool.map(lambda item: read(s3, item['key']) is not None, targets))
        for item, exists in zip(targets, present):
            if exists:
                raise ValueError('Refusing to overwrite existing target: ' + item['key'])
        receipt = {'run':dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
            'dates':DATES,'targets':targets,'manifest_sha256':manifest_hash,
            'deployment_baseline':baseline,
            'publication_engineering_review_sha256':publication_review_sha256,
            'protected_before':snapshot(s3),'confirmed':{},'stage':'planned',
            'latest_write_performed':False,'lambda_write_performed':False}
    idx = read(s3,'reports/index.html')
    if idx is None:
        raise ValueError('Archive index missing')
    merged = merge_index(idx['body'])
    print('Reviewed plan:',len(targets),'artifacts; index links preserved; protected snapshot checked',flush=True)
    if not args.go:
        print('Dry run complete. No writes.',flush=True)
        return
    if deployment_baseline() != baseline:
        raise ValueError('Source-provenance metadata changed during publication planning')
    if require_publication_engineering_review() != publication_review_sha256:
        raise ValueError('Publication engineering review changed during planning')
    save(RECEIPT, receipt)
    if 'index_backup' not in receipt:
        key = f'reports/_retrospective_backup/apr-2024-weekdays/{receipt["run"]}/reports/index.html'
        s3.put_object(Bucket=BUCKET, Key=key, Body=idx['body'], ContentType='text/html; charset=utf-8',IfNoneMatch='*')
        if read(s3,key)['sha256'] != idx['sha256']:
            raise ValueError('Index backup verification failed')
        receipt['index_backup']={'key':key,'sha256':idx['sha256'],'etag':idx['etag']}
        save(RECEIPT,receipt)
    receipt['stage']='upload'
    save(RECEIPT,receipt)
    for item in targets:
        key = item['key']
        current = read(s3,key)
        if current is None:
            blob = (ROOT/item['path']).read_bytes()
            if sha(blob) != item['sha256'] or len(blob) != item['bytes']:
                raise ValueError('Artifact changed before upload: ' + item['path'])
            s3.put_object(Bucket=BUCKET,Key=key,Body=blob,ContentType=item['content_type'],IfNoneMatch='*')
            current = read(s3,key)
        if current['sha256'] != item['sha256'] or current['bytes'] != item['bytes']:
            raise ValueError('Unexpected object version: '+key)
        receipt['confirmed'][key]={k:current[k] for k in ('etag','sha256','bytes')}
        save(RECEIPT,receipt)
    idx = read(s3,'reports/index.html')
    merged = merge_index(idx['body'])
    s3.put_object(Bucket=BUCKET,Key='reports/index.html',Body=merged,
                  ContentType='text/html; charset=utf-8',IfMatch=idx['etag'])
    if read(s3,'reports/index.html')['sha256'] != sha(merged):
        raise ValueError('Index body verification failed')
    receipt['index_sha256']=sha(merged)
    receipt['protected_after']=snapshot(s3)
    if receipt['protected_before'] != receipt['protected_after']:
        raise ValueError('Protected object preservation failed')
    save(RECEIPT,receipt)
    if 'invalidation' not in receipt:
        cf = session.client('cloudfront',config=config)
        result = cf.create_invalidation(DistributionId=DIST,InvalidationBatch={
            'Paths':{'Quantity':5,'Items':['/reports/index.html','/reports/archive/2024-04-*','/reports/2024-04*','/Strategies/json/2024-04-*','/Strategies/2024-04-*']},
            'CallerReference':str(uuid.uuid4())})['Invalidation']
        receipt['invalidation']={'id':result['Id'],'status':result['Status']}
    receipt['stage']='origin_verified'
    receipt['finished_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
    save(RECEIPT,receipt)
    print('All scoped origin bodies verified; index merged; cache invalidation submitted.',flush=True)


if __name__ == '__main__':
    main()
