"""upload.py <dates> [--go] [--no-aws] — publish the November 2025 retrospective briefings to the report archive.

For each date: reports/archive/<date>.html, Strategies/json/<date>_Market_Intelligence.json and
Strategies/<date>_Market_Intelligence.pdf (rendered with the report Lambda's own matplotlib renderer). Any object that
already exists under those keys, and reports/index.html, are first copied to
reports/_retrospective_backup/november-weekdays/<UTC timestamp>/<original key>. The archive index gets one row per date
(newest first, same markup as the Lambda's index); reports/latest.html is never touched. Only the written paths are
invalidated on CloudFront. Without --go it is a dry run; --no-aws builds the HTML / JSON / PDF in memory only (no AWS
call at all) to prove the pages render.

Needs boto3 and matplotlib, and the report Lambda source for the PDF renderer: $LAMBDA_PY, default
../../lambda_function.py (repo root, as on the report-scope branches).

Credentials: in the cloud session the default AWS_ACCESS_KEY_ID is a proxy placeholder and is rejected by AWS. Put the
real IAM key in the environment settings as AWS_Key / AWS_Pass — this script maps them to AWS_ACCESS_KEY_ID /
AWS_SECRET_ACCESS_KEY itself. A pre-flight (sts:GetCallerIdentity + s3:HeadBucket) stops the run before any write if
the key is not accepted."""
import sys, os, re, json, types, datetime as dt, importlib.util
import boto3

if os.environ.get('AWS_Key') and os.environ.get('AWS_Pass'):
    os.environ['AWS_ACCESS_KEY_ID'], os.environ['AWS_SECRET_ACCESS_KEY'] = os.environ['AWS_Key'], os.environ['AWS_Pass']

T = os.path.dirname(os.path.abspath(__file__)); C = os.path.dirname(T)
B = os.environ.get('S3_BUCKET', 's3bucketmz'); CF = os.environ.get('CLOUDFRONT_DISTRIBUTION_ID', 'E15IJW4438D21G')
go = '--go' in sys.argv; offline = '--no-aws' in sys.argv
dates = [a for a in sys.argv[1:] if not a.startswith('--')]
stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
BAK = f'reports/_retrospective_backup/november-weekdays/{stamp}/'

for v in ('ANTHROPIC_API_KEY', 'SENDER_EMAIL', 'RECIPIENT_EMAIL'):
    os.environ.setdefault(v, 'x')
sys.modules.setdefault('anthropic', types.ModuleType('anthropic'))
lp = os.environ.get('LAMBDA_PY') or os.path.join(C, '..', '..', 'lambda_function.py')
spec = importlib.util.spec_from_file_location('lf', lp)
lf = importlib.util.module_from_spec(spec); spec.loader.exec_module(lf)

if not offline:
    s3 = boto3.client('s3', region_name='eu-north-1')
    try:
        who = boto3.client('sts', region_name='eu-north-1').get_caller_identity()
        s3.head_bucket(Bucket=B)
    except Exception as e:
        sys.exit(f'PRE-FLIGHT FAILED — AWS did not accept the credentials ({type(e).__name__}: {str(e)[:160]}).\n'
                 'Set AWS_Key / AWS_Pass (the real IAM key) in the environment and run again. Nothing was written.')
    print('pre-flight ok:', who['Arn'], '| bucket', B, '| distribution', CF)


def exists(k):
    try:
        s3.head_object(Bucket=B, Key=k); return True
    except Exception:
        return False


def put(key, body, ct):
    if offline:
        print(f'built {key} ({len(body):,} bytes)'); return
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

if offline:
    sys.exit(f'--no-aws: built {len(dates)} dates in memory, nothing uploaded')

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
        'Paths': {'Quantity': len(paths), 'Items': paths}, 'CallerReference': f'nov-retro-{stamp}'})
    print('uploaded', len(dates), 'dates; backups under', BAK, '; invalidation', inv['Invalidation']['Id'])
else:
    print('dry run —', len(dates), 'dates')
