"""Read-only snapshot audit of actual retained June physical transport records.
This is an interim observation, not final source acceptance or a complete attempt census.
"""
from pathlib import Path,PurePosixPath
import collections,datetime as dt,gzip,hashlib,json
R=Path(__file__).resolve().parent.parent
sha=lambda b:hashlib.sha256(b).hexdigest()
p=R/'audit/news_physical_requests.jsonl';raw=p.read_bytes();lines=raw.splitlines();ledger=[json.loads(x)for x in lines if x]
errors=[];bodies=collections.Counter();number_groups=collections.defaultdict(list);identity=collections.Counter();paths=collections.Counter();missing=[]
for n,x in enumerate(ledger,1):
 key=(x['signature'],x['attempt'],x['started_at_utc']);identity[key]+=1;number_groups[(x['signature'],x['attempt'])].append(n)
 if sha(('jun-2024-cutoff-prefix-partition-v1\n'+x['request_url']).encode())!=x['signature']:errors.append({'row':n,'error':'URL signature mismatch'})
 if dt.datetime.fromisoformat(x['started_at_utc'])>dt.datetime.fromisoformat(x['finished_at_utc']):errors.append({'row':n,'error':'clock order'})
 if x.get('raw_response_path'):
  rel=x['raw_response_path'];q=PurePosixPath(rel);f=R/q;paths[rel]+=1
  if q.is_absolute()or'..'in q.parts or f.is_symlink()or not f.resolve().is_relative_to(R):errors.append({'row':n,'error':'unsafe body path'});continue
  try:
   compressed=f.read_bytes();body=gzip.decompress(compressed)
   if sha(compressed)!=x['raw_compressed_sha256']or sha(body)!=x['raw_sha256']:errors.append({'row':n,'error':'body hash mismatch','path':rel})
  except Exception as e:errors.append({'row':n,'error':'body unavailable','type':type(e).__name__,'path':rel})
  bodies[x['status']]+=1
 else:
  missing.append({'row':n,**x})
  if x['status']=='fetched':errors.append({'row':n,'error':'successful body missing'})
for key,n in identity.items():
 if n>1:errors.append({'error':'duplicate physical tuple','identity':list(key),'count':n})
for path,n in paths.items():
 if n>1:errors.append({'error':'body path reused across physical records','path':path,'count':n})
limit= json.loads((R/'audit_work/acquisition_capture_limitation.json').read_text())
legacy={(x['signature'],x['attempt'],x['started_at_utc'])for x in limit['affected_attempts']}
unknown=[x for x in missing if (x['signature'],x['attempt'],x['started_at_utc'])not in legacy]
if unknown:errors.append({'error':'missing bodies outside disclosed legacy identities','rows':[x['row']for x in unknown]})
start=R/'audit/news_physical_attempt_starts.jsonl';starts=[json.loads(x)for x in start.read_bytes().splitlines()if x]if start.exists()else[]
ids=collections.Counter(x.get('attempt_id')for x in ledger if x.get('attempt_id'));startids=collections.Counter(x.get('attempt_id')for x in starts)
for k,v in ids.items():
 if v!=1 or startids[k]!=1:errors.append({'error':'new attempt ID not unique or start absent','attempt_id':k,'finished_count':v,'start_count':startids[k]})
finished_ids=set(ids);pending_start_ids=set(startids)-finished_ids
out={'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'status':'interim_transport_snapshot','passed_observed_checks':not errors,'ledger_snapshot_sha256':sha(raw),'ledger_snapshot_bytes':len(raw),'ledger_snapshot_records':len(ledger),'ledger_first_started_at':min(x['started_at_utc']for x in ledger),'ledger_last_finished_at':max(x['finished_at_utc']for x in ledger),'recorded_status_counts':dict(collections.Counter(x['status']for x in ledger)),'retained_bodies_rehashed_by_status':dict(bodies),'recorded_missing_body_count':len(missing),'recorded_missing_bodies_match_disclosed_initial58':len(missing)==58 and not unknown,'duplicate_signature_attempt_number_groups':[{'signature':k[0],'attempt':k[1],'ledger_rows':v}for k,v in number_groups.items()if len(v)>1],'physical_tuple_unique':all(n==1 for n in identity.values()),'retained_body_paths_unique':all(n==1 for n in paths.values()),'new_attempt_ids_finished':len(ids),'new_attempt_starts':len(starts),'new_pending_start_ids_observed':len(pending_start_ids),'limitation_receipt_sha256':sha((R/'audit_work/acquisition_capture_limitation.json').read_bytes()),'errors':errors,'limits':['Acquisition was still running while this stable ledger prefix was read; later completions are outside this snapshot.','The first58 recorded HTTP503 error bodies were discarded before the handler correction and are unrecoverable; they are explicitly excluded from retained-byte completeness.','Up to16 interrupted in-flight attempts may have no ledger rows, bodies or known outcomes. Their exact count/identity cannot be proved from this snapshot.','Legacy signature+attempt integers may repeat on restart. Actual started_at timestamps and unique immutable raw paths distinguish retained physical records; old rows are not renumbered.','A successful logical-query census and complete independent canonical RSS reconstruction require the final declared refinement plan and settled ledgers.']}
(R/'audit/independent_transport_observation.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
