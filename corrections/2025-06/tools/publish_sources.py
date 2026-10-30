"""Publish the frozen source archive with resumable checked parts; dry-run unless --go."""
from pathlib import Path
import argparse,base64,datetime as dt,hashlib,json,os,time,urllib.request
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError,ConnectionError,HTTPClientError
ROOT=Path(__file__).resolve().parent.parent
PART_SIZE=8*1024*1024

def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp');temporary.write_text(json.dumps(value,indent=2));temporary.replace(path)

def retry(label,fn):
    for attempt in range(12):
        try:return fn()
        except Exception as error:
            transient=isinstance(error,(ConnectionError,HTTPClientError)) or (isinstance(error,ClientError) and error.response.get('ResponseMetadata',{}).get('HTTPStatusCode') in (408,429,500,502,503,504))
            if not transient or attempt==11:raise
            delay=min(2**attempt,15);print(label,'transport retry',attempt+1,'waiting',delay,'seconds',flush=True);time.sleep(delay)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--go',action='store_true');args=ap.parse_args()
    receipt_path=ROOT/'checks/source_archive_publication.json'
    record=json.loads((ROOT/'checks/source_archive_build.json').read_text())
    if receipt_path.exists():
        previous=json.loads(receipt_path.read_text())
        if any(previous.get(k)!=record.get(k) for k in ('path','key','sha256','bytes','dates')):
            raise ValueError('Published source receipt differs from this build; review before replacing it')
    path=ROOT/record['path'];digest=lambda b:hashlib.sha256(b).hexdigest()
    dates=[dt.date(2025,6,n).isoformat() for n in range(1,31) if dt.date(2025,6,n).weekday()<5]
    if record.get('dates')!=len(dates):raise ValueError(f'Source archive must contain all {len(dates)} June weekdays')
    if record.get('key')!='reports/2025-06/June_2025_Frozen_News_Feeds.zip':raise ValueError('Unexpected June source archive key')
    if digest(path.read_bytes())!=record['sha256'] or path.stat().st_size!=record['bytes']:raise ValueError('Source archive differs from its receipt')
    print('Validated source archive:',record['dates'],'dates,',record['bytes'],'bytes',flush=True)
    if not args.go:print('DRY RUN: no remote calls or writes');return
    session=boto3.Session(aws_access_key_id=os.environ['AWS_KEY'],aws_secret_access_key=os.environ['AWS_SECRET'],region_name='eu-north-1')
    s3=session.client('s3',config=Config(connect_timeout=8,read_timeout=30,retries={'total_max_attempts':1,'mode':'standard'}));bucket='s3bucketmz';key=record['key'];state_path=ROOT/'work/source_upload_state.json'
    def existing_object():
        try:response=s3.get_object(Bucket=bucket,Key=key)
        except ClientError as error:
            if error.response['Error']['Code'] in ('404','NoSuchKey','NotFound'):return None
            raise
        try:blob=response['Body'].read()
        finally:response['Body'].close()
        if len(blob)!=record['bytes'] or digest(blob)!=record['sha256']:raise ValueError('Existing source archive differs; refusing replacement')
        return response['ETag']
    matched=retry('GetObject/source',existing_object)
    if matched is None:
        state=json.loads(state_path.read_text()) if state_path.exists() else None
        if state and (state.get('sha256')!=record['sha256'] or state.get('key')!=key or state.get('bytes')!=record['bytes']):raise ValueError('Resume state does not match this exact archive')
        if state is None:
            response=retry('CreateMultipartUpload',lambda:s3.create_multipart_upload(Bucket=bucket,Key=key,ContentType='application/zip',ChecksumAlgorithm='SHA256',Metadata={'sha256':record['sha256'],'retrospective-month':'2025-06'}))
            state={'key':key,'sha256':record['sha256'],'bytes':record['bytes'],'upload_id':response['UploadId'],'parts':{}};save(state_path,state)
        def list_parts():
            result={};marker=None
            while True:
                args={'Bucket':bucket,'Key':key,'UploadId':state['upload_id']}
                if marker is not None:args['PartNumberMarker']=marker
                response=s3.list_parts(**args)
                for part in response.get('Parts',[]):result[str(part['PartNumber'])]=part
                if not response.get('IsTruncated'):return result
                marker=response['NextPartNumberMarker']
        remote=retry('ListParts',list_parts);completed=[]
        with path.open('rb') as stream:
            index=0
            while chunk:=stream.read(PART_SIZE):
                index+=1;checksum=base64.b64encode(hashlib.sha256(chunk).digest()).decode();old=state['parts'].get(str(index));seen=remote.get(str(index))
                if old and seen and old['etag']==seen['ETag'] and seen['Size']==len(chunk) and old['checksum_sha256']==checksum:
                    etag=seen['ETag'];print('Reused verified part',index,flush=True)
                else:
                    response=retry('UploadPart/'+str(index),lambda:s3.upload_part(Bucket=bucket,Key=key,UploadId=state['upload_id'],PartNumber=index,Body=chunk,ChecksumSHA256=checksum))
                    if response.get('ChecksumSHA256')!=checksum:raise ValueError('Server part checksum differs')
                    etag=response['ETag'];state['parts'][str(index)]={'etag':etag,'bytes':len(chunk),'checksum_sha256':checksum};save(state_path,state);print('Confirmed source part',index,flush=True)
                completed.append({'PartNumber':index,'ETag':etag,'ChecksumSHA256':checksum})
        try:
            retry('CompleteMultipartUpload',lambda:s3.complete_multipart_upload(Bucket=bucket,Key=key,UploadId=state['upload_id'],MultipartUpload={'Parts':completed},IfNoneMatch='*'))
        except ClientError as error:
            if error.response['Error']['Code'] not in ('412','PreconditionFailed','NoSuchUpload'):raise
        if retry('GetObject/final-source-SHA',existing_object) is None:raise ValueError('Completed archive missing')
    url='https://d7g7nkeytae81.cloudfront.net/'+key
    for attempt in range(12):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'Accept-Encoding':'identity'}),timeout=30) as response:blob=response.read()
            if len(blob)!=record['bytes'] or digest(blob)!=record['sha256']:raise ValueError('Public archive verification failed')
            break
        except Exception:
            if attempt==11:raise
            time.sleep(min(2**attempt,15))
    record.update(published=True,verified_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),public_url=url,origin_and_public_sha_verified=True,resumable_part_bytes=PART_SIZE);save(receipt_path,record)
    print('Origin and public source archive SHA256 verified',flush=True)
if __name__=='__main__':main()
