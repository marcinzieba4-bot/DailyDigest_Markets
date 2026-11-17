"""publish_nov2023.py [--go] — publish the 22 November 2023 editions and the month collection to s3bucketmz
(zembihf.xyz via CloudFront E15IJW4438D21G), mirroring the April 2024 publisher's key layout.

Dry run (default): verify every artifact against checks/artifact_manifest.json, confirm no target key already exists,
read reports/index.html and preview the merged archive index. --go: back up the index, upload all targets with
create-only writes (IfNoneMatch='*'), merge the index (preserving every existing link), verify every origin body by
SHA-256, confirm protected objects are unchanged, and create a scoped CloudFront invalidation. Receipt:
checks/publication.json. Credentials: AWS_Key / AWS_Pass environment variables (never printed or stored)."""
import datetime as dt, hashlib, json, os, re, sys
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
from bs4 import BeautifulSoup
ROOT = Path(__file__).resolve().parent.parent
BUCKET, DIST, YM = 's3bucketmz', 'E15IJW4438D21G', '2023-11'
DATES = [dt.date(2023, 11, n).isoformat() for n in range(1, 31) if dt.date(2023, 11, n).weekday() < 5]
sha = lambda b: hashlib.sha256(b).hexdigest()
CT = {'html': 'text/html; charset=utf-8', 'json': 'application/json', 'pdf': 'application/pdf', 'zip': 'application/zip', 'txt': 'text/plain; charset=utf-8'}

def targets():
    m = json.loads((ROOT/'checks/artifact_manifest.json').read_text()); out = []
    assert [r['date'] for r in m['reports']] == DATES
    for r in m['reports']:
        d = r['date']
        for ext, key in (('html', f'reports/archive/{d}.html'), ('json', f'Strategies/json/{d}_Market_Intelligence.json'), ('pdf', f'Strategies/{d}_Market_Intelligence.pdf')):
            out.append(dict(r['files'][ext], key=key, content_type=CT[ext]))
    for name, art in m['collection'].items():
        key = f'reports/{name}' if name == f'{YM}.html' else f'reports/{YM}/{name}'
        out.append(dict(art, key=key, content_type=CT[name.rsplit('.', 1)[1]]))
    assert len(out) == 70 and len({x['key'] for x in out}) == 70
    for t in out:
        blob = (ROOT/t['path']).read_bytes()
        assert len(blob) == t['bytes'] and sha(blob) == t['sha256'], 'artifact changed: ' + t['path']
        assert YM in t['key'], t['key']
    return out

def merge_index(blob):
    soup = BeautifulSoup(blob, 'html.parser')
    cands = [ul for ul in soup.find_all('ul') if any(re.fullmatch(r'archive/\d{4}-\d{2}-\d{2}\.html', a.get('href', '')) and a.find_parent('ul') is ul for a in ul.find_all('a'))]
    if len(cands) != 1: raise ValueError('A single unambiguous daily archive list is required')
    ul = cands[0]; old = {a.get('href') for a in soup.find_all('a')}
    for d in DATES:
        if f'archive/{d}.html' not in old:
            li = soup.new_tag('li'); a = soup.new_tag('a', href=f'archive/{d}.html'); a.string = d; li.append(a); ul.append(li)
    rows = []
    for li in ul.find_all('li', recursive=False):
        a = li.find('a'); mm = re.fullmatch(r'archive/(\d{4}-\d{2}-\d{2})\.html', a.get('href', '')) if a else None
        if mm: rows.append((mm.group(1), li))
    for _, li in sorted(rows, key=lambda x: x[0], reverse=True): li.extract(); ul.append(li)
    for href, label in [(f'{YM}.html', 'November 2023 — 22 weekday briefings & download'), (f'{YM}/What_Retail_Is_Playing_{YM}.html', 'November 2023 — What Retail Is Playing')]:
        if not soup.find('a', href=href):
            p = soup.new_tag('p'); a = soup.new_tag('a', href=href); a.string = label; p.append(a); ul.insert_before(p)
    if not old <= {a.get('href') for a in soup.find_all('a')}: raise ValueError('Merge would remove links')
    for d in DATES:
        if len(ul.find_all('a', href=f'archive/{d}.html')) != 1: raise ValueError('Missing/duplicate ' + d)
    return str(soup).encode(), len(old)

def main(go):
    s = boto3.session.Session(aws_access_key_id=os.environ['AWS_Key'], aws_secret_access_key=os.environ['AWS_Pass'], region_name='eu-north-1')
    s3, cf = s.client('s3'), s.client('cloudfront')
    ts = targets(); existing = []
    for t in ts:
        try: s3.head_object(Bucket=BUCKET, Key=t['key']); existing.append(t['key'])
        except ClientError as e:
            if e.response['Error']['Code'] not in ('404', 'NoSuchKey', 'NotFound'): raise
    if existing: raise SystemExit('Refusing: target keys already exist: ' + repr(existing[:5]))
    idx = s3.get_object(Bucket=BUCKET, Key='reports/index.html'); idx_body = idx['Body'].read()
    merged, nlinks = merge_index(idx_body)
    protected = ['reports/latest.html', 'reports/2024-04.html', 'reports/2024-11.html', 'reports/archive/2024-04-30.html']
    def snap():
        out = {}
        for k in protected:
            try: out[k] = sha(s3.get_object(Bucket=BUCKET, Key=k)['Body'].read())
            except ClientError: out[k] = None
        return out
    before = snap()
    print(f'Plan: {len(ts)} new objects ({sum(t["bytes"] for t in ts)/1e6:.1f} MB), none pre-existing; index {len(idx_body)} -> {len(merged)} bytes, {nlinks} existing links preserved')
    if not go: print('DRY RUN only'); return
    run = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    rec = {'run': run, 'bucket': BUCKET, 'distribution': DIST, 'targets': [], 'protected_before': before}
    bkey = f'reports/_retrospective_backup/nov-2023-weekdays/{run}/reports/index.html'
    s3.put_object(Bucket=BUCKET, Key=bkey, Body=idx_body, ContentType='text/html; charset=utf-8', IfNoneMatch='*')
    rec['index_backup'] = {'key': bkey, 'sha256': sha(idx_body)}
    for t in ts:
        blob = (ROOT/t['path']).read_bytes()
        s3.put_object(Bucket=BUCKET, Key=t['key'], Body=blob, ContentType=t['content_type'], IfNoneMatch='*')
        got = sha(s3.get_object(Bucket=BUCKET, Key=t['key'])['Body'].read())
        assert got == t['sha256'], 'origin body mismatch ' + t['key']
        rec['targets'].append({'key': t['key'], 'sha256': got, 'bytes': t['bytes']})
    s3.put_object(Bucket=BUCKET, Key='reports/index.html', Body=merged, ContentType='text/html; charset=utf-8', IfMatch=idx['ETag'])
    assert sha(s3.get_object(Bucket=BUCKET, Key='reports/index.html')['Body'].read()) == sha(merged)
    rec['index_sha256'] = sha(merged); rec['protected_after'] = snap()
    assert rec['protected_before'] == rec['protected_after'], 'protected object changed'
    inv = cf.create_invalidation(DistributionId=DIST, InvalidationBatch={'Paths': {'Quantity': 5, 'Items': ['/reports/index.html', f'/reports/archive/{YM}-*', f'/reports/{YM}*', f'/Strategies/json/{YM}-*', f'/Strategies/{YM}-*']}, 'CallerReference': 'nov2023-' + run})
    rec['invalidation'] = {'id': inv['Invalidation']['Id'], 'status': inv['Invalidation']['Status']}
    (ROOT/'checks/publication.json').write_text(json.dumps(rec, indent=1) + '\n')
    print('Published', len(ts), 'objects; index merged; invalidation', rec['invalidation'])

if __name__ == '__main__':
    main('--go' in sys.argv)
