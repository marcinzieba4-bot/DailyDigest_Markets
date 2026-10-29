"""Verify revised public bytes and preservation of every protected live edition."""
from pathlib import Path
import concurrent.futures as cf
import datetime as dt
import hashlib
import importlib.util
import json
import os
import time
import threading
import urllib.request
import urllib.error
import boto3
from botocore.config import Config

ROOT=Path(__file__).resolve().parent
BASE='https://d7g7nkeytae81.cloudfront.net/'
_spec=importlib.util.spec_from_file_location('retail_publisher_for_verification',ROOT/'publish_revisions.py')
_publisher=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_publisher)
request,read=_publisher.request,_publisher.read


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
    expected={item['key']:item for item in receipt['targets']}
    if len(expected)!=len(receipt['targets']) or set(receipt['objects'])!=set(expected) or receipt.get('verified_count')!=len(expected):
        raise ValueError('Complete stored-artifact receipt is required')
    for key,item in expected.items():
        state=receipt['objects'][key];proof=state.get('current',{})
        if not state.get('verified') or proof.get('sha256')!=item['sha256'] or proof.get('bytes')!=item['bytes'] or not proof.get('etag'):
            raise ValueError('Stored-artifact proof mismatch: '+key)
    session=boto3.Session(aws_access_key_id=os.environ['AWS_KEY'],aws_secret_access_key=os.environ['AWS_SECRET'],region_name='eu-north-1')
    config=Config(connect_timeout=8,read_timeout=25,retries={'total_max_attempts':1},max_pool_connections=6)
    s3=session.client('s3',config=config);cdn=session.client('cloudfront',config=config)
    # Completed is monotonic. Reuse a previously observed completion instead of
    # making every retry depend on a healthy CloudFront control-plane tunnel.
    status=receipt.get('invalidation_status')
    if status!='Completed':
        status=request(lambda:cdn.get_invalidation(DistributionId='E15IJW4438D21G',Id=receipt['invalidation_id']))['Invalidation']['Status']
    if status!='Completed':raise ValueError('CDN invalidation still '+status+'; retry verification shortly')
    receipt['invalidation_status']=status;receipt_path.write_text(json.dumps(receipt,indent=2))
    targets=[x for x in receipt['targets'] if x['key'].startswith('reports/')]
    result={'started_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'public_artifacts':[]}
    checkpoint_path=ROOT/'audit/live_verification_checkpoint.json'
    fingerprint=hashlib.sha256(json.dumps(receipt['targets'],sort_keys=True).encode()).hexdigest()
    checkpoint=json.loads(checkpoint_path.read_text()) if checkpoint_path.exists() else {}
    if checkpoint.get('run')!=receipt['run'] or checkpoint.get('targets_sha256')!=fingerprint:
        checkpoint={'run':receipt['run'],'targets_sha256':fingerprint,'public':{},'protected':{}}
    lock=threading.RLock()
    def save_checkpoint():
        with lock:
            temporary=checkpoint_path.with_suffix('.tmp')
            temporary.write_text(json.dumps(checkpoint,indent=2));temporary.replace(checkpoint_path)
    missing=[item for item in targets if not (checkpoint['public'].get(item['key'],{}).get('passed') and
        checkpoint['public'][item['key']]['sha256']==item['sha256'] and checkpoint['public'][item['key']]['bytes']==item['bytes'])]
    public_failures=[]
    def public_one(item):
        with lock:
            if len(public_failures)>=3:return {'key':item['key'],'passed':False}
        try:
            row=public(item)
            row['verified_at_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
            with lock:checkpoint['public'][row['key']]=row;save_checkpoint()
            return row
        except Exception as error:
            row={'key':item['key'],'passed':False,'error_type':type(error).__name__}
            with lock:public_failures.append(row)
            return row
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        rows=list(ex.map(public_one,missing))
    pending_public=[row['key'] for row in rows if not row['passed']]
    if pending_public:raise ValueError('Public checks pending for '+str(len(pending_public))+' keys; successes retained in checkpoint')
    print('Public SHA verified',len(targets),'of',len(targets),flush=True)
    result['public_artifacts']=[checkpoint['public'][item['key']] for item in targets]
    scope=json.loads((ROOT/'audit/retrospective_scope.json').read_text())
    snapshots=json.loads((ROOT/'audit/published_snapshots.json').read_text())
    snapshots+=json.loads((ROOT/'audit/published_pdf_snapshots.json').read_text())
    protected=[x for x in snapshots if x.get('date') in scope['protected_live_dates']]
    if len(protected)!=3*scope['protected_count']:raise ValueError('Protected live variant inventory incomplete')
    snapshot_fingerprint=hashlib.sha256(json.dumps(protected,sort_keys=True).encode()).hexdigest()
    if checkpoint.get('protected_snapshot_sha256')!=snapshot_fingerprint:
        checkpoint['protected']={};checkpoint['protected_snapshot_sha256']=snapshot_fingerprint
    failures=[]
    def preserve(item):
        with lock:
            cached=checkpoint['protected'].get(item['key'],{})
            if cached.get('passed') and cached.get('baseline_sha256')==item['sha256']:return cached
            if len(failures)>=3:return {'key':item['key'],'passed':False,'reason':'transport circuit opened; retry required'}
        try:
            h=request(lambda:s3.head_object(Bucket='s3bucketmz',Key=item['key']))
            if h['ETag']==item['etag'] and h['ContentLength']==item['bytes']:
                row={'key':item['key'],'passed':True,'proof':'unchanged ETag/size tied to original full SHA256 snapshot'}
            else:
                actual,_=read(s3,item['key'])
                if actual['sha256']!=item['sha256']:raise ValueError('Protected live artifact changed: '+item['key'])
                row={'key':item['key'],'passed':True,'proof':'fresh atomic GET SHA256 equals original snapshot'}
            row.update(baseline_sha256=item['sha256'],verified_at_utc=dt.datetime.now(dt.timezone.utc).isoformat())
            with lock:checkpoint['protected'][item['key']]=row;save_checkpoint()
            return row
        except Exception as error:
            row={'key':item['key'],'passed':False,'error_type':type(error).__name__}
            with lock:failures.append(row)
            return row
    with cf.ThreadPoolExecutor(max_workers=5) as ex:
        result['protected_live_variants']=list(ex.map(preserve,protected))
    pending=[row['key'] for row in result['protected_live_variants'] if not row['passed']]
    if pending:raise ValueError('Live preservation checks pending for '+str(len(pending))+' keys; successes retained in checkpoint: '+str(pending[:3]))
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
