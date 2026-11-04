"""Preserve historical links after a concurrent live index refresh.

Plans by default. --go requires the independently reviewed plan and exact
current ETag, backs up that body, and conditionally writes the merged index.
No report body, latest object, Lambda or configuration is changed.
"""
from pathlib import Path
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import uuid

import boto3
from botocore.config import Config
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / 'checks/index_reconciliation_plan.json'
REVIEW = ROOT / 'audit/independent_index_reconciliation_review.json'
RECEIPT = ROOT / 'checks/index_reconciliation.json'


def sha(body):
    return hashlib.sha256(body).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False))


def read(s3, key):
    obj = s3.get_object(Bucket='s3bucketmz', Key=key)
    try:
        body = obj['Body'].read()
    finally:
        obj['Body'].close()
    return body, {'key': key, 'etag': obj['ETag'], 'sha256': sha(body),
                  'bytes': len(body), 'last_modified': obj['LastModified'].isoformat()}


def hrefs(body):
    return {a.get('href') for a in BeautifulSoup(body, 'html.parser').find_all('a')}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--go', action='store_true')
    args = parser.parse_args()
    session = boto3.Session(aws_access_key_id=os.environ['AWS_KEY'],
        aws_secret_access_key=os.environ['AWS_SECRET'], region_name='eu-north-1')
    config = Config(connect_timeout=8, read_timeout=30,
                    retries={'total_max_attempts': 3})
    s3 = session.client('s3', config=config)
    publication = json.loads((ROOT / 'checks/publication.json').read_text())
    if args.go:
        plan = json.loads(PLAN.read_text())
        review = json.loads(REVIEW.read_text())
        if (review.get('passed') is not True
                or review.get('plan_sha256') != sha(PLAN.read_bytes())
                or review.get('script_sha256') != sha(Path(__file__).read_bytes())):
            raise ValueError('Exact independent plan/script acceptance required')
        current, metadata = read(s3, 'reports/index.html')
        if metadata != plan['current']:
            raise ValueError('Index changed after planning; replan and review')
        merged = (ROOT / 'work/index_reconciled.html').read_bytes()
        if sha(merged) != plan['merged_sha256']:
            raise ValueError('Reviewed merged index changed')
        key = ('reports/_retrospective_backup/aug-2024-weekdays/'
               + publication['run'] + '/index_after_external_update.html')
        s3.put_object(Bucket='s3bucketmz', Key=key, Body=current,
                      ContentType='text/html; charset=utf-8', IfNoneMatch='*')
        _, backup = read(s3, key)
        if backup['sha256'] != metadata['sha256']:
            raise ValueError('Concurrent index backup failed')
        s3.put_object(Bucket='s3bucketmz', Key='reports/index.html', Body=merged,
                      ContentType='text/html; charset=utf-8', IfMatch=metadata['etag'])
        body, after = read(s3, 'reports/index.html')
        if (after['sha256'] != plan['merged_sha256']
                or not set(plan['prior_hrefs']) <= hrefs(body)
                or not set(plan['current_hrefs']) <= hrefs(body)
                or not set(plan['expected_august_hrefs']) <= hrefs(body)):
            raise ValueError('Merged index verification failed')
        invalidation = session.client('cloudfront', config=config).create_invalidation(
            DistributionId='E15IJW4438D21G', InvalidationBatch={
                'Paths': {'Quantity': 1, 'Items': ['/reports/index.html']},
                'CallerReference': str(uuid.uuid4())})['Invalidation']
        save(RECEIPT, {'passed': True, 'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
            'plan_sha256': sha(PLAN.read_bytes()), 'review_sha256': sha(REVIEW.read_bytes()),
            'script_sha256': sha(Path(__file__).read_bytes()), 'before': metadata,
            'backup': backup, 'after': after, 'restored_hrefs': plan['restored_hrefs'],
            'all_prior_and_concurrent_hrefs_preserved': True,
            'conditional_etag_write': True, 'report_or_latest_writes': False,
            'invalidation': {'id': invalidation['Id'], 'status': invalidation['Status']}})
        print('Reconciled index verified; all prior and concurrent links preserved.')
        return
    current, metadata = read(s3, 'reports/index.html')
    prior, backup = read(s3, publication['index_backup']['key'])
    if backup['sha256'] != publication['index_backup']['sha256']:
        raise ValueError('Original archive backup changed')
    soup = BeautifulSoup(current, 'html.parser')
    ul = soup.find('ul')
    if ul is None:
        raise ValueError('Archive list missing')
    prior_hrefs, current_hrefs = hrefs(prior), hrefs(current)
    missing = prior_hrefs - current_hrefs
    allowed = {f'{ym}{suffix}' for ym in ('2024-09', '2024-10', '2024-11')
               for suffix in ('.html', '/What_Retail_Is_Playing_' + ym + '.html')}
    if not missing or not missing <= allowed:
        raise ValueError('Unexpected or absent reconciliation scope')
    old_soup = BeautifulSoup(prior, 'html.parser')
    august_labels = {
        '2024-08.html': 'August 2024 — 22 weekday briefings & download',
        '2024-08/What_Retail_Is_Playing_2024-08.html': 'August 2024 — What Retail Is Playing'}
    restored = missing | (set(august_labels) - current_hrefs)
    for href in sorted(restored):
        p = soup.new_tag('p')
        a = soup.new_tag('a', href=href)
        a.string = (august_labels[href] if href in august_labels else
                    old_soup.find('a', href=href).get_text(' ', strip=True))
        p.append(a)
        ul.insert_before(p)
    merged = str(soup).encode()
    if not (prior_hrefs | current_hrefs | set(august_labels)) <= hrefs(merged):
        raise ValueError('Reconciliation would lose a link')
    for date in publication['dates']:
        if len(soup.find_all('a', href=f'archive/{date}.html')) != 1:
            raise ValueError('August date link missing or duplicated')
    (ROOT / 'work/index_reconciled.html').write_bytes(merged)
    save(PLAN, {'created_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'publication_sha256': sha((ROOT / 'checks/publication.json').read_bytes()),
        'current': metadata, 'original_backup': backup,
        'missing_prior_hrefs': sorted(missing),
        'restored_hrefs': sorted(restored), 'expected_august_hrefs': sorted(august_labels),
        'prior_hrefs': sorted(prior_hrefs), 'current_hrefs': sorted(current_hrefs),
        'merged_sha256': sha(merged), 'merged_bytes': len(merged),
        'all_prior_and_current_hrefs_preserved': True,
        'conditional_etag_write': True, 'scope': 'Restore month/retail navigation links for August–November 2024; preserve every concurrent link.'})
    print('Plan saved:', len(restored), 'historical links; no writes.')


if __name__ == '__main__':
    main()
