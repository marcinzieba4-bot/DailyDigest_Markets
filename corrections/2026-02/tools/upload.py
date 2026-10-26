"""upload.py <dates> [--go] — publish the February 2026 retrospective briefings to the report archive.

For each date: reports/archive/<date>.html, Strategies/json/<date>_Market_Intelligence.json and
Strategies/<date>_Market_Intelligence.pdf (rendered with the report Lambda's own matplotlib renderer). Any object that
already exists under those keys, and reports/index.html, are first copied to
reports/_retrospective_backup/february-weekdays/<UTC timestamp>/<original key>. The archive index gets one row per date
(newest first, same markup as the Lambda's index); reports/latest.html is never touched. Only the written paths are
invalidated on CloudFront. Without --go it is a dry run.

Needs boto3 and matplotlib, and the report Lambda source for the PDF renderer: $LAMBDA_PY, default
../../../lambda_function.py (as on the report-scope branches). In the cloud session use
AWS_ACCESS_KEY_ID=$AWS_Key AWS_SECRET_ACCESS_KEY=$AWS_Pass."""
import sys, os, re, json, types, datetime as dt, importlib.util
import boto3

T = os.path.dirname(os.path.abspath(__file__)); C = os.path.dirname(T)
B = os.environ.get('S3_BUCKET', 's3bucketmz'); CF = os.environ.get('CLOUDFRONT_DISTRIBUTION_ID', 'E15IJW4438D21G')
go = '--go' in sys.argv; dates = [a for a in sys.argv[1:] if not a.startswith('--')]
stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
BAK = f'reports/_retrospective_backup/february-weekdays/{stamp}/'

for v in ('ANTHROPIC_API_KEY', 'SENDER_EMAIL', 'RECIPIENT_EMAIL'):
    os.environ.setdefault(v, 'x')
sys.modules.setdefault('anthropic', types.ModuleType('anthropic'))
lp = os.environ.get('LAMBDA_PY') or os.path.join(C, '..', '..', 'lambda_function.py')
spec = importlib.util.spec_from_file_location('lf', lp)
lf = importlib.util.module_from_spec(spec); spec.loader.exec_module(lf)
s3 = boto3.client('s3', region_name='eu-north-1')


def exists(k):
    try:
        s3.head_object(Bucket=B, Key=k); return True
    except Exception:
        return False


def put(key, body, ct):
    live = exists(key)
    if not go:
        print(f'{"would back up + " if live else ""}would put {key} ({len(body):,} bytes)'); return
    if live:
        s3.copy_object(Bucket=B, CopySource={'Bucket': B, 'Key': key}, Key=BAK + key)
    s3.put_object(Bucket=B, Key=key, Body=body, ContentType=ct)
    print(f'put {key} ({len(body):,} bytes){" — previous object backed up" if live else ""}')


paths = []
for d in dates:
    h = open(os.path.join(C, 'html', f'{d}.html'), encoding='utf-8').read()
    jp = os.path.join(C, 'json', f'{d}_Market_Intelligence.json')
    label = json.load(open(jp))['date']
    pdf = lf._html_to_pdf_bytes(h, label)
    put(f'reports/archive/{d}.html', h.encode('utf-8'), 'text/html; charset=utf-8')
    put(f'Strategies/json/{d}_Market_Intelligence.json', open(jp, 'rb').read(), 'application/json')
    put(f'Strategies/{d}_Market_Intelligence.pdf', pdf, 'application/pdf')
    paths.append(f'/reports/archive/{d}.html')

# archive index: add the new rows, keep everything else byte-for-byte
idx = s3.get_object(Bucket=B, Key='reports/index.html')['Body'].read().decode('utf-8')
have = set(re.findall(r'archive/(\d{4}-\d{2}-\d{2})\.html', idx))
rows = sorted(have | set(dates), reverse=True)
ul = '<ul style="line-height:1.8">' + ''.join(f'<li><a href="archive/{d}.html">{d}</a></li>' for d in rows) + '</ul>'
new_idx = re.sub(r'<ul style="line-height:1.8">.*?</ul>', lambda m: ul, idx, count=1, flags=re.S)
print(f'index: {len(have)} rows -> {len(rows)} rows')
if go:
    s3.copy_object(Bucket=B, CopySource={'Bucket': B, 'Key': 'reports/index.html'}, Key=BAK + 'reports/index.html')
    s3.put_object(Bucket=B, Key='reports/index.html', Body=new_idx.encode('utf-8'), ContentType='text/html; charset=utf-8')
    paths.append('/reports/index.html')
    inv = boto3.client('cloudfront').create_invalidation(DistributionId=CF, InvalidationBatch={
        'Paths': {'Quantity': len(paths), 'Items': paths}, 'CallerReference': f'feb-retro-{stamp}'})
    print('uploaded', len(dates), 'dates; backups under', BAK, '; invalidation', inv['Invalidation']['Id'])
else:
    print('dry run —', len(dates), 'dates')
