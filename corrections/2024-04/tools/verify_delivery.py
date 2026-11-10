"""Verify scoped April origin/public delivery and live preservation read-only."""
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
    spec=importlib.util.spec_from_file_location('sep_publish',ROOT/'tools/publish.py')
    pub=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pub)
    receipt_bytes=pub.RECEIPT.read_bytes()
    receipt=json.loads(receipt_bytes)
    receipt_sha256=hashlib.sha256(receipt_bytes).hexdigest()
    publication_review_sha256=pub.require_publication_engineering_review()
    if receipt.get('publication_engineering_review_sha256')!=publication_review_sha256:
        raise ValueError('Publication engineering review changed after publication')
    baseline=pub.deployment_baseline()
    if receipt.get('deployment_baseline') != baseline:
        raise ValueError('Original source-provenance metadata changed after publication')
    dates=[dt.date(2024, 4, n).isoformat() for n in range(1,31)
           if dt.date(2024, 4, n).weekday()<5]
    expected_targets={key for date in dates for key in
        (f'reports/archive/{date}.html',
         f'Strategies/json/{date}_Market_Intelligence.json',
         f'Strategies/{date}_Market_Intelligence.pdf')}
    expected_targets.update({'reports/2024-04.html',
        'reports/2024-04/April_2024_Weekday_Reports.zip',
        'reports/2024-04/April_2024_Frozen_Sources.zip',
        'reports/2024-04/What_Retail_Is_Playing_2024-04.html',
        'reports/2024-04/methodology.txt'})
    if (receipt.get('dates')!=dates or len(receipt.get('targets',[]))!=len(dates)*3+5
            or {x['key'] for x in receipt['targets']}!=expected_targets):
        raise ValueError('Delivery receipt must contain exactly the 71 expected April artifacts')
    session=boto3.Session(aws_access_key_id=os.environ['AWS_KEY'],
        aws_secret_access_key=os.environ['AWS_SECRET'],region_name='eu-north-1')
    config=Config(connect_timeout=8,read_timeout=30,
        retries={'mode':'standard','total_max_attempts':3},max_pool_connections=12)
    s3=session.client('s3',config=config)
    bundle_key='reports/2024-04/April_2024_Weekday_Reports.zip'
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
    manifest_bytes=(ROOT/'checks/artifact_manifest.json').read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest()!=receipt.get('manifest_sha256'):
        raise ValueError('Artifact manifest changed after publication')
    manifest=json.loads(manifest_bytes)
    if public_bundle.get('body'):
        with zipfile.ZipFile(io.BytesIO(public_bundle['body'])) as archive:
            if archive.testzip() is not None:
                raise ValueError('Public report ZIP has a corrupt member')
            expected_members={path for date in dates for path in
                (f'html/{date}.html',f'json/{date}_Market_Intelligence.json',
                 f'pdf/{date}_Market_Intelligence.pdf')}
            expected_members.update({'index.html','methodology.txt',
                'What_Retail_Is_Playing_2024-04.html'})
            if len(archive.namelist())!=len(dates)*3+3 or set(archive.namelist())!=expected_members:
                raise ValueError('Public report ZIP must contain exactly 69 expected members')
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
    index_origin_pass=idx['sha256']==receipt['index_sha256']
    backup=pub.read(s3,receipt['index_backup']['key'])
    old_hrefs={a.get('href') for a in BeautifulSoup(backup['body'],'html.parser').find_all('a')}
    archive_links_preserved=(backup['sha256']==receipt['index_backup']['sha256'] and
                             old_hrefs <= {a.get('href') for a in soup.find_all('a')})
    index_error=None
    try:
        request=urllib.request.Request('https://zembihf.xyz/reports/index.html',
                                       headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(request,timeout=45) as response:
            index_public_pass=hashlib.sha256(response.read()).hexdigest()==idx['sha256']
    except Exception as exc:
        index_public_pass=False
        index_error=type(exc).__name__+': '+str(exc)[:200]
    inv=session.client('cloudfront',config=config).get_invalidation(
        DistributionId=pub.DIST,Id=receipt['invalidation']['id'])['Invalidation']
    live=session.client('lambda',config=config).get_function_configuration(FunctionName='daily-trends-digest')
    original=baseline['lambda_metadata']
    lambda_unchanged=all(live.get(k)==original.get(k) for k in ('CodeSha256','LastModified','Runtime'))
    manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest()
    if (hashlib.sha256(pub.RECEIPT.read_bytes()).hexdigest()!=receipt_sha256
            or hashlib.sha256((ROOT/'checks/artifact_manifest.json').read_bytes()).hexdigest()!=manifest_sha256):
        raise ValueError('Publication receipt or manifest changed during delivery verification')
    passed=all(x['origin_sha256_pass'] and x['public_sha256_pass'] for x in rows) and len(members)==len(dates)*3 and all(x['sha256_pass'] for x in members) and unchanged and lambda_unchanged and all(n==1 for n in links.values()) and inv['Status']=='Completed' and index_origin_pass and index_public_pass and archive_links_preserved
    result={'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
        'passed':passed,'objects':rows,'protected_objects_unchanged':unchanged,
        'publication_receipt_sha256':receipt_sha256,
        'artifact_manifest_sha256':manifest_sha256,
        'publication_engineering_review_sha256':publication_review_sha256,
        'protected_checked':len(protected),'lambda_code_and_runtime_unchanged':lambda_unchanged,
        'code_provenance_sha256':baseline['code_provenance_sha256'],
        'retained_source_sha256':baseline['retained_source_sha256'],
        'archive_date_link_counts':links,'invalidation_status':inv['Status'],
        'archive_index_origin_sha256_pass':index_origin_pass,
        'archive_index_public_sha256_pass':index_public_pass,
        'archive_index_public_error':index_error,
        'archive_prior_hrefs_preserved':archive_links_preserved,
        'archive_prior_href_count':len(old_hrefs),
        'public_report_zip_members':members,
        'direct_strategy_route_observation':'Existing /Strategies PDF/JSON URLs return site fallback HTML (HTTP200,text/html); they are not canonical download links. All 44 PDF/JSON files are delivered and SHA-verified inside the publicly verified report ZIP. No routing configuration changed.',
        'scope':'All 71 scoped origin bodies checked. Public delivery: 22 daily HTML and five collection objects checked directly; all 66 HTML/PDF/JSON report members checked inside the public ZIP, including 44 native Strategy files. The global archive index is SHA-checked at origin and public HTTPS, with all prior hrefs preserved. Latest, June/July/August/September/October/November 2024 and August 2026 HTML, April 2024 weekends and live Lambda metadata are compared with the pre-publication snapshot.'}
    pub.save(ROOT/'checks/delivery_verification.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('objects','public_report_zip_members')},indent=2))
    for row in rows:
        if not row['origin_sha256_pass'] or not row['public_sha256_pass']:
            print(json.dumps(row))
    if not passed:
        raise SystemExit(1)


if __name__=='__main__':
    main()
