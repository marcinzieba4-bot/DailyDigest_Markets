"""Read-only verification/planning for later cited metadata; never changes frozen inputs."""
from pathlib import Path
import base64,datetime as dt,gzip,hashlib,importlib.util,json,re,sys
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'tools'))
import import_public_metadata as importer
from audit_source_dates import CITE,DATES,path_dates,valid_publisher_url

def sha(raw):return hashlib.sha256(raw).hexdigest()
def read(path):return json.loads(path.read_text())
def snapshot(dates=None):
 cache=read(ROOT/'audit/canonical_all_cited_urls.json');rows=[];spec_hashes={};refs=[]
 for p in sorted((ROOT/'specs').glob('*.json')):
  date=p.stem
  if dates is not None and date not in dates:continue
  raw=p.read_bytes();json.loads(raw);assert p.read_bytes()==raw,'Spec changed during snapshot; retry'
  spec_hashes[date]=sha(raw);feed={x['id']:x for x in json.loads(gzip.decompress((ROOT/'feeds'/(date+'.json.gz')).read_bytes()))['items']}
  for key in sorted(set(CITE.findall(raw.decode()))):
   item=feed[key];metadata=cache.get(item['url'],{});canonical=metadata.get('canonical_url')
   refs.append({'date':date,'id':key,'title':item['title'],'source':item['src'],'url':item['url'],'canonical_url':canonical,'path_dates':path_dates(canonical)if valid_publisher_url(canonical)else[]})
 missing=sorted({r['url']for r in refs if r['url'].startswith('https://news.google.com/')and not valid_publisher_url(r['canonical_url'])})
 conflicts=[r for r in refs if any(d>=r['date']for d in r['path_dates'])]
 return {'dates':sorted(spec_hashes),'spec_sha256':spec_hashes,'cited_occurrences':len(refs),'unique_google_urls':len({r['url']for r in refs}),'missing_urls':missing,'missing_count':len(missing),'path_conflicts_before_any_timing_exception':conflicts,'cache_sha256':sha((ROOT/'audit/canonical_all_cited_urls.json').read_bytes())}

def batch_proof(number):
 b=ROOT/'work'/f'recovery_batch{number}';records,proof,bundle,payload=importer.verify(b)
 remote=read(b/'independent_remote_binding.json');assert remote['run']['head_sha']==proof['commit_sha']and remote['run']['id']==proof['workflow_run_id']and remote['run']['status']=='completed'and remote['run']['conclusion']=='success'
 assert remote['run']['event']=='pull_request'and remote['run']['head_branch']=='codex/apr2025-public-metadata-recovery'
 j=next(j for j in remote['jobs']if j['id']==proof['workflow_job_id']);assert j['run_id']==proof['workflow_run_id']and j['status']=='completed'and j['conclusion']=='success'
 manifest=read(b/'code_manifest.json');tree=remote['tree'];blobs={x['path']:x for x in tree['tree']if x['type']=='blob'};assert not tree['truncated']and set(blobs)==set(manifest)|{'README.md'}and blobs['README.md']['size']==21
 for path,row in manifest.items():
  raw=(b/'source'/path).read_bytes();assert sha(raw)==row['sha256'];assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==blobs[path]['sha'];assert len(raw)==blobs[path]['size']
 assert remote['fresh_log_payload_sha256']==proof['payload_sha256']==sha((b/'payload.gz').read_bytes())
 ingestion=read(ROOT/'audit'/f'metadata_ci_ingestion_batch{number}.json');assert ingestion['commit_sha']==proof['commit_sha']and ingestion['output_sha256']==proof['output_sha256']and ingestion['records']==len(records)
 return {'batch':number,'status':'passed','records':len(records),'head':proof['commit_sha'],'run_id':proof['workflow_run_id'],'job_id':proof['workflow_job_id'],'tree_sha':tree['sha'],'payload_sha256':proof['payload_sha256'],'output_sha256':proof['output_sha256'],'code_manifest_sha256':sha((b/'code_manifest.json').read_bytes()),'ingestion_sha256':sha((ROOT/'audit'/f'metadata_ci_ingestion_batch{number}.json').read_bytes()),'independent_remote_binding_sha256':sha((b/'independent_remote_binding.json').read_bytes()),'verified_four_remote_files_and_readme_only':True,'publisher_bodies_fetched':False,'initial_frozen_inputs_changed':False}

def verify_frozen():
 inventory_path=ROOT/'audit/news_replay_inventory.json';initial_qa=ROOT/'checks/source_acquisition_independent_review.json'
 assert sha(inventory_path.read_bytes())=='d2db362d94c8f94753567d5018675efcf7fcd428674fd758dcaf53a761131c52'
 assert sha(initial_qa.read_bytes())=='53b7ee234719eef8f44f634f3ce09b17701c6f4eeb51e4c79ccc536bc7960a5d'
 inventory=read(inventory_path)
 for row in inventory['files']:
  path=ROOT/row['path'];raw=path.read_bytes();assert len(raw)==row['bytes']and sha(raw)==row['sha256'],row['path']
 return {'passed':True,'files_verified':len(inventory['files']),'bytes_verified':sum(row['bytes']for row in inventory['files']),'inventory_sha256':sha(inventory_path.read_bytes()),'initial_source_qa_sha256':sha(initial_qa.read_bytes())}

def verify_cache():
 cache_path=ROOT/'audit/canonical_all_cited_urls.json';cache=read(cache_path);expected={};receipts={}
 paths=sorted((ROOT/'audit').glob('metadata_ci_ingestion_batch*.json'),key=lambda p:int(re.search(r'batch(\d+)',p.name).group(1)))
 for path in paths:
  ingestion=read(path);batch=ROOT/ingestion['files'];records,proof,_,_=importer.verify(batch)
  assert ingestion['commit_sha']==proof['commit_sha']and ingestion['output_sha256']==proof['output_sha256']and ingestion['payload_sha256']==proof['payload_sha256']
  for url,row in records.items():
   if url in expected:assert expected[url]['canonical_url']==row['canonical_url'],'Captured canonical mappings conflict'
   expected[url]=row
  receipts[str(path.relative_to(ROOT))]=sha(path.read_bytes())
 assert set(cache)==set(expected),'Current canonical cache URL set differs from verified captured outputs'
 for url,row in expected.items():
  assert cache[url]==row,'Current cache object differs from captured output: '+url
  assert valid_publisher_url(row.get('canonical_url'))and row.get('publisher_body_fetched')is False and not row.get('error')
 semantic=json.dumps(cache,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
 return {'passed':True,'url_count':len(cache),'source_batches':len(paths),'canonical_cache_sha256':sha(cache_path.read_bytes()),'canonical_cache_semantic_sha256':sha(semantic),'all_current_cache_objects_match_captured_outputs':True,'ingestion_receipt_sha256':receipts}

def main():
 mode=sys.argv[1]if len(sys.argv)>1 else'plan';dates=read(ROOT/'work/cited_metadata_sealed_dates.json')['dates'];current=snapshot(dates)
 if mode=='plan':
  out={'urls':current['missing_urls']};(ROOT/'work/cited_metadata_missing_input.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');(ROOT/'work/cited_metadata_missing_plan.json').write_text(json.dumps(current,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:current[k]for k in ['dates','cited_occurrences','unique_google_urls','missing_count']}));return
 batches=[]
 for p in sorted((ROOT/'audit').glob('metadata_ci_ingestion_batch*.json')):
  n=int(re.search(r'batch(\d+)',p.name).group(1))
  if n>=2 and(ROOT/'work'/f'recovery_batch{n}'/'independent_remote_binding.json').exists():batches.append(batch_proof(n))
 frozen=verify_frozen();verified_cache=verify_cache();passed=len(current['dates'])==len(DATES)and current['missing_count']==0
 result={'status':'passed'if passed else'progress','passed':passed,'current_snapshot_only':True,'editorial_finalization':'Pending root confirmation; PR7 remains open','reviewer':'/root/apr_news','scope':'Independent direct GitHub commit-tree/run/job/file/log-payload bindings for cited-only recovery batches after initial source freeze; no source timing exception approval.','checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'batches':batches,'frozen_acquisition_verification':frozen,'current_cache_verification':verified_cache,'review_tool_sha256':sha(Path(__file__).read_bytes()),'verified_later_records':sum(r['records']for r in batches),'current_citation_snapshot':current,'pending_report_dates':[date for date in DATES if date not in current['dates']],'initial_inventory_sha256':sha((ROOT/'audit/news_replay_inventory.json').read_bytes()),'initial_source_qa_sha256':sha((ROOT/'checks/source_acquisition_independent_review.json').read_bytes()),'mutable_cache_outside_initial_inventory':True,'limits':['Canonical URL and path dates do not establish original article-body vintage or exact intraday publication.','Timing conflicts are flagged to independent editors; this review grants no timing exception.']}
 output=ROOT/'checks/cited_metadata_independent_review.json'
 semantic=lambda value:{k:v for k,v in value.items()if k!='checked_at_utc'}
 if mode in ('--check-only','check-only'):
  assert passed,'Current complete-month citation mappings are not ready'
  assert output.exists()and semantic(read(output))==semantic(result),'Cited metadata receipt is stale; run review mode before freezing artifacts'
  result=read(output)
 elif output.exists()and semantic(read(output))==semantic(result):result=read(output)
 else:output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'status':result['status'],'batches':len(batches),'verified_later_records':result['verified_later_records'],'sealed_reports':len(current['dates']),'missing_cited_urls':current['missing_count'],'raw_path_conflicts':len(current['path_conflicts_before_any_timing_exception'])}))
if __name__=='__main__':main()
