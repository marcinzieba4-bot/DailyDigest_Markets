#!/usr/bin/env python3
"""finalize.py [--go] — splice all verified Poland blocks, rebuild JSON/PDF, upload (with --go), invalidate.
Run with -I from anywhere. Without --go it only splices and builds locally and reports."""
import sys, os, re, glob, json, types, subprocess, importlib.util, datetime
W = '/tmp/claude-0/-home-user/01233cf7-f758-5bad-b280-d38226412ca9/scratchpad/work'
A = '/tmp/claude-0/-home-user/01233cf7-f758-5bad-b280-d38226412ca9/scratchpad/archive'
go = '--go' in sys.argv

# 1. splice every passing block
r = subprocess.run([sys.executable, '-I', f'{W}/pl/splice.py'], capture_output=True, text=True)
print(r.stdout.strip().splitlines()[-1])
dates = sorted(os.path.basename(f)[:-5] for f in glob.glob(f'{W}/edited/*.html'))
spliced = [d for d in dates if open(f'{W}/edited/{d}.html', encoding='utf-8').read().count('Geopolitics &amp; Security') + open(f'{W}/edited/{d}.html', encoding='utf-8').read().count('Geopolitics & Security') > 0]
print('reports with wide Poland block:', len(spliced), 'of', len(dates))

# 2. yield verifier must still pass on every spliced report (Poland block must not reintroduce yield errors)
bad = []
for d in dates:
    rr = subprocess.run([sys.executable, '-I', f'{W}/verify.py', d], capture_output=True, text=True)
    real = [l for l in rr.stdout.splitlines() if 'FAIL:' in l and 'tag multiset' not in l]
    if real: bad.append((d, real[:3]))
print('yield verifier failures:', len(bad)); [print(' ', b) for b in bad[:5]]
if bad: sys.exit(1)

# 3. rebuild JSON + PDF with the Lambda's own functions
for v in ('ANTHROPIC_API_KEY', 'SENDER_EMAIL', 'RECIPIENT_EMAIL'): os.environ.setdefault(v, 'x')
sys.modules.setdefault('anthropic', types.ModuleType('anthropic'))
spec = importlib.util.spec_from_file_location('lf', '/home/user/DailyDigest_Markets/lambda_function.py')
lf = importlib.util.module_from_spec(spec); spec.loader.exec_module(lf)
os.makedirs(f'{W}/out/json', exist_ok=True); os.makedirs(f'{W}/out/pdf', exist_ok=True)
import warnings; warnings.filterwarnings('ignore')
for d in dates:
    html_ = open(f'{W}/edited/{d}.html', encoding='utf-8').read()
    oj = json.load(open(f'{A}/Strategies__json__{d}_Market_Intelligence.json'))
    sections, cur = [], None
    for style, text in lf._parse_html_paragraphs(html_):
        if style == 'h1': cur = {'heading': text, 'subheadings': [], 'body': []}; sections.append(cur)
        elif style == 'h2':
            if cur is None: cur = {'heading': '', 'subheadings': [], 'body': []}; sections.append(cur)
            cur['subheadings'].append(text)
        elif style == 'body' and text:
            if cur is None: cur = {'heading': '', 'subheadings': [], 'body': []}; sections.append(cur)
            cur['body'].append(text)
    json.dump({'date': oj['date'], 'generated_at': oj['generated_at'], 'sections': sections},
              open(f'{W}/out/json/{d}_Market_Intelligence.json', 'w'), ensure_ascii=False, indent=2)
    open(f'{W}/out/pdf/{d}_Market_Intelligence.pdf', 'wb').write(lf._html_to_pdf_bytes(html_, oj['date']))
print('built JSON/PDF for', len(dates))

if not go:
    print('dry run: nothing uploaded'); sys.exit(0)

# 4. upload under the original keys + latest.html, then invalidate
import boto3
B = 's3bucketmz'
s3 = boto3.client('s3', region_name='eu-north-1', aws_access_key_id=os.environ['AWS_Key'], aws_secret_access_key=os.environ['AWS_Pass'])
put = lambda k, p, ct: s3.put_object(Bucket=B, Key=k, Body=open(p, 'rb').read(), ContentType=ct)
for d in dates:
    put(f'reports/archive/{d}.html', f'{W}/edited/{d}.html', 'text/html; charset=utf-8')
    put(f'Strategies/json/{d}_Market_Intelligence.json', f'{W}/out/json/{d}_Market_Intelligence.json', 'application/json')
    put(f'Strategies/{d}_Market_Intelligence.pdf', f'{W}/out/pdf/{d}_Market_Intelligence.pdf', 'application/pdf')
# latest.html only if the newest archived report on S3 is one of ours
keys = sorted(o['Key'] for o in s3.list_objects_v2(Bucket=B, Prefix='reports/archive/').get('Contents', []))
newest = keys[-1].rsplit('/', 1)[-1][:-5]
if newest == dates[-1]:
    put('reports/latest.html', f'{W}/edited/{dates[-1]}.html', 'text/html; charset=utf-8'); print('latest.html ->', dates[-1])
else:
    print('latest.html left alone: newest archived report is', newest)
cf = boto3.client('cloudfront', aws_access_key_id=os.environ['AWS_Key'], aws_secret_access_key=os.environ['AWS_Pass'])
inv = cf.create_invalidation(DistributionId='E15IJW4438D21G', InvalidationBatch={'Paths': {'Quantity': 1, 'Items': ['/reports/*']},
                             'CallerReference': f"poland-{datetime.datetime.now(datetime.UTC).timestamp()}"})
print('uploaded', len(dates), 'invalidation', inv['Invalidation']['Id'])
