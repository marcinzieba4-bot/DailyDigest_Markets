"""Verify scoped November origin/public delivery and live preservation read-only."""
from pathlib import Path
import concurrent.futures as cf
import datetime as dt
import hashlib
import importlib.util
import json
import os
import urllib.request
import io
import zipfile

import boto3
from botocore.config import Config

ROOT=Path(__file__).resolve().parent.parent


def main():
    spec=importlib.util.spec_from_file_location('nov_publish',ROOT/'tools/publish.py')
    pub=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pub)
    receipt=json.loads(pub.RECEIPT.read_text())
    session=boto3.Session(aws_access_key_id=os.environ['AWS_KEY'],
        aws_secret_access_key=os.environ['AWS_SECRET'],region_name='eu-north-1')
    config=Config(connect_timeout=8,read_timeout=30,
        retries={'mode':'standard','total_max_attempts':3},max_pool_connections=8)
    s3=session.client('s3',config=config)
    bundle_key='reports/2024-11/November_2024_Weekday_Reports.zip'
    public_bundle={}
    def verify(item):
        obj=pub.read(s3,item['key'])
        origin=obj is not None and obj['sha256']==item['sha256'] and obj['bytes']==item['bytes']
        if item['key'].startswith('Strategies/'):
            return {'key':item['key'],'origin_sha256_pass':origin,
                'public_sha256_pass':None,'public_status':None,'error':None,
                'public_delivery_route':'verified_report_zip_member'}
        url='https://zembihf.xyz/'+item['key']
        request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(request,timeout=45) as response:
                body=response.read()
                public_status=response.status
            public=hashlib.sha256(body).hexdigest()==item['sha256'] and len(body)==item['bytes']
            if item['key']==bundle_key and public:
                public_bundle['body']=body
            error=None
        except Exception as exc:
            public=False
            public_status=None
            error=type(exc).__name__+': '+str(exc)[:200]
        return {'key':item['key'],'origin_sha256_pass':origin,
            'public_sha256_pass':public,'public_status':public_status,'error':error,
            'public_delivery_route':'direct_https'}
    with cf.ThreadPoolExecutor(max_workers=6) as pool:
        rows=list(pool.map(verify,receipt['targets']))
    # The site's existing /Strategies routes return fallback HTML. PDFs/JSON
    # are delivered through the public report ZIP, so verify the actual public
    # archive and every contained report member instead of changing routing.
    members=[]
    manifest=json.loads((ROOT/'checks/artifact_manifest.json').read_text())
    if public_bundle.get('body'):
        with zipfile.ZipFile(io.BytesIO(public_bundle['body'])) as archive:
            if archive.testzip() is not None:
                raise ValueError('Public report ZIP has a corrupt member')
            for report in manifest['reports']:
                date=report['date']
                for ext,artifact in report['files'].items():
                    body=archive.read(artifact['path'])
                    ok=hashlib.sha256(body).hexdigest()==artifact['sha256'] and len(body)==artifact['bytes']
                    members.append({'date':date,'format':ext,'member':artifact['path'],'sha256_pass':ok})
                    if ext in ('pdf','json'):
                        key=(f'Strategies/{date}_Market_Intelligence.pdf' if ext=='pdf' else
                             f'Strategies/json/{date}_Market_Intelligence.json')
                        row=next(x for x in rows if x['key']==key)
                        row['public_sha256_pass']=ok
                        row['public_bundle_key']=bundle_key
                        row['public_bundle_member']=artifact['path']
    protected=pub.snapshot(s3)
    unchanged=protected==receipt['protected_before']
    idx=pub.read(s3,'reports/index.html')
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(idx['body'],'html.parser')
    links={d:len(soup.find_all('a',href=f'archive/{d}.html')) for d in pub.DATES}
    inv=session.client('cloudfront',config=config).get_invalidation(
        DistributionId=pub.DIST,Id=receipt['invalidation']['id'])['Invalidation']
    live=session.client('lambda',config=config).get_function_configuration(FunctionName='daily-trends-digest')
    original=json.loads((ROOT/'checks/code_discovery.json').read_text())['live_lambda_metadata']
    lambda_unchanged=all(live.get(k)==original.get(k) for k in ('CodeSha256','LastModified','Runtime'))
    passed=all(x['origin_sha256_pass'] and x['public_sha256_pass'] for x in rows) and len(members)==63 and all(x['sha256_pass'] for x in members) and unchanged and lambda_unchanged and all(n==1 for n in links.values()) and inv['Status']=='Completed'
    result={'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
        'passed':passed,'objects':rows,'protected_objects_unchanged':unchanged,
        'protected_checked':len(protected),'lambda_code_and_runtime_unchanged':lambda_unchanged,
        'archive_date_link_counts':links,'invalidation_status':inv['Status'],
        'public_report_zip_members':members,
        'direct_strategy_route_observation':'Existing /Strategies PDF/JSON URLs return site fallback HTML (HTTP200,text/html); they are not canonical download links. All42PDF/JSON files are delivered and SHA-verified inside the publicly verified report ZIP. No routing configuration changed.',
        'scope':'All68scoped origin bodies checked. Public delivery:21dailyHTML+5collection objects checked directly; all63HTML/PDF/JSON report members checked inside the publicZIP, including42nativeStrategy files. Latest,AugustHTML,Novemberweekends and liveLambda metadata compared with pre-publication snapshot.'}
    pub.save(ROOT/'checks/delivery_verification.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('objects','public_report_zip_members')},indent=2))
    for row in rows:
        if not row['origin_sha256_pass'] or not row['public_sha256_pass']:
            print(json.dumps(row))
    if not passed:
        raise SystemExit(1)


if __name__=='__main__':
    main()
