"""Verify/import exact parsed public RSS responses from isolated reviewed CI.

All run/job/artifact bindings come from the GitHub connector. Default verification
performs no mutation. --import-cache writes only validated acquisition caches and
an exact hash receipt. No network, publisher bodies, credentials or prose.
"""
from pathlib import Path
import argparse,datetime as dt,gzip,hashlib,json,re,urllib.parse,zipfile
from fetch_news import ROOT,CACHE,VERSION,PARSER_SCHEMA,UTC,ROLLING,url_for,atomic_json
FILES={'.github/workflows/apr2025-rss-recovery.yml','corrections/2025-04/rss_recovery/input.json','corrections/2025-04/rss_recovery/fetch_news.py','corrections/2025-04/rss_recovery/run.py'}
def sha(raw):return hashlib.sha256(raw).hexdigest()
def verify(batch):
 manifest=json.loads((batch/'code_manifest.json').read_text());remote=json.loads((batch/'remote_files.json').read_text());verified=json.loads((batch/'remote_code_verification.json').read_text());binding=json.loads((batch/'run_binding.json').read_text())
 assert set(manifest)==FILES=={r['path']for r in remote}
 assert verified['head']==binding['head']and verified['exact_four_files_verified']
 for row in remote:
  assert row['encoding']=='utf-8';raw=(batch/'source'/row['path']).read_bytes();assert sha(raw)==manifest[row['path']]['sha256']
  assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==row['sha'],'Remote Git blob identity mismatch'
  if row.get('remote_content_omitted_by_contents_api'):assert not row['content']and len(raw)>1048576
  else:assert row['content'].encode()==raw
 fetcher=batch/'source/corrections/2025-04/rss_recovery/fetch_news.py';assert fetcher.read_bytes()==(ROOT/'tools/fetch_news.py').read_bytes(),'CI parser differs from accepted acquisition source'
 input_path=batch/'source/corrections/2025-04/rss_recovery/input.json';input_obj=json.loads(input_path.read_text());jobs=input_obj['jobs'];part_size=input_obj.get('part_size',750)
 assert 0<len(jobs)<=15000 and 0<part_size<=1000
 expected={}
 for row in jobs:
  t,q,c,loc,lo,hi=row['job'];lo=dt.date.fromisoformat(lo);hi=dt.date.fromisoformat(hi);url,_=url_for(q,lo,hi,tuple(loc));u=urllib.parse.urlsplit(url)
  assert row['request_url']==url and u.scheme=='https'and u.hostname=='news.google.com'and u.path=='/rss/search'
  assert row['signature']==sha((VERSION+'\n'+url).encode())and row['signature']not in expected
  expected[row['signature']]=row
 records={};artifact_rows=[]
 for job in binding['jobs']:
  assert job['commit_sha']==binding['head']and job['run_id']==job['job_run_id']and job['conclusion']=='success'
  path=(batch/job['file']).resolve();assert path.is_relative_to(batch.resolve()),'Artifact outside captured batch'
  raw=path.read_bytes();assert sha(raw)==job['artifact_sha256']and len(raw)==job['artifact_size_bytes']
  if job.get('job_log_sha256'):
   log_path=(batch/job.get('job_log_file','job.log')).resolve();assert log_path.is_relative_to(batch.resolve())
   assert sha(log_path.read_bytes())==job['job_log_sha256']
  with zipfile.ZipFile(path)as archive:
   assert archive.testzip()is None and set(archive.namelist())=={'records.json','receipt.json'}
   record_raw=archive.read('records.json');receipt_raw=archive.read('receipt.json');receipt=json.loads(receipt_raw);part_records=json.loads(record_raw)
  assert receipt['input_sha256']==manifest['corrections/2025-04/rss_recovery/input.json']['sha256']
  assert receipt['fetcher_sha256']==manifest['corrections/2025-04/rss_recovery/fetch_news.py']['sha256']
  assert receipt['runner_sha256']==manifest['corrections/2025-04/rss_recovery/run.py']['sha256']
  assert receipt['records_sha256']==sha(record_raw)and receipt['failures']==0 and receipt['parser_schema']==PARSER_SCHEMA
  part=job['part'];wanted={r['signature']for r in jobs[part*part_size:(part+1)*part_size]}
  assert set(part_records)==wanted and len(wanted)==receipt['records']and receipt['part']==part and receipt['part_size']==part_size
  for signature,row in part_records.items():
   request=expected[signature];t,q,c,loc,lo,hi=request['job']
   assert row['request_url']==request['request_url']and row['signature']==signature and row['version']==VERSION
   assert row['status']=='fetched'and row['parser_schema']==PARSER_SCHEMA and row['response_format_verified']is True
   assert [row['topic'],row['query'],row['category'],row['locale'],row['lower_date'],row['upper_date_exclusive']]==request['job']
   assert re.fullmatch('[0-9a-f]{64}',row['raw_sha256'])and row['possibly_capped']==(row['raw_count']>=100)
   for item in row['items']:
    published=dt.datetime.fromisoformat(item['published_at']);assert published.tzinfo is not None and lo<=published.astimezone(UTC).date().isoformat()<hi
    assert item['title']and item['url'].startswith('https://')and not ROLLING.search(item['title'])
   assert signature not in records;records[signature]=row
  artifact_rows.append({**job,'records':len(part_records),'records_sha256':sha(record_raw),'receipt_sha256':sha(receipt_raw)})
 assert set(records)==set(expected),'Missing or extra imported request signatures'
 proof={'status':'verified','head':binding['head'],'batch':str(batch.relative_to(ROOT)),'records':len(records),'failures':0,'parser_schema':PARSER_SCHEMA,'exact_four_files_verified':True,'input_sha256':sha(input_path.read_bytes()),'fetcher_sha256':sha(fetcher.read_bytes()),'runner_sha256':manifest['corrections/2025-04/rss_recovery/run.py']['sha256'],'workflow_sha256':manifest['.github/workflows/apr2025-rss-recovery.yml']['sha256'],'importer_sha256':sha(Path(__file__).read_bytes()),'artifacts':artifact_rows,'scope':'Exact reviewed public RSS query inputs, strict parser and parsed response JSON; no publisher article bodies or historical original server snapshots.'}
 return records,proof

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('batch_directory');ap.add_argument('--import-cache',action='store_true');args=ap.parse_args();batch=(ROOT/args.batch_directory).resolve();assert batch.is_relative_to(ROOT/'work')
 records,proof=verify(batch);prepared=[]
 for signature,row in records.items():
  path=CACHE/(signature+'.json.gz')
  if path.exists():
   prior=json.loads(gzip.decompress(path.read_bytes()))
   if prior.get('status')=='fetched'and prior.get('parser_schema')==PARSER_SCHEMA:assert prior==row,'Successful strict cache conflicts with captured response'
  prepared.append((path,row))
 if args.import_cache:
  imported=[]
  for path,row in prepared:
   atomic_json(path,row,True);imported.append({'path':str(path.relative_to(ROOT)),'sha256':sha(path.read_bytes()),'bytes':path.stat().st_size,'signature':row['signature'],'record_json_sha256':sha(json.dumps(row,ensure_ascii=False,separators=(',',':')).encode())})
  proof.update(status='imported',cache_files=imported)
  output=ROOT/'audit'/('news_public_rss_ingestion_'+batch.name+'.json');atomic_json(output,proof)
 print(json.dumps({k:v for k,v in proof.items()if k not in('cache_files','artifacts')},indent=2))
if __name__=='__main__':main()
