"""publish_march_2025.py [--go] — publish the 21 March 2025 editions and the What Retail Is Playing page.

Dry run unless --go. The script:
- writes only new March keys: reports/archive/<date>.html, Strategies/json/<date>_Market_Intelligence.json and
  reports/2025-03/What_Retail_Is_Playing_2025-03.html;
- refuses to overwrite any existing key, and never writes reports/latest.html or any April key;
- labels every page and JSON file as an AI-audited retrospective reconstruction, not independently reviewed by a human;
- merges the March archive links into reports/index.html without removing any existing link (conditional on the ETag read);
- verifies each upload by ETag (MD5) against the local bytes;
- invalidates /reports/* and /Strategies/json/2025-03-* on CloudFront distribution E15IJW4438D21G;
- writes audit/publish_receipt_2025-03.json.

Credentials come from the AWS_Key and AWS_Pass environment variables; their values are never printed.
The April publish.py is not used: it is hard-wired to April keys and requires April review receipts.
"""
import datetime as dt
import hashlib
import json
import os
import re
import sys
import uuid
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
GO = '--go' in sys.argv
BUCKET = 's3bucketmz'
DIST = 'E15IJW4438D21G'
DATES = [dt.date(2025, 3, n).isoformat() for n in range(1, 32) if dt.date(2025, 3, n).weekday() < 5]
RETAIL_KEY = 'reports/2025-03/What_Retail_Is_Playing_2025-03.html'
NOTICE = 'Retrospective reconstruction, March 2025. AI-audited; not independently reviewed by a human editor.'
JSON_STATUS = 'Retrospective reconstruction. AI-audited; not independently reviewed by a human editor.'
INDEX_LINK = '2025-03/What_Retail_Is_Playing_2025-03.html'

session = boto3.Session(aws_access_key_id=os.environ['AWS_Key'], aws_secret_access_key=os.environ['AWS_Pass'],
                        region_name='eu-north-1')
s3 = session.client('s3')
cf = session.client('cloudfront')


def banner(html):
    box = ('<div style="font:13px/1.4 system-ui,sans-serif;background:#fff7e6;color:#5a3b00;'
           'border-bottom:1px solid #f0d9a8;padding:8px 16px">' + NOTICE + '</div>')
    m = re.search(r'<body[^>]*>', html, re.I)
    if not m:
        raise ValueError('no <body> tag to anchor the notice')
    return html[:m.end()] + box + html[m.end():]


def stage():
    items = []
    for d in DATES:
        html = (ROOT / 'html' / f'{d}.html').read_text(encoding='utf-8')
        items.append((f'reports/archive/{d}.html', 'text/html; charset=utf-8', banner(html).encode('utf-8')))
        js = json.loads((ROOT / 'json' / f'{d}_Market_Intelligence.json').read_text(encoding='utf-8'))
        js = {'publication_status': JSON_STATUS, **js}
        items.append((f'Strategies/json/{d}_Market_Intelligence.json', 'application/json; charset=utf-8',
                      json.dumps(js, ensure_ascii=False, indent=2).encode('utf-8')))
    rh = (ROOT / 'retail' / 'What_Retail_Is_Playing_2025-03.html').read_text(encoding='utf-8')
    items.append((RETAIL_KEY, 'text/html; charset=utf-8', banner(rh).encode('utf-8')))
    for key, _, _ in items:
        assert key != 'reports/latest.html' and '2025-04' not in key and '/apr' not in key, key
        assert key.startswith('reports/') or key.startswith('Strategies/json/'), key
    return items


def key_exists(key):
    try:
        s3.head_object(Bucket=BUCKET, Key=key)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] in ('404', 'NoSuchKey', 'NotFound'):
            return False
        raise


def merged_index(blob):
    soup = BeautifulSoup(blob, 'html.parser')
    ul = soup.find('ul')
    if ul is None:
        raise ValueError('archive index structure missing')
    old = {a.get('href') for a in soup.find_all('a')}
    for d in DATES:
        href = f'archive/{d}.html'
        if href not in old:
            li = soup.new_tag('li')
            a = soup.new_tag('a', href=href)
            a.string = d
            li.append(a)
            ul.append(li)
    rows = []
    for li in ul.find_all('li', recursive=False):
        a = li.find('a')
        m = re.fullmatch(r'archive/(\d{4}-\d{2}-\d{2})\.html', a.get('href', '')) if a else None
        if m:
            rows.append((m.group(1), li))
    for _, li in sorted(rows, reverse=True):
        li.extract()
        ul.append(li)
    if not soup.find('a', href=INDEX_LINK):
        p = soup.new_tag('p')
        a = soup.new_tag('a', href=INDEX_LINK)
        a.string = 'March 2025 — What Retail Is Playing (21 weekday briefings)'
        p.append(a)
        ul.insert_before(p)
    new = {a.get('href') for a in soup.find_all('a')}
    if not old <= new:
        raise ValueError('merge would drop an existing archive link')
    for d in DATES:
        if len(soup.find_all('a', href=f'archive/{d}.html')) != 1:
            raise ValueError('missing or duplicate March row ' + d)
    return str(soup).encode('utf-8')


def main():
    items = stage()
    print(f'staged {len(items)} objects (21 editions x 2 files + retail page)')
    clashes = [k for k, _, _ in items if key_exists(k)]
    if clashes:
        print('ABORT: these keys already exist and will not be overwritten:', clashes[:5], '...' if len(clashes) > 5 else '')
        return 2
    print('no March key exists yet: OK')
    idx = s3.get_object(Bucket=BUCKET, Key='reports/index.html')
    idx_etag = idx['ETag']
    new_index = merged_index(idx['Body'].read())
    print('archive index: March rows present after merge:', new_index.count(b'archive/2025-03-'), '| index etag read')
    if not GO:
        print('DRY RUN — nothing uploaded, index not written, no invalidation. Re-run with --go to publish.')
        return 0

    receipt = {'started_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'bucket': BUCKET,
               'distribution': DIST, 'notice': NOTICE, 'objects': []}
    for key, ctype, body in items:
        s3.put_object(Bucket=BUCKET, Key=key, Body=body, ContentType=ctype)
        head = s3.head_object(Bucket=BUCKET, Key=key)
        md5 = hashlib.md5(body).hexdigest()
        if head['ETag'].strip('"') != md5 or head['ContentLength'] != len(body):
            raise RuntimeError('verification failed for ' + key)
        receipt['objects'].append({'key': key, 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()})
    print(f'uploaded and verified {len(items)} objects')

    cur = s3.head_object(Bucket=BUCKET, Key='reports/index.html')['ETag']
    if cur != idx_etag:
        raise RuntimeError('reports/index.html changed during publication; index not written')
    s3.put_object(Bucket=BUCKET, Key='reports/index.html', Body=new_index, ContentType='text/html; charset=utf-8',
                  IfMatch=idx_etag)
    receipt['index'] = {'key': 'reports/index.html', 'sha256': hashlib.sha256(new_index).hexdigest()}
    print('archive index updated')

    inv = cf.create_invalidation(DistributionId=DIST, InvalidationBatch={
        'Paths': {'Quantity': 2, 'Items': ['/reports/*', '/Strategies/json/2025-03-*']},
        'CallerReference': str(uuid.uuid4())})['Invalidation']
    receipt['invalidation'] = {'id': inv['Id'], 'status': inv['Status'], 'paths': ['/reports/*', '/Strategies/json/2025-03-*']}
    print('CloudFront invalidation created:', inv['Id'], inv['Status'])
    receipt['finished_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
    out = ROOT / 'audit' / 'publish_receipt_2025-03.json'
    out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print('receipt written:', out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
