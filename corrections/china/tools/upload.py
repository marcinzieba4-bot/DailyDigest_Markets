"""upload.py <dates> [--go] — publish the edited reports for the given dates only.

For each date: copy the live S3 objects to reports/_pre_china_backup/ and Strategies/json/_pre_china_backup/ (a new prefix,
so the earlier _pre_correction_backup originals are never overwritten), then write HTML, JSON and a regenerated PDF under
the original keys, and invalidate exactly those CloudFront paths. reports/latest.html is never touched.
Without --go it is a dry run."""
import sys, os, json, types, datetime, importlib.util, boto3
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import C, REPORTS
ROOT = os.path.dirname(os.path.dirname(C)); JD = os.path.join(os.path.dirname(REPORTS), 'json')
B = os.environ.get('S3_BUCKET', 's3bucketmz'); CF = os.environ.get('CLOUDFRONT_DISTRIBUTION_ID', 'E15IJW4438D21G')
go = '--go' in sys.argv; dates = [a for a in sys.argv[1:] if not a.startswith('--')]
for v in ('ANTHROPIC_API_KEY', 'SENDER_EMAIL', 'RECIPIENT_EMAIL'): os.environ.setdefault(v, 'x')
sys.modules.setdefault('anthropic', types.ModuleType('anthropic'))
spec = importlib.util.spec_from_file_location('lf', os.path.join(ROOT, 'lambda_function.py'))
lf = importlib.util.module_from_spec(spec); spec.loader.exec_module(lf)
s3 = boto3.client('s3', region_name='eu-north-1')
def exists(k):
    try: s3.head_object(Bucket=B, Key=k); return True
    except Exception: return False
paths = []
for d in dates:
    h = open(os.path.join(REPORTS, f'{d}.html'), encoding='utf-8').read()
    jp = os.path.join(JD, f'{d}_Market_Intelligence.json'); label = json.load(open(jp))['date']
    pdf = lf._html_to_pdf_bytes(h, label)
    plan = [(f'reports/archive/{d}.html', h.encode('utf-8'), 'text/html; charset=utf-8', f'reports/_pre_china_backup/{d}.html'),
            (f'Strategies/json/{d}_Market_Intelligence.json', open(jp, 'rb').read(), 'application/json',
             f'Strategies/json/_pre_china_backup/{d}_Market_Intelligence.json'),
            (f'Strategies/{d}_Market_Intelligence.pdf', pdf, 'application/pdf', f'Strategies/_pre_china_backup/{d}_Market_Intelligence.pdf')]
    for key, body, ct, bak in plan:
        live = exists(key)
        if not go: print(f'would backup {key} -> {bak}' if live else f'(no live {key})', f'| would put {key} {len(body)} bytes'); continue
        if live and not exists(bak): s3.copy_object(Bucket=B, CopySource={'Bucket': B, 'Key': key}, Key=bak)
        s3.put_object(Bucket=B, Key=key, Body=body, ContentType=ct)
    paths.append(f'/reports/archive/{d}.html')
if go and paths:
    inv = boto3.client('cloudfront').create_invalidation(DistributionId=CF, InvalidationBatch={
        'Paths': {'Quantity': len(paths), 'Items': paths}, 'CallerReference': f"china-{datetime.datetime.now(datetime.timezone.utc).timestamp()}"})
    print('uploaded', len(dates), 'dates; invalidation', inv['Invalidation']['Id'])
elif not go: print('dry run —', len(dates), 'dates')
