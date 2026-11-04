"""Publish reviewed October 2024 editions; dry-run unless --go.

Creates scoped historical objects only, preserves latest/live reports, backs up
the archive index, uses conditional writes and verifies complete object bodies.
No Lambda invocation, code deployment, email or Telegram.
"""
from pathlib import Path
import argparse
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
DATES = [dt.date(2024, 10, n).isoformat() for n in range(1, 32)
         if dt.date(2024, 10, n).weekday() < 5]
RECEIPT = ROOT / 'checks/publication.json'


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


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


def plan():
    validator = module('oct_verify', ROOT / 'tools/verify.py')
    retail = module('oct_retail_gate', ROOT.parent / 'retail-quality/retail_quality.py')
    retail.require_review(ROOT)
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
            or frozen.get('status') != 'all_23_ready'
            or sources.get('source_freeze_sha256') != sha((ROOT/'audit/source_freeze.json').read_bytes())):
        raise ValueError('Frozen source acceptance missing or changed')
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
        if precision.get(field) != sha((ROOT/'audit'/name).read_bytes()):
            raise ValueError('Acceptance or release exclusions changed after final review: ' + name)
    manifest = json.loads((ROOT / 'checks/artifact_manifest.json').read_text())
    if manifest.get('dates') != DATES or not manifest.get('complete_month'):
        raise ValueError('Complete 23-date month required')
    if [x['date'] for x in manifest.get('reports', [])] != DATES:
        raise ValueError('Missing or duplicated reports')
    reviews = json.loads((ROOT / 'audit/final_editorial_review.json').read_text())
    if reviews.get('dates') != DATES or reviews.get('fatal_or_major_remaining') != 0:
        raise ValueError('Complete independent editorial review required')
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
        if not re.fullmatch(r'(2024-10\.html|October_2024_(Weekday_Reports|Frozen_Sources)\.zip|methodology\.txt|What_Retail_Is_Playing_2024-10\.html)', name):
            raise ValueError('Unexpected collection artifact: ' + name)
        key = 'reports/' + name if name == '2024-10.html' else 'reports/2024-10/' + name
        ctype = ('text/html; charset=utf-8' if name.endswith('.html') else
                 'application/zip' if name.endswith('.zip') else 'text/plain; charset=utf-8')
        targets.append(dict(artifact, key=key, content_type=ctype))
    if len(targets) != 74 or len({x['key'] for x in targets}) != 74:
        raise ValueError('Expected 69 daily files and five collection files')
    for item in targets:
        path = (ROOT / item['path']).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ValueError('Artifact path out of scope')
        blob = path.read_bytes()
        if len(blob) != item['bytes'] or sha(blob) != item['sha256']:
            raise ValueError('Artifact changed: ' + str(path))
        if '2024-10' not in item['key'] and item['key'] != 'reports/2024-10/methodology.txt':
            raise ValueError('Target outside October 2024')
    return targets, sha((ROOT/'checks/artifact_manifest.json').read_bytes())


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
    dates = [dt.date(2024, 10, n).isoformat() for n in range(1,32)
             if dt.date(2024,10,n).weekday() > 4]
    return ['reports/latest.html','reports/2024-11.html','reports/2024-11/What_Retail_Is_Playing_2024-11.html'] + [f'reports/archive/2026-08-{n:02}.html' for n in range(1,32)] + [f'reports/archive/2024-11-{n:02}.html' for n in range(1,31) if dt.date(2024,11,n).weekday()<5] + [
        key for date in dates for key in (f'reports/archive/{date}.html',
        f'Strategies/json/{date}_Market_Intelligence.json', f'Strategies/{date}_Market_Intelligence.pdf')]


def snapshot(s3):
    out = {}
    for key in protected_keys():
        obj = read(s3, key)
        out[key] = None if obj is None else {k: obj[k] for k in ('etag','sha256','bytes')}
    return out


def merge_index(blob):
    soup = BeautifulSoup(blob, 'html.parser')
    ul = soup.find('ul')
    if ul is None:
        raise ValueError('Archive list missing')
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
    for href, label in [('2024-10.html','October 2024 — 23 weekday briefings & download'),
        ('2024-10/What_Retail_Is_Playing_2024-10.html','October 2024 — What Retail Is Playing')]:
        if not soup.find('a', href=href):
            p = soup.new_tag('p')
            a = soup.new_tag('a', href=href)
            a.string = label
            p.append(a)
            ul.insert_before(p)
    if not old <= {a.get('href') for a in soup.find_all('a')}:
        raise ValueError('Merge would remove archive links')
    for date in DATES:
        if len(soup.find_all('a', href=f'archive/{date}.html')) != 1:
            raise ValueError('Missing/duplicate archive date: ' + date)
    return str(soup).encode()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--go', action='store_true')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    targets, manifest_hash = plan()
    session = boto3.Session(aws_access_key_id=os.environ['AWS_KEY'],
        aws_secret_access_key=os.environ['AWS_SECRET'], region_name='eu-north-1')
    config = Config(connect_timeout=8, read_timeout=30,
                    retries={'mode':'standard','total_max_attempts':3})
    s3 = session.client('s3', config=config)
    if args.resume:
        receipt = json.loads(RECEIPT.read_text())
        if receipt['targets'] != targets or receipt['manifest_sha256'] != manifest_hash:
            raise ValueError('Resume requires original reviewed artifacts')
        if receipt['protected_before'] != snapshot(s3):
            raise ValueError('Protected content changed; inspect before resuming')
    else:
        if RECEIPT.exists():
            raise ValueError('Existing run receipt: use --resume')
        for item in targets:
            if read(s3, item['key']) is not None:
                raise ValueError('Refusing to overwrite existing target: ' + item['key'])
        receipt = {'run':dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
            'dates':DATES,'targets':targets,'manifest_sha256':manifest_hash,
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
    save(RECEIPT, receipt)
    if 'index_backup' not in receipt:
        key = f'reports/_retrospective_backup/oct-2024-weekdays/{receipt["run"]}/reports/index.html'
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
            'Paths':{'Quantity':3,'Items':['/reports/*','/Strategies/json/2024-10-*','/Strategies/2024-10-*']},
            'CallerReference':str(uuid.uuid4())})['Invalidation']
        receipt['invalidation']={'id':result['Id'],'status':result['Status']}
    receipt['stage']='origin_verified'
    receipt['finished_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
    save(RECEIPT,receipt)
    print('All scoped origin bodies verified; index merged; cache invalidation submitted.',flush=True)


if __name__ == '__main__':
    main()
