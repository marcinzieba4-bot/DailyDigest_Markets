"""Publish only reviewed retail revisions. Dry run by default; resumable backups.

Input: audit/revision_artifacts.json produced by the local artifact builder.
No index, latest-report, Lambda, email or Telegram writes are performed.
"""
from pathlib import Path
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import time
import urllib.request
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parent
BUCKET = 's3bucketmz'
DIST = 'E15IJW4438D21G'
PUBLIC = 'https://d7g7nkeytae81.cloudfront.net/'
RECEIPT = ROOT/'audit/publication.json'
COLLECTIONS = {
    '2025-09': 'September_2025_Weekday_Reports.zip',
    '2025-10': 'October_2025_Weekday_Reports.zip',
    '2025-11': 'November_2025_Weekday_Reports.zip',
}


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def save(path, value):
    p = path.with_suffix('.tmp')
    p.write_text(json.dumps(value, indent=2))
    p.replace(path)


def request(fn):
    for attempt in range(6):
        try:
            return fn()
        except Exception as error:
            if isinstance(error, ClientError):
                status = error.response.get('ResponseMetadata', {}).get('HTTPStatusCode')
                if status not in (408, 429, 500, 502, 503, 504):
                    raise
            elif type(error).__name__ not in ('EndpointConnectionError', 'ProxyConnectionError',
                    'ConnectTimeoutError', 'ReadTimeoutError', 'ResponseStreamingError',
                    'IncompleteReadError', 'ConnectionClosedError', 'SSLError', 'URLError',
                    'TimeoutError'):
                raise
            if attempt == 5:
                raise
            time.sleep(min(2**attempt, 12))


def read(s3, key):
    def one():
        x = s3.get_object(Bucket=BUCKET, Key=key)
        try:
            blob = x['Body'].read()
        finally:
            x['Body'].close()
        return {'etag': x['ETag'], 'bytes': len(blob), 'sha256': sha(blob)}, blob
    return request(one)


def maybe_read(s3, key):
    try:
        return read(s3, key)
    except ClientError as error:
        if error.response.get('Error', {}).get('Code') in ('404', 'NoSuchKey', 'NotFound'):
            return None, None
        raise


def plan():
    manifest = json.loads((ROOT/'audit/revision_artifacts.json').read_text())
    if not manifest.get('reviewed'):
        raise ValueError('Completed editorial review is required')
    if not manifest.get('reviewed_inputs'):
        raise ValueError('Reviewed input hashes are required')
    for relative,expected in manifest['reviewed_inputs'].items():
        p=(ROOT/relative).resolve()
        if not p.is_relative_to(ROOT.parents[1].resolve()) or sha(p.read_bytes())!=expected:
            raise ValueError('Reviewed input changed: '+relative)
    dates = set(json.loads((ROOT/'audit/retrospective_scope.json').read_text())['allowed_retrospective_dates'])
    targets = manifest['targets']
    if len({x['key'] for x in targets}) != len(targets):
        raise ValueError('Duplicate targets')
    for item in targets:
        key = item['key']
        match = re.fullmatch(r'(?:reports/archive/(\d{4}-\d{2}-\d{2})\.html|Strategies/json/(\d{4}-\d{2}-\d{2})_Market_Intelligence\.json|Strategies/(\d{4}-\d{2}-\d{2})_Market_Intelligence\.pdf)', key)
        collection = key in {name for month, zip_name in COLLECTIONS.items()
                            for name in (f'reports/{month}.html', f'reports/{month}/{zip_name}', f'reports/{month}/methodology.txt')}
        if not ((match and next(x for x in match.groups() if x) in dates) or collection):
            raise ValueError('Out-of-scope target: '+key)
        p = (ROOT/item['path']).resolve()
        if not p.is_relative_to(ROOT.parents[1].resolve()):
            raise ValueError('Artifact path leaves repository: '+str(p))
        blob = p.read_bytes()
        if sha(blob) != item['sha256'] or len(blob) != item['bytes']:
            raise ValueError('Artifact changed: '+str(p))
        original = item.get('expected_original_sha256')
        if not isinstance(original, str) or not re.fullmatch(r'[0-9a-f]{64}', original):
            raise ValueError('Reviewed original SHA256 is required: '+key)
    return targets


def validate_resume(receipt, targets):
    if receipt.get('targets') != targets:
        raise ValueError('Resume requires exact original targets')
    run = receipt.get('run', '')
    if not re.fullmatch(r'\d{8}T\d{6}Z', run):
        raise ValueError('Invalid original publication run')
    expected_prefix = 'reports/_retrospective_backup/retail-editorial/'+run+'/'
    if receipt.get('backup_prefix') != expected_prefix:
        raise ValueError('Resume backup prefix differs from original run')
    if receipt.get('latest_write_performed') is not False or receipt.get('index_write_performed') is not False:
        raise ValueError('Unexpected latest/index write flag')
    by_key = {item['key']: item for item in targets}
    if not set(receipt.get('objects', {})) <= set(by_key):
        raise ValueError('Out-of-scope object in original receipt')
    for key, state in receipt.get('objects', {}).items():
        item = by_key[key]
        if 'original' in state:
            if state['original'].get('sha256') != item['expected_original_sha256']:
                raise ValueError('Original proof differs from reviewed bytes: '+key)
            if state.get('backup_key') != expected_prefix+key or state.get('backup_sha_verified') is not True:
                raise ValueError('Invalid original backup proof: '+key)
        if state.get('verified'):
            proof = state.get('current', {})
            if proof.get('sha256') != item['sha256'] or proof.get('bytes') != item['bytes'] or not proof.get('etag'):
                raise ValueError('Incomplete current artifact proof: '+key)
    return receipt


def publish(targets, resume=False):
    config = Config(connect_timeout=8, read_timeout=25,
                    retries={'total_max_attempts': 1}, max_pool_connections=2)
    session = boto3.Session(aws_access_key_id=os.environ['AWS_KEY'],
                           aws_secret_access_key=os.environ['AWS_SECRET'], region_name='eu-north-1')
    s3 = session.client('s3', config=config)
    cf = session.client('cloudfront', config=config)
    if resume:
        receipt = validate_resume(json.loads(RECEIPT.read_text()), targets)
        # Preserve and revalidate the original backups. Never replace them
        # with a partially published version during resume.
        for key, state in receipt['objects'].items():
            if 'original' in state:
                proof, _ = read(s3, state['backup_key'])
                if proof['sha256'] != state['original']['sha256'] or proof['bytes'] != state['original']['bytes']:
                    raise ValueError('Original backup changed: '+key)
    else:
        if RECEIPT.exists():
            raise ValueError('Original receipt exists; use --resume')
        run = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        latest, _ = read(s3, 'reports/latest.html')
        receipt = {'run': run, 'targets': targets, 'objects': {}, 'stage': 'objects',
                   'backup_prefix': 'reports/_retrospective_backup/retail-editorial/'+run+'/',
                   'latest_before': latest, 'latest_write_performed': False,
                   'index_write_performed': False, 'started_at_utc': now()}
        save(RECEIPT, receipt)
    for index, item in enumerate(targets, 1):
        key = item['key']
        state = receipt['objects'].get(key)
        if state and state.get('verified'):
            continue
        current, blob = read(s3, key)
        if current['sha256'] == item['sha256']:
            state = state or {}
        else:
            if state is None:
                if current['sha256'] != item['expected_original_sha256']:
                    raise ValueError('Original changed since review: '+key)
                backup = receipt['backup_prefix']+key
                prior_backup, _ = maybe_read(s3, backup)
                if prior_backup is not None:
                    if prior_backup['sha256'] != current['sha256'] or prior_backup['bytes'] != current['bytes']:
                        raise ValueError('Existing backup differs from reviewed original: '+key)
                else:
                    request(lambda: s3.copy_object(Bucket=BUCKET, Key=backup,
                            CopySource={'Bucket': BUCKET, 'Key': key}, CopySourceIfMatch=current['etag']))
                proof, _ = read(s3, backup)
                if proof['sha256'] != current['sha256'] or proof['bytes'] != current['bytes']:
                    raise ValueError('Backup hash mismatch: '+key)
                state = {'original': current, 'backup_key': backup, 'backup_sha_verified': True}
                receipt['objects'][key] = state
                save(RECEIPT, receipt)
            if current['etag'] != state['original']['etag']:
                raise ValueError('Concurrent target change: '+key)
            body = (ROOT/item['path']).read_bytes()
            try:
                request(lambda: s3.put_object(Bucket=BUCKET, Key=key, Body=body,
                        ContentType=item['content_type'], IfMatch=current['etag'],
                        Metadata={'retail-revision-run': receipt['run']}))
            except ClientError as error:
                if error.response.get('ResponseMetadata', {}).get('HTTPStatusCode') != 412:
                    raise
                # A completed write can lose its response and make the retry's
                # condition fail. Accept only a full hash proof of our bytes.
            current, _ = read(s3, key)
            if current['sha256'] != item['sha256'] or current['bytes'] != item['bytes']:
                raise ValueError('Written artifact failed SHA check: '+key)
        state.update(verified=True, current=current, verified_at_utc=now())
        receipt['objects'][key] = state
        receipt['verified_count'] = sum(bool(x.get('verified')) for x in receipt['objects'].values())
        save(RECEIPT, receipt)
        if index % 20 == 0 or index == len(targets):
            print('Origin SHA verified', index, 'of', len(targets), flush=True)
    receipt['stage'] = 'complete-set-check'
    save(RECEIPT, receipt)
    for item in targets:
        proof = receipt['objects'][item['key']]['current']
        head = request(lambda: s3.head_object(Bucket=BUCKET, Key=item['key']))
        if head['ETag'] != proof['etag'] or head['ContentLength'] != proof['bytes']:
            current, _ = read(s3, item['key'])
            if current['sha256'] != item['sha256'] or current['bytes'] != item['bytes']:
                raise ValueError('Target changed before final gate: '+item['key'])
            receipt['objects'][item['key']]['current'] = current
    latest, _ = read(s3, 'reports/latest.html')
    receipt['latest_after'] = latest
    receipt['latest_unchanged'] = latest == receipt['latest_before']
    paths = ['/'+x['key'] for x in targets if x['key'].startswith('reports/')]
    inv = request(lambda: cf.create_invalidation(DistributionId=DIST,
        InvalidationBatch={'Paths': {'Quantity': len(paths), 'Items': paths},
                           'CallerReference': 'retail-editorial-'+receipt['run']}))['Invalidation']
    receipt.update(stage='published', invalidation_id=inv['Id'],
                   invalidation_status=inv['Status'], finished_at_utc=now())
    save(RECEIPT, receipt)
    print('Published', len(targets), 'artifacts; invalidation', inv['Id'], inv['Status'], flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--go', action='store_true')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    targets = plan()
    print('Validated', len(targets), 'reviewed artifact targets', flush=True)
    if args.go:
        publish(targets, args.resume)
    else:
        print('Dry run: no remote calls or changes', flush=True)


if __name__ == '__main__':
    main()
