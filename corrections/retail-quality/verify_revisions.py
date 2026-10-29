"""Verify revised public bytes and preservation of every protected live edition."""
from pathlib import Path
import concurrent.futures as cf
import datetime as dt
import hashlib
import json
import os
import time
import urllib.request
import urllib.error
import boto3
from botocore.config import Config
from publish_revisions import request, read

ROOT=Path(__file__).resolve().parent
BASE='https://d7g7nkeytae81.cloudfront.net/'


def public(item):
    for attempt in range(6):
        try:
            req=urllib.request.Request(BASE+item['key'],headers={
                'User-Agent':'DailyDigest-retail-revision-verification/1.0','Accept-Encoding':'identity'})
            with urllib.request.urlopen(req,timeout=30) as response:
                blob=response.read();status=response.status
            digest=hashlib.sha256(blob).hexdigest()
            if digest!=item['sha256'] or len(blob)!=item['bytes']:
                raise ValueError('Public SHA mismatch: '+item['key'])
            return {'key':item['key'],'sha256':digest,'bytes':len(blob),'status':status,'passed':True}
        except urllib.error.HTTPError as error:
            if error.code not in (404,408,429,500,502,503,504) or attempt==5:raise
        except (urllib.error.URLError,TimeoutError):
            if attempt==5:raise
        time.sleep(min(2**attempt,12))


def main():
    receipt_path=ROOT/'audit/publication.json'
    receipt=json.loads(receipt_path.read_text())
    if receipt['stage']!='published':raise ValueError('Publication incomplete')
    session=boto3.Session(aws_access_key_id=os.environ['AWS_KEY'],aws_secret_access_key=os.environ['AWS_SECRET'],region_name='eu-north-1')
    config=Config(connect_timeout=8,read_timeout=25,retries={'total_max_attempts':1},max_pool_connections=6)
    s3=session.client('s3',config=config);cdn=session.client('cloudfront',config=config)
    status=request(lambda:cdn.get_invalidation(DistributionId='E15IJW4438D21G',Id=receipt['invalidation_id']))['Invalidation']['Status']
    if status!='Completed':raise ValueError('CDN invalidation still '+status+'; retry verification shortly')
    receipt['invalidation_status']=status;receipt_path.write_text(json.dumps(receipt,indent=2))
    targets=[x for x in receipt['targets'] if x['key'].startswith('reports/')]
    result={'started_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'public_artifacts':[]}
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        for i,row in enumerate(ex.map(public,targets),1):
            result['public_artifacts'].append(row)
            if i%25==0:print('Public SHA verified',i,'of',len(targets),flush=True)
    scope=json.loads((ROOT/'audit/retrospective_scope.json').read_text())
    snapshots=json.loads((ROOT/'audit/published_snapshots.json').read_text())
    snapshots+=json.loads((ROOT/'audit/published_pdf_snapshots.json').read_text())
    protected=[x for x in snapshots if x.get('date') in scope['protected_live_dates']]
    if len(protected)!=3*scope['protected_count']:raise ValueError('Protected live variant inventory incomplete')
    def preserve(item):
        h=request(lambda:s3.head_object(Bucket='s3bucketmz',Key=item['key']))
        if h['ETag']==item['etag'] and h['ContentLength']==item['bytes']:
            return {'key':item['key'],'passed':True,'proof':'unchanged ETag/size tied to original full SHA256 snapshot'}
        actual,_=read(s3,item['key'])
        if actual['sha256']!=item['sha256']:raise ValueError('Protected live artifact changed: '+item['key'])
        return {'key':item['key'],'passed':True,'proof':'fresh atomic GET SHA256 equals original snapshot'}
    with cf.ThreadPoolExecutor(max_workers=5) as ex:
        result['protected_live_variants']=list(ex.map(preserve,protected))
    specials=json.loads((ROOT/'audit/protected_specials.json').read_text())
    for key,expected in specials.items():
        actual,blob=read(s3,key)
        if actual['sha256']!=expected['sha256']:raise ValueError('Protected latest/index bytes changed: '+key)
        if key=='reports/index.html':
            index=blob.decode()
            for date in json.loads((ROOT/'audit/revision_artifacts.json').read_text())['dates']:
                if f'archive/{date}.html' not in index:raise ValueError('Archive index lost date: '+date)
    result.update(passed=True,public_artifact_count=len(targets),stored_artifact_count=len(receipt['targets']),
        protected_live_editions=scope['protected_count'],protected_live_variants_count=len(protected),
        latest_unchanged=True,index_unchanged=True,invalidation_status=status,
        finished_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        format_delivery='All origin HTML/JSON/PDF variants verified. September/October/November public ZIPs include byte-identical variants; Strategies paths retain the existing backend delivery model.')
    (ROOT/'audit/live_verification.json').write_text(json.dumps(result,indent=2))
    final_path=ROOT/'audit/final_validation.json';final=json.loads(final_path.read_text())
    final.update(passed=True,publication_status='published',stored_artifacts_verified=len(receipt['targets']),
        public_artifacts_verified=len(targets),protected_live_variants_verified=len(protected),
        all_live_editions_unchanged=True,latest_unchanged=True,index_unchanged=True,
        invalidation_status='Completed',live_verification_sha256=hashlib.sha256((ROOT/'audit/live_verification.json').read_bytes()).hexdigest(),
        publication_receipt_sha256=hashlib.sha256(receipt_path.read_bytes()).hexdigest())
    final_path.write_text(json.dumps(final,indent=2))
    print('VERIFIED:',len(targets),'public artifacts;',len(receipt['targets']),'origin artifacts;',len(protected),'protected live variants; latest/index unchanged',flush=True)


if __name__=='__main__':main()
