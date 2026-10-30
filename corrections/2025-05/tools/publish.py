"""Publish the complete validated May month; dry-run unless --go.

Uses runtime AWS_KEY/AWS_SECRET bindings through the ordinary configured SDK.
Does not invoke Lambda or any email/Telegram channel. Backs up replaced objects,
preserves concurrent archive additions, and never writes reports/latest.html.
"""
from pathlib import Path
import argparse
import copy
import time
import datetime as dt
import hashlib
import importlib.util
import json
import os
import sys
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, ConnectionError, HTTPClientError
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parent.parent
B='s3bucketmz';DIST='E15IJW4438D21G'
DATES=[dt.date(2025,5,n).isoformat() for n in range(1,32) if dt.date(2025,5,n).weekday()<5]
# One SDK attempt; bounded retries below cover the complete operation, including body reads.
CONFIG=Config(connect_timeout=8,read_timeout=20,retries={'total_max_attempts':1,'mode':'standard'},max_pool_connections=2)
MAX_ATTEMPTS=3
BACKOFF_BASE=1.0
BACKOFF_CAP=4.0
DEST=ROOT/'checks'/'publication.json'

def sha(blob):return hashlib.sha256(blob).hexdigest()

def head(s3,key):
    try:return s3.head_object(Bucket=B,Key=key)
    except ClientError as e:
        if e.response['Error']['Code'] in ['404','NoSuchKey','NotFound']:return None
        raise

def snapshot(s3,keys):
    out={}
    for k in keys:
        h=head(s3,k);out[k]={'etag':h['ETag'],'bytes':h['ContentLength']} if h else None
    return out

def plan():
    review_spec=importlib.util.spec_from_file_location('may_review_gate',ROOT/'tools'/'review_gate.py')
    review_module=importlib.util.module_from_spec(review_spec);review_spec.loader.exec_module(review_module)
    review_module.require_review()
    retail_quality_gate=importlib.util.spec_from_file_location('retail_quality_gate',ROOT.parent/'retail-quality'/'retail_quality.py')
    retail_quality_module=importlib.util.module_from_spec(retail_quality_gate);retail_quality_gate.loader.exec_module(retail_quality_module)
    retail_quality_module.require_review(ROOT)
    manifest=json.loads((ROOT/'checks'/'artifact_manifest.json').read_text())
    if manifest.get('dates')!=DATES or not manifest.get('complete_month'):raise ValueError(f'Complete {len(DATES)}-date May month required')
    if [r['date'] for r in manifest.get('reports',[])]!=DATES:raise ValueError('Missing/duplicate report artifacts')
    expected_collection={'2025-05.html','methodology.txt','May_2025_Weekday_Reports.zip'}
    if set(manifest.get('collection',{}))!=expected_collection:raise ValueError('May collection, methodology and full report ZIP required')
    sp=importlib.util.spec_from_file_location('verify',ROOT/'tools'/'verify.py')
    verify=importlib.util.module_from_spec(sp);sp.loader.exec_module(verify)
    out=[]
    for row in manifest['reports']:
        d=row['date'];spec=ROOT/'specs'/f'{d}.json'
        if set(row.get('files',{}))!={'html','json','pdf'}:raise ValueError('HTML, JSON and PDF required for '+d)
        if sha(spec.read_bytes())!=row['spec_sha256']:raise ValueError('Spec changed after artifact checks: '+d)
        for field,path in [('card_sha256',ROOT/'cards'/f'{d}.json'),('feed_sha256',ROOT/'feeds'/f'{d}.json.gz'),('renderer_sha256',ROOT/'tools'/'render.py'),('builder_sha256',ROOT/'tools'/'build_artifacts.py'),('timing_exceptions_sha256',ROOT/'audit/canonical_source_exceptions.json')]:
            if sha(path.read_bytes())!=row[field]:raise ValueError('Artifact input changed: '+str(path))
        fails,*_=verify.verify(d)
        if fails:raise ValueError('Validation no longer passes: '+d+' '+repr(fails))
        for ext,f in row['files'].items():
            p=ROOT/f['path'];blob=p.read_bytes()
            if sha(blob)!=f['sha256'] or len(blob)!=f['bytes']:raise ValueError('Artifact changed after checks: '+str(p))
            key={'html':f'reports/archive/{d}.html','json':f'Strategies/json/{d}_Market_Intelligence.json','pdf':f'Strategies/{d}_Market_Intelligence.pdf'}[ext]
            ct={'html':'text/html; charset=utf-8','json':'application/json','pdf':'application/pdf'}[ext]
            out.append({'key':key,'path':f['path'],'sha256':f['sha256'],'bytes':f['bytes'],'content_type':ct,'date':d})
    for name,f in manifest['collection'].items():
        p=ROOT/f['path'];blob=p.read_bytes()
        if sha(blob)!=f['sha256'] or len(blob)!=f['bytes']:raise ValueError('Collection changed')
        key='reports/'+name if name.endswith('.html') else 'reports/2025-05/'+name
        out.append({'key':key,'path':f['path'],'sha256':f['sha256'],'bytes':f['bytes'],'content_type':('text/html; charset=utf-8' if name.endswith('.html') else 'application/zip' if name.endswith('.zip') else 'text/plain; charset=utf-8'),'date':None})
    expected=len(manifest['reports'])*3+len(manifest['collection'])
    if len(out)!=expected or len({item['key'] for item in out})!=expected:raise ValueError('Missing or duplicate publication targets')
    return out

def manifest_statistics():
    manifest=json.loads((ROOT/'checks'/'artifact_manifest.json').read_text())
    reports=manifest['reports']
    return {'report_count':len(reports),'daily_artifact_count':sum(len(row['files']) for row in reports),
            'collection_artifact_count':len(manifest['collection']),
            'total_words':sum(row['words'] for row in reports),'total_pdf_pages':sum(row['pdf_pages'] for row in reports),
            'distinct_citations_per_report':{row['date']:row['distinct_sources'] for row in reports}}

def merge_index(blob):
    soup=BeautifulSoup(blob,'html.parser');ul=soup.find('ul')
    if ul is None:raise ValueError('Archive index structure missing')
    old={a.get('href') for a in soup.find_all('a')}
    for d in DATES:
        href=f'archive/{d}.html'
        if href not in old:
            li=soup.new_tag('li');a=soup.new_tag('a',href=href);a.string=d;li.append(a);ul.append(li)
    import re
    rows=[]
    for li in ul.find_all('li',recursive=False):
        a=li.find('a');m=re.fullmatch(r'archive/(\d{4}-\d{2}-\d{2})\.html',a.get('href','')) if a else None
        if m:rows.append((m.group(1),li))
    for _,li in sorted(rows,reverse=True):li.extract();ul.append(li)
    if not soup.find('a',href='2025-05.html'):
        p=soup.new_tag('p');a=soup.new_tag('a',href='2025-05.html');a.string=f'May 2025 — {len(DATES)} weekday briefings & download';p.append(a);ul.insert_before(p)
    new={a.get('href') for a in soup.find_all('a')}
    if not old<=new:raise ValueError('Would lose an existing archive link')
    for d in DATES:
        if len(soup.find_all('a',href=f'archive/{d}.html'))!=1:raise ValueError('Missing/duplicate archive row: '+d)
    return str(soup).encode()

def utc():return dt.datetime.now(dt.timezone.utc).isoformat()

def save_json(path,data):
    # A receipt must survive interruption between two confirmed uploads.
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(data,indent=2));temporary.replace(path)

def protected_keys():
    weekends=[dt.date(2025,5,n).isoformat() for n in range(1,32) if dt.date(2025,5,n).weekday()>4]
    return ['reports/latest.html']+[k for d in weekends for k in [f'reports/archive/{d}.html',f'Strategies/json/{d}_Market_Intelligence.json',f'Strategies/{d}_Market_Intelligence.pdf']]

def error_summary(error):
    response=getattr(error,'response',{}) or {}
    metadata=response.get('ResponseMetadata',{})
    request_id=metadata.get('RequestId')
    return {'exception':type(error).__name__,'http_status':metadata.get('HTTPStatusCode'),
            'aws_error_code':response.get('Error',{}).get('Code'),'aws_request_id':request_id,
            'classification':('upstream_transport_unavailable' if metadata.get('HTTPStatusCode') in (502,503,504) and not request_id else
                              'transport_or_connection_error' if isinstance(error,(ConnectionError,HTTPClientError)) else 'operation_error')}

def transient(error):
    if isinstance(error,ClientError):
        r=error.response
        return r.get('ResponseMetadata',{}).get('HTTPStatusCode') in (408,429,500,502,503,504) or r.get('Error',{}).get('Code') in ('SlowDown','RequestTimeout','ServiceUnavailable','InternalError','Throttling','ThrottlingException')
    # Includes proxy, endpoint, timeout, TLS and streamed-response failures. It does
    # not include validation errors, IAM denials or conditional-write conflicts.
    return isinstance(error,(ConnectionError,HTTPClientError)) or type(error).__name__ in ('ResponseStreamingError','IncompleteReadError')

def request(operation,fn,receipt=None,save=None,key=None):
    for attempt in range(1,MAX_ATTEMPTS+1):
        if receipt is not None:
            receipt['last_attempt']={'operation':operation,'key':key,'attempt':attempt,'at_utc':utc()}
            if save:save()
        try:return fn()
        except Exception as error:
            if receipt is not None:
                receipt['last_error']={**error_summary(error),'operation':operation,'key':key,'attempt':attempt,'at_utc':utc()}
                if save:save()
            if not transient(error) or attempt==MAX_ATTEMPTS:raise
            delay=min(BACKOFF_BASE*(2**(attempt-1)),BACKOFF_CAP)
            print(f'Retry {operation} {key or ""}: attempt {attempt}/{MAX_ATTEMPTS}, waiting {delay:g}s',flush=True)
            time.sleep(delay)

def validate_resume(receipt,targets):
    if receipt.get('dates')!=DATES or receipt.get('targets')!=targets:
        raise ValueError('Resume targets differ from the original run; retain its exact checked artifacts')
    run=receipt.get('run')
    if not isinstance(run,str) or not __import__('re').fullmatch(r'\d{8}T\d{6}Z',run):raise ValueError('Invalid original publication run')
    if receipt.get('backup_prefix')!=f'reports/_retrospective_backup/may-2025-weekdays/{run}/':raise ValueError('Invalid original backup prefix')
    stage=receipt.get('stage')
    if stage not in ('backup','upload','verify','index','invalidate','published'):
        raise ValueError('Unknown publication stage')
    protected=receipt.get('protected_before',{})
    # A failed initial HeadBucket/snapshot has not written any backup or target.
    # Once backup work starts, its original protected snapshot is immutable.
    if set(protected)!=set(protected_keys()):
        untouched=stage=='backup' and not protected and not receipt.get('backups') and not receipt.get('backup_intents')
        if not untouched:raise ValueError('Original protected snapshot missing/incomplete')
    if receipt.get('latest_write_performed') is not False:raise ValueError('Unexpected latest-report write flag')
    keys={x['key'] for x in targets}|{'reports/index.html'};seen=set()
    for backup in receipt.get('backups',[]):
        key=backup.get('key')
        if key not in keys or key in seen or backup.get('backup_key')!=receipt['backup_prefix']+key:
            raise ValueError('Invalid/duplicate original backup record')
        if not backup.get('etag') or not isinstance(backup.get('bytes'),int):raise ValueError('Incomplete original backup record')
        seen.add(key)
    for key,intent in receipt.get('backup_intents',{}).items():
        if key not in keys:raise ValueError('Unknown original backup intent')
        if intent is None:continue
        if (intent.get('key')!=key or intent.get('backup_key')!=receipt['backup_prefix']+key
                or not intent.get('etag') or not isinstance(intent.get('bytes'),int)):
            raise ValueError('Incomplete original backup intent')
        recorded=next((x for x in receipt.get('backups',[]) if x['key']==key),None)
        if recorded is not None and recorded!=intent:raise ValueError('Backup intent differs from original record')
    return receipt

def cached_confirmation(receipt,item):
    known=receipt.get('confirmed_targets',{}).get(item['key'],{})
    return known if known.get('sha256')==item['sha256'] and known.get('bytes')==item['bytes'] and known.get('etag') else None

def forget_confirmation(receipt,key,save):
    if key in receipt.get('confirmed_targets',{}):
        receipt['confirmed_targets'].pop(key)
        receipt['confirmed_count']=len(receipt['confirmed_targets']);save()

def remote_state(s3,item,receipt,save):
    key=item['key'];known=cached_confirmation(receipt,item)
    if known:
        h=request('HeadObject/revalidate',lambda:head(s3,key),receipt,save,key)
        if h is None:
            forget_confirmation(receipt,key,save);return None,False
        if h['ETag']==known['etag'] and h['ContentLength']==item['bytes']:
            # This version's SHA was already checked. Its unchanged strong object
            # ETag and length bind the current object to that exact byte proof.
            h['_verification_method']='unchanged ETag and size';return h,True
        forget_confirmation(receipt,key,save)
    # An unconfirmed version needs one atomic GET. Its ETag, metadata, length and
    # body all describe that response's object version, so HEAD+IfMatch is redundant.
    def read():
        try:r=s3.get_object(Bucket=B,Key=key)
        except ClientError as error:
            if error.response['Error']['Code'] in ('404','NoSuchKey','NotFound'):return None,False
            raise
        h={k:r[k] for k in ('ETag','ContentLength','Metadata','VersionId') if k in r}
        try:
            if h['ContentLength']!=item['bytes']:return h,False
            blob=r['Body'].read()
        finally:r['Body'].close()
        matching=len(blob)==item['bytes'] and sha(blob)==item['sha256']
        if matching:h['_verification_method']='atomic GET SHA256'
        return h,matching
    return request('GetObject/atomic-verify',read,receipt,save,key)

def confirm(receipt,item,h,source,save):
    known=cached_confirmation(receipt,item);now=utc()
    method=h.get('_verification_method','atomic GET SHA256')
    proof_time=(known.get('sha_verified_at_utc',known.get('verified_at_utc')) if known and method=='unchanged ETag and size' else now)
    receipt.setdefault('confirmed_targets',{})[item['key']]={'sha256':item['sha256'],'bytes':item['bytes'],
            'etag':h['ETag'],'verified_at_utc':now,'sha_verified_at_utc':proof_time,'verification_method':method,'source':source}
    receipt['confirmed_count']=len(receipt['confirmed_targets'])
    save()

def publish_targets(s3,targets,receipt,save):
    originals={x['key']:x for x in receipt['backups']}
    receipt['stage']='upload';save()
    known_count=sum(bool(cached_confirmation(receipt,item)) for item in targets)
    if known_count:print('Retaining',known_count,'previous SHA proofs; unchanged versions will be revalidated before index merge',flush=True)
    for item in targets:                           # intentionally sequential: one remote operation at a time
        # Make new progress first after a transport interruption. Previously hashed
        # targets need no writes; revalidate them at the final complete-set gate.
        if cached_confirmation(receipt,item):continue
        h,matching=remote_state(s3,item,receipt,save)
        if matching:
            confirm(receipt,item,h,'matching object skipped',save)
            print('Confirmed',receipt['confirmed_count'],'of',len(targets),item['key'],flush=True);continue
        # Do not overwrite another publisher's intervening change. An unmatched
        # object must be the backed-up original or a partial object from this run.
        if h is not None:
            original=originals.get(item['key'])
            own=h.get('Metadata',{}).get('retrospective-run')==receipt['run']
            untouched=original and h['ETag']==original['etag'] and h['ContentLength']==original['bytes']
            if not own and not untouched:raise ValueError('Concurrent target change; refusing overwrite: '+item['key'])
        blob=(ROOT/item['path']).read_bytes()
        if len(blob)!=item['bytes'] or sha(blob)!=item['sha256']:raise ValueError('Local artifact changed: '+item['path'])
        metadata={'sha256':item['sha256'],'retrospective-run':receipt['run']}
        if item['date']:metadata['news-cutoff-utc']=item['date']+'T00:00:00Z'
        conditions={'IfMatch':h['ETag']} if h else {'IfNoneMatch':'*'}
        # If a transport retry follows a successful conditional PUT, its 412 is
        # ambiguous, so verify the expected bytes before deciding it failed.
        try:
            request('PutObject',lambda:s3.put_object(Bucket=B,Key=item['key'],Body=blob,ContentType=item['content_type'],Metadata=metadata,**conditions),receipt,save,item['key'])
        except ClientError as error:
            if error.response['Error']['Code'] not in ('412','PreconditionFailed','ConditionalRequestConflict','409'):raise
        after,matching=remote_state(s3,item,receipt,save)
        if not matching:raise ValueError('Upload verification failed: '+item['key'])
        uploaded=receipt.setdefault('uploaded',[])
        if item['key'] not in uploaded:uploaded.append(item['key'])
        confirm(receipt,item,after,'uploaded and verified',save)
        print('Confirmed',receipt['confirmed_count'],'of',len(targets),item['key'],flush=True)
    receipt['stage']='verify';save()
    # Gate index changes on complete-set revalidation. Every SHA proof must still
    # identify the current ETag/length; changed versions are downloaded and hashed.
    for item in targets:
        h,matching=remote_state(s3,item,receipt,save)
        if not matching:raise ValueError('Final target verification failed: '+item['key'])
        confirm(receipt,item,h,'final complete-set verification',save)
    receipt['all_targets_verified_at_utc']=utc();receipt['stage']='index';save()

def verify_original_backups(s3,receipt,save):
    for backup in receipt['backups']:
        h=request('HeadObject/original-backup',lambda:head(s3,backup['backup_key']),receipt,save,backup['backup_key'])
        if not h or h['ETag']!=backup['etag'] or h['ContentLength']!=backup['bytes']:
            raise ValueError('Original backup is missing or changed: '+backup['key'])

def complete_backup_phase(s3,targets,receipt,save):
    """Resume only pre-upload work, preserving every original object version.

    Persist source ETags before copying. If a copy succeeds but its response or
    verification read fails, the next attempt recognizes the already copied
    version rather than copying a possibly changed source over it.
    """
    if receipt.get('stage')!='backup':raise ValueError('Backup phase cannot run after target writes')
    protected=protected_keys()
    if receipt.get('protected_before'):
        current=request('Snapshot/protected',lambda:snapshot(s3,protected),receipt,save)
        if any(current[k]!=receipt['protected_before'][k] for k in protected if k!='reports/latest.html'):
            raise ValueError('Weekend objects changed since the original run; investigate before resuming')
    else:
        if receipt.get('backups') or receipt.get('backup_intents'):
            raise ValueError('Cannot reconstruct the protected snapshot after backup writes')
        receipt['protected_before']=request('Snapshot/protected',lambda:snapshot(s3,protected),receipt,save)
        save()
    verify_original_backups(s3,receipt,save)
    recorded={x['key']:x for x in receipt['backups']}
    intents=receipt.setdefault('backup_intents',{})
    for item in targets+[{'key':'reports/index.html'}]:
        key=item['key']
        if key in recorded:continue
        if key not in intents:
            h=request('HeadObject/original',lambda:head(s3,key),receipt,save,key)
            intents[key]=({'key':key,'backup_key':receipt['backup_prefix']+key,
                           'etag':h['ETag'],'bytes':h['ContentLength']} if h else None)
            save()
        intent=intents[key]
        if intent is None:continue
        def ensure_backup():
            bh=head(s3,intent['backup_key'])
            if bh is None:
                s3.copy_object(Bucket=B,Key=intent['backup_key'],CopySource={'Bucket':B,'Key':key},CopySourceIfMatch=intent['etag'])
                bh=head(s3,intent['backup_key'])
            if not bh or bh['ContentLength']!=intent['bytes'] or bh['ETag']!=intent['etag']:
                raise ValueError('Original backup conflicts with its persisted source version: '+key)
            return bh
        request('EnsureOriginalBackup',ensure_backup,receipt,save,intent['backup_key'])
        receipt['backups'].append(copy.deepcopy(intent));recorded[key]=intent
        save()
    receipt['backup_phase_completed_at_utc']=utc();receipt['stage']='upload';save()

def execute(s3,cloudfront,targets,receipt,save,resume):
    protected=protected_keys()
    request('HeadBucket',lambda:s3.head_bucket(Bucket=B),receipt,save)
    if resume and receipt.get('stage')!='backup':
        verify_original_backups(s3,receipt,save)
        current=request('Snapshot/protected',lambda:snapshot(s3,protected),receipt,save)
        if any(current[k]!=receipt['protected_before'][k] for k in protected if k!='reports/latest.html'):
            raise ValueError('Weekend objects changed since the original run; investigate before resuming')
    else:
        complete_backup_phase(s3,targets,receipt,save)
    publish_targets(s3,targets,receipt,save)
    for attempt in range(4):
        def read_index():
            r=s3.get_object(Bucket=B,Key='reports/index.html')
            try:return r['ETag'],r['Body'].read()
            finally:r['Body'].close()
        etag,old=request('GetObject/index',read_index,receipt,save,'reports/index.html');new=merge_index(old)
        checkpoint=receipt['backup_prefix']+'index-before-merge-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+str(attempt)+'.html'
        request('PutObject/index-checkpoint',lambda:s3.put_object(Bucket=B,Key=checkpoint,Body=old,ContentType='text/html; charset=utf-8',IfNoneMatch='*'),receipt,save,checkpoint)
        try:
            request('PutObject/index-merge',lambda:s3.put_object(Bucket=B,Key='reports/index.html',Body=new,ContentType='text/html; charset=utf-8',IfMatch=etag),receipt,save,'reports/index.html')
            receipt['index_sha256']=sha(new);save();break
        except ClientError as e:
            if e.response['Error']['Code'] not in ('412','PreconditionFailed'):raise
    else:raise ValueError('Concurrent archive updates: retry merge')
    receipt['protected_after']=request('Snapshot/protected',lambda:snapshot(s3,protected),receipt,save)
    receipt['weekends_unchanged']=all(receipt['protected_before'][k]==receipt['protected_after'][k] for k in protected if k!='reports/latest.html')
    receipt['latest_unchanged']=receipt['protected_before']['reports/latest.html']==receipt['protected_after']['reports/latest.html']
    if not receipt['weekends_unchanged']:raise ValueError('Weekend objects changed: investigate')
    receipt['stage']='invalidate';save()
    paths=['/'+x['key'] for x in targets]+['/reports/index.html']
    inv=request('CreateInvalidation',lambda:cloudfront.create_invalidation(DistributionId=DIST,InvalidationBatch={'Paths':{'Quantity':len(paths),'Items':paths},'CallerReference':'may-2025-'+receipt['run']})['Invalidation'],receipt,save)
    receipt.update(stage='published',status='published',invalidation_id=inv['Id'],invalidation_status=inv['Status'],public_collection_url='https://d7g7nkeytae81.cloudfront.net/reports/2025-05.html')
    receipt.pop('last_error',None);save()
    print('Published',len(DATES),'reports; archive index merged; invalidation',inv['Id'],inv['Status'],flush=True)

def offline_self_test(targets):
    import io
    from unittest.mock import patch
    before=json.loads(DEST.read_text()) if DEST.exists() else None
    original={
        'run':'20000101T000000Z','dates':DATES,'targets':targets,'stage':'upload',
        'backup_prefix':'reports/_retrospective_backup/may-2025-weekdays/20000101T000000Z/',
        'protected_before':{key:None for key in protected_keys()},'backups':[],'latest_write_performed':False}
    original_before=copy.deepcopy(original)
    validate_resume(original,targets)
    assert original==original_before
    altered=copy.deepcopy(targets);altered[0]['sha256']='0'*64
    try:validate_resume(original,altered)
    except ValueError:pass
    else:raise AssertionError('Changed resume targets accepted')
    attempts=[];waits=[]
    unavailable=ClientError({'Error':{'Code':'503'},'ResponseMetadata':{'HTTPStatusCode':503}},'GetObject')
    with patch.object(time,'sleep',lambda delay:waits.append(delay)):
        def fail():attempts.append(1);raise unavailable
        try:request('offline-test',fail)
        except ClientError:pass
    assert len(attempts)==MAX_ATTEMPTS and len(waits)==MAX_ATTEMPTS-1 and all(0<=x<=BACKOFF_CAP for x in waits)
    denied=ClientError({'Error':{'Code':'AccessDenied'},'ResponseMetadata':{'HTTPStatusCode':403}},'GetObject')
    attempts=[]
    def deny():attempts.append(1);raise denied
    try:request('offline-test',deny)
    except ClientError:pass
    assert len(attempts)==1
    item=targets[0];blob=(ROOT/item['path']).read_bytes()
    def fixture():
        receipt=copy.deepcopy(original);receipt['confirmed_targets']={};receipt['confirmed_count']=0;receipt['uploaded']=[]
        return receipt
    class FakeS3:
        def __init__(self):self.object=None;self.puts=0;self.copies=0;self.gets=0;self.heads=0;self.etag='"test-etag"';self.metadata={'retrospective-run':original['run']}
        def metadata_response(self):
            if self.object is None:raise ClientError({'Error':{'Code':'404'}},'GetObject')
            return {'ETag':self.etag,'ContentLength':len(self.object),'Metadata':self.metadata}
        def head_object(self,**kw):self.heads+=1;return self.metadata_response()
        def get_object(self,**kw):
            self.gets+=1
            assert 'IfMatch' not in kw
            return {**self.metadata_response(),'Body':io.BytesIO(self.object)}
        def put_object(self,**kw):self.puts+=1;self.object=kw['Body'];self.metadata=kw.get('Metadata',{});return {}
        def copy_object(self,**kw):self.copies+=1;raise AssertionError('Resume attempted a new original backup')
    fake=FakeS3();fake.object=blob;receipt=fixture();snapshots=[]
    def save():snapshots.append(copy.deepcopy(receipt))
    publish_targets(fake,[item],receipt,save)
    assert fake.puts==0 and fake.copies==0 and fake.gets==1 and fake.heads==1
    proof=receipt['confirmed_targets'][item['key']]['sha_verified_at_utc'];download_count=fake.gets
    publish_targets(fake,[item],receipt,save)
    assert fake.gets==download_count and fake.heads==2 and receipt['confirmed_targets'][item['key']]['sha_verified_at_utc']==proof
    assert receipt['run']==original['run'] and receipt['backup_prefix']==original['backup_prefix'] and receipt['protected_before']==original['protected_before'] and receipt['backups']==original['backups']
    fake.etag='"changed-but-same-bytes"'
    publish_targets(fake,[item],receipt,save)
    assert fake.gets==download_count+1 and receipt['confirmed_targets'][item['key']]['etag']==fake.etag
    fake=FakeS3();receipt=fixture();snapshots=[]
    publish_targets(fake,[item],receipt,save)
    assert fake.puts==1 and fake.copies==0 and item['key'] in snapshots[-1]['confirmed_targets']
    foreign=FakeS3();foreign.object=b'x';foreign.etag='"foreign"';foreign.metadata={};receipt=fixture()
    try:publish_targets(foreign,[item],receipt,lambda:None)
    except ValueError:pass
    else:raise AssertionError('Concurrent foreign target was overwritten')
    assert foreign.puts==0
    class Interrupted(FakeS3):
        def get_object(self,**kw):
            if kw['Key']==targets[1]['key']:raise unavailable
            return super().get_object(**kw)
    interrupted=Interrupted();receipt=fixture();snapshots=[]
    with patch.object(time,'sleep',lambda _:None):
        try:publish_targets(interrupted,targets[:2],receipt,save)
        except ClientError:pass
        else:raise AssertionError('Transport interruption not surfaced')
    assert interrupted.puts==1 and receipt['stage']=='upload'
    assert item['key'] in snapshots[-1]['confirmed_targets'] and receipt['backups']==original['backups']
    corrupted=FakeS3();corrupted.object=b'x'*len(blob)
    _,matches=remote_state(corrupted,item,fixture(),lambda:None)
    assert not matches
    # A cached version changed by somebody else cannot pass the complete-set gate.
    changed=FakeS3();changed.object=b'x'*len(blob);changed.etag='"foreign"';changed.metadata={}
    receipt=fixture();receipt['confirmed_targets'][item['key']]={'sha256':item['sha256'],'bytes':item['bytes'],'etag':'"old-version"','verified_at_utc':utc()}
    try:publish_targets(changed,[item],receipt,lambda:None)
    except ValueError:pass
    else:raise AssertionError('Changed cached version passed final verification')
    assert item['key'] not in receipt['confirmed_targets'] and receipt['stage']=='verify' and changed.puts==0
    # A failure before the protected snapshot, an ambiguous successful copy,
    # and a later interrupted copy must all resume without recopying originals.
    def backup_fixture():
        result=copy.deepcopy(original);result['stage']='backup';result['backups']=[]
        result.pop('protected_before',None);result.pop('backup_intents',None)
        return result
    first,second=[x['key'] for x in targets[:2]]
    first_backup=original['backup_prefix']+first
    second_backup=original['backup_prefix']+second
    class BackupS3:
        def __init__(self):
            self.objects={key:{'ETag':'"original-'+str(i)+'"','ContentLength':100+i}
                          for i,key in enumerate([first,second,'reports/index.html','reports/latest.html'])}
            self.copies=[];self.failed_head_bucket=True
            self.fail_verification=True;self.verification_failures=0;self.blocked_copy=second_backup
        def head_bucket(self,**kw):
            if self.failed_head_bucket:raise unavailable
            return {}
        def head_object(self,**kw):
            key=kw['Key']
            if key==first_backup and key in self.objects and self.verification_failures:
                self.verification_failures-=1;raise unavailable
            if key not in self.objects:raise ClientError({'Error':{'Code':'404'}},'HeadObject')
            return copy.deepcopy(self.objects[key])
        def copy_object(self,**kw):
            key=kw['Key']
            if key==self.blocked_copy:raise unavailable
            source=self.objects[kw['CopySource']['Key']]
            if source['ETag']!=kw['CopySourceIfMatch']:raise ClientError({'Error':{'Code':'412'}},'CopyObject')
            self.objects[key]=copy.deepcopy(source);self.copies.append(key)
            if key==first_backup and self.fail_verification:
                self.fail_verification=False;self.verification_failures=MAX_ATTEMPTS
            return {}
    backup_s3=BackupS3();backup_receipt=backup_fixture();backup_snapshots=[]
    def save_backup():backup_snapshots.append(copy.deepcopy(backup_receipt))
    with patch.object(time,'sleep',lambda _:None):
        try:request('HeadBucket',lambda:backup_s3.head_bucket(Bucket=B),backup_receipt,save_backup)
        except ClientError:pass
        else:raise AssertionError('Initial HeadBucket failure not surfaced')
        validate_resume(backup_receipt,targets)
        assert not backup_receipt.get('protected_before') and not backup_receipt['backups']
        backup_s3.failed_head_bucket=False
        try:complete_backup_phase(backup_s3,targets[:2],backup_receipt,save_backup)
        except ClientError:pass
        else:raise AssertionError('Ambiguous backup verification failure not surfaced')
        protected_before=copy.deepcopy(backup_receipt['protected_before'])
        original_first=copy.deepcopy(backup_s3.objects[first_backup])
        assert backup_receipt['stage']=='backup' and not backup_receipt['backups']
        assert backup_s3.copies==[first_backup] and first in backup_receipt['backup_intents']
        # A newer source and latest edition cannot replace the saved original.
        backup_s3.objects[first]['ETag']='"intervening-source-version"'
        backup_s3.objects['reports/latest.html']['ETag']='"new-live-edition"'
        validate_resume(backup_receipt,targets)
        try:complete_backup_phase(backup_s3,targets[:2],backup_receipt,save_backup)
        except ClientError:pass
        else:raise AssertionError('Later backup interruption not surfaced')
        assert backup_receipt['stage']=='backup' and len(backup_receipt['backups'])==1
        assert backup_receipt['protected_before']==protected_before
        assert backup_s3.objects[first_backup]==original_first and backup_s3.copies==[first_backup]
        # Previously confirmed backups are verified before any further copy.
        backup_s3.objects[first_backup]['ETag']='"tampered-backup"'
        try:complete_backup_phase(backup_s3,targets[:2],backup_receipt,save_backup)
        except ValueError:pass
        else:raise AssertionError('Changed original backup accepted')
        assert backup_s3.copies==[first_backup]
        backup_s3.objects[first_backup]=original_first;backup_s3.blocked_copy=None
        validate_resume(backup_receipt,targets)
        complete_backup_phase(backup_s3,targets[:2],backup_receipt,save_backup)
    assert backup_receipt['stage']=='upload' and len(backup_receipt['backups'])==3
    assert backup_receipt['protected_before']==protected_before
    assert backup_s3.objects[first_backup]==original_first
    assert backup_s3.copies==[first_backup,second_backup,original['backup_prefix']+'reports/index.html']
    conflict=BackupS3();conflict.fail_verification=False;conflict.blocked_copy=None
    conflict.objects[first_backup]={'ETag':'"unrecognized-backup"','ContentLength':1}
    try:complete_backup_phase(conflict,targets[:2],backup_fixture(),lambda:None)
    except ValueError:pass
    else:raise AssertionError('Unrecognized existing backup overwritten')
    assert conflict.copies==[]
    assert (json.loads(DEST.read_text()) if DEST.exists() else None)==before
    print('OFFLINE SELF-TEST PASS: atomic GET version-bound SHA; cached identical ETags avoid repeat downloads; changed ETags rehashed; foreign changes blocked; full-set gate enforced; interrupted confirmations retained; pre-snapshot and partial-backup failures resume; ambiguous successful copies preserve original versions; changed/unrecognized backups blocked; exact targets/backups preserved; bounded configurable retries; no network or real receipt changes')

def main():
    global MAX_ATTEMPTS,BACKOFF_BASE,BACKOFF_CAP
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--go',action='store_true');ap.add_argument('--resume',action='store_true');ap.add_argument('--self-test',action='store_true')
    ap.add_argument('--attempts',type=int,default=3,help='attempts per remote operation, 1..10 (default3)')
    ap.add_argument('--backoff-seconds',type=float,default=1,help='initial exponential retry delay, 0..30seconds (default1)')
    ap.add_argument('--max-backoff-seconds',type=float,default=4,help='maximum retry delay, 0..30seconds (default4)')
    a=ap.parse_args()
    if not 1<=a.attempts<=10:ap.error('--attempts must be1..10')
    if not 0<=a.backoff_seconds<=30 or not 0<=a.max_backoff_seconds<=30:ap.error('retry delays must be0..30seconds')
    if a.backoff_seconds>a.max_backoff_seconds:ap.error('initial retry delay cannot exceed maximum delay')
    MAX_ATTEMPTS=a.attempts;BACKOFF_BASE=a.backoff_seconds;BACKOFF_CAP=a.max_backoff_seconds
    targets=plan();stats=manifest_statistics()
    print('Validated',stats['report_count'],'reports;',len(targets),'artifacts + archive index;',stats['total_words'],'words;',stats['total_pdf_pages'],'PDF pages',flush=True)
    receipt=None
    if a.resume:
        if not DEST.exists():raise ValueError('No original publication receipt to resume')
        receipt=validate_resume(json.loads(DEST.read_text()),targets)
        print('Resume validated:',receipt['run'],'stage',receipt['stage'],'original backups retained',flush=True)
    if a.self_test:offline_self_test(targets);return
    if not a.go:
        print('DRY RUN: no remote calls or changes');return
    if not a.resume and DEST.exists():
        prior=json.loads(DEST.read_text())
        if prior.get('stage')!='published':raise ValueError('An unfinished publication already exists; use --resume to preserve its backups')
    if receipt is None:
        run=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        receipt={'run':run,'dates':DATES,'stage':'backup','backup_prefix':f'reports/_retrospective_backup/may-2025-weekdays/{run}/','targets':targets,'artifact_statistics':stats,'backups':[],'latest_write_performed':False}
    def save():save_json(DEST,receipt)
    receipt['status']='in_progress'
    receipt['retry_policy']={'max_attempts':MAX_ATTEMPTS,'backoff_base_seconds':BACKOFF_BASE,'backoff_cap_seconds':BACKOFF_CAP,'sdk_attempts':1,'concurrency':1};save()
    try:
        session=boto3.Session(aws_access_key_id=os.environ['AWS_KEY'],aws_secret_access_key=os.environ['AWS_SECRET'],region_name='eu-north-1')
        execute(session.client('s3',config=CONFIG),session.client('cloudfront',config=CONFIG),targets,receipt,save,a.resume)
    except Exception as error:
        receipt['status']='blocked_transport' if transient(error) else 'blocked_error'
        receipt['failure']={**error_summary(error),'at_utc':utc()};save()
        print('Publication stopped:',receipt['status'],'stage',receipt['stage'],'confirmed',len(receipt.get('confirmed_targets',{})),'of',len(targets),flush=True)
        raise

if __name__=='__main__':main()
