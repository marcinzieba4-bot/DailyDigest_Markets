"""Save the corrected reports back to S3 under their original archive keys.

Run from the repo root:
    export $(grep -v '^#' .env | xargs)
    python3 corrections/2026-10-19/upload.py            # dry run: lists what would be written
    python3 corrections/2026-10-19/upload.py --go       # backup originals (server-side copy), write corrected
                                                        # HTML + JSON + regenerated PDFs, invalidate /reports/*
Options: --no-pdf (skip PDF regeneration; needs matplotlib otherwise), --no-backup.
Originals are copied first to reports/_pre_correction_backup/ and
Strategies/json/_pre_correction_backup/, prefixes the archive index does not list.
"""
import boto3, os, sys, glob, json, types, datetime, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
B = os.environ.get('S3_BUCKET', 's3bucketmz')
CF = os.environ.get('CLOUDFRONT_DISTRIBUTION_ID', 'E15IJW4438D21G')
dry = '--go' not in sys.argv
do_pdf = '--no-pdf' not in sys.argv
do_backup = '--no-backup' not in sys.argv

s3 = boto3.client('s3', region_name='eu-north-1')
count = 0

def put(key, body, ct):
    global count
    count += 1
    if dry:
        print('would put', key, len(body))
    else:
        s3.put_object(Bucket=B, Key=key, Body=body, ContentType=ct)

def backup(key, dest):
    global count
    count += 1
    if dry:
        print('would copy', key, '->', dest)
    else:
        s3.copy_object(Bucket=B, CopySource={'Bucket': B, 'Key': key}, Key=dest)

if do_pdf:
    # load the Lambda's own PDF renderer without its secrets
    for v in ('ANTHROPIC_API_KEY', 'SENDER_EMAIL', 'RECIPIENT_EMAIL'):
        os.environ.setdefault(v, 'x')
    sys.modules.setdefault('anthropic', types.ModuleType('anthropic'))
    spec = importlib.util.spec_from_file_location('lambda_function', os.path.join(ROOT, 'lambda_function.py'))
    lf = importlib.util.module_from_spec(spec); spec.loader.exec_module(lf)

dates = sorted(os.path.basename(f)[:-5] for f in glob.glob(os.path.join(HERE, 'html', '*.html')))
for d in dates:
    html_path = os.path.join(HERE, 'html', f'{d}.html')
    json_path = os.path.join(HERE, 'json', f'{d}_Market_Intelligence.json')
    if do_backup:
        backup(f'reports/archive/{d}.html', f'reports/_pre_correction_backup/{d}.html')
        backup(f'Strategies/json/{d}_Market_Intelligence.json', f'Strategies/json/_pre_correction_backup/{d}_Market_Intelligence.json')
    html = open(html_path, encoding='utf-8').read()
    put(f'reports/archive/{d}.html', html.encode('utf-8'), 'text/html; charset=utf-8')
    put(f'Strategies/json/{d}_Market_Intelligence.json', open(json_path, 'rb').read(), 'application/json')
    if do_pdf:
        date_label = json.load(open(json_path))['date']
        put(f'Strategies/{d}_Market_Intelligence.pdf', lf._html_to_pdf_bytes(html, date_label), 'application/pdf')
put('reports/latest.html', open(os.path.join(HERE, 'html', f'{dates[-1]}.html'), 'rb').read(), 'text/html; charset=utf-8')
print('operations', count, 'dates', len(dates), 'latest ->', dates[-1], '(dry run)' if dry else '')

if not dry:
    cf = boto3.client('cloudfront')
    inv = cf.create_invalidation(
        DistributionId=CF,
        InvalidationBatch={'Paths': {'Quantity': 1, 'Items': ['/reports/*']},
                           'CallerReference': f"retro-{datetime.datetime.utcnow().timestamp()}"})
    print('cloudfront invalidation', inv['Invalidation']['Id'], inv['Invalidation']['Status'])
