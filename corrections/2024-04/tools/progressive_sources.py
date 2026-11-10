"""Stage/freeze one completed own-cutoff source candidate while later dates acquire.

Never releases a feed without independent hash-bound acceptance. The final full
month finalizer must replay every raw/ready/provenance candidate and prove the
same frozen bytes before updating the final source-freeze ledger.
"""
from __future__ import annotations
import argparse,datetime as dt,gzip,hashlib,json
from pathlib import Path
from fetch_news import ROOT,atomic_json,json_bytes
from ready_feeds import screen,DATES,SCHEDULE_PATH,NAMED_PATH,DISPOSITIONS_PATH
from announced_source_integrity import check_announced

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):
 raw=path.read_bytes();return json.loads(gzip.decompress(raw)if path.suffix=='.gz'else raw)
def main(date,freeze=False):
 stamp=date.isoformat();assert date in DATES
 source=ROOT/'work/source_candidates_partial'
 rawpath=source/'unreviewed_feeds'/(stamp+'.json.gz');provenancepath=source/'news_provenance'/(stamp+'.json.gz')
 raw=read(rawpath);partial=read(source/'receipts'/(stamp+'.json'))
 assert partial['date']==stamp and partial['status']=='raw_cutoff_queries_complete_semantic_screen_pending_do_not_author'
 assert partial['failed_query_windows']==0 and partial['future_items']==0 and partial['outside_category_window']==0
 assert sha(rawpath)==partial['feed_sha256']and sha(provenancepath)==partial['provenance_sha256']
 provenance=read(provenancepath)
 assert provenance['date']==stamp and provenance['cutoff_utc']==raw['cutoff_utc'],'Own-date provenance identity mismatch'
 assert set(provenance['records'])=={x['id']for x in raw['items']},'Own-date provenance source IDs mismatch'
 prepared=screen(date,raw=raw,persist=False);payload=prepared.pop('_payload')
 frozen_path=ROOT/'audit'/('news_frozen_'+stamp+'.json')
 if frozen_path.exists():
  frozen=read(frozen_path)
  check_announced(stamp,frozen)
  assert frozen['raw_sha256']==sha(rawpath)and frozen['provenance_sha256']==sha(provenancepath),'Previously frozen raw/provenance changed'
  assert frozen['feed_sha256']==hashlib.sha256(json_bytes(payload,True)).hexdigest(),'Previously frozen effective own-date screen changed'
  print(stamp,'ALREADY FROZEN; exact raw/provenance/ready bytes unchanged; receipt preserved',flush=True)
  return
 stage=ROOT/'work/source_candidates_partial_ready';ready_path=stage/'feeds'/(stamp+'.json.gz')
 atomic_json(ready_path,payload,True)
 candidate={
 'date':stamp,'status':'completed_own_cutoff_candidate_requires_independent_review',
 'raw_path':str(rawpath.relative_to(ROOT)),'raw_sha256':sha(rawpath),
 'provenance_path':str(provenancepath.relative_to(ROOT)),'provenance_sha256':sha(provenancepath),
 'ready_path':str(ready_path.relative_to(ROOT)),'ready_sha256':sha(ready_path),
 'ready_receipt':prepared,'cutoff_receipt_sha256':sha(source/'receipts'/(stamp+'.json')),
 'release_schedule_sha256':sha(SCHEDULE_PATH),'named_exclusions_sha256':sha(NAMED_PATH),
 'observed_semantic_dispositions_sha256':sha(DISPOSITIONS_PATH),
 'screening_tool_sha256':sha(ROOT/'tools/ready_feeds.py'),
 'limits':['Own-cutoff query plan and all observed response caps completed; later-date query results cannot contribute.','Final full-month raw/ready/provenance byte-equality replay remains required before publication.','Historical Google RSS timestamps/headlines do not certify original publisher vintages.']}
 candidate_path=stage/'receipts'/(stamp+'.json');atomic_json(candidate_path,candidate)
 print(stamp,'STAGED READY',prepared['ready_items'],'EXCLUDED',prepared['excluded_items'],'candidate',sha(candidate_path),flush=True)
 if not freeze:return
 review_path=ROOT/'audit'/('progressive_source_review_'+stamp+'.json');review=read(review_path)
 assert review.get('date')==stamp and review.get('passed')is True and type(review.get('fatal_or_major_remaining'))is int and review.get('fatal_or_major_remaining')==0
 assert review.get('candidate_sha256')==sha(candidate_path),'Independent review stale: candidate changed'
 assert review.get('independent_reviewer')and review.get('review_notes'),'No independent review rationale'
 target=ROOT/'feeds'/(stamp+'.json.gz')
 if target.exists():assert sha(target)==sha(ready_path),'Refusing changed announced source set'
 atomic_json(ROOT/'work/unreviewed_feeds'/(stamp+'.json.gz'),raw,True)
 atomic_json(ROOT/'audit/news_provenance'/(stamp+'.json.gz'),read(provenancepath),True)
 atomic_json(target,payload,True)
 atomic_json(ROOT/'audit'/('news_ready_'+stamp+'.json'),prepared)
 frozen={'date':stamp,'feed_sha256':sha(target),'raw_sha256':sha(rawpath),'provenance_sha256':sha(provenancepath),'status':'frozen_complete_own_date_pending_full_month_equality_replay','full_month_replay_pending':True,'full_month_replay_verified':False,'candidate_manifest':str(candidate_path.relative_to(ROOT)),'candidate_manifest_sha256':sha(candidate_path),'independent_review':str(review_path.relative_to(ROOT)),'independent_review_sha256':sha(review_path),'ready_receipt_sha256':sha(ROOT/'audit'/('news_ready_'+stamp+'.json')),'ready_items':prepared['ready_items'],'excluded_items':prepared['excluded_items'],'rule':'Immutable own-cutoff completed acquisition; only full-month equality replay may finalize ledger.'}
 atomic_json(ROOT/'audit'/('news_frozen_'+stamp+'.json'),frozen)
 ex=ROOT/'exclusions'/(stamp+'.json')
 if ex.exists():assert read(ex)['feed_sha256']==sha(target),'Stale exclusions'
 else:atomic_json(ex,{'date':stamp,'feed_sha256':sha(target),'exclusions':[],'scope':'Known pre-release/unsafe records removed before progressive freeze; subsequent editorial exclusions only.'})
 print(stamp,'FROZEN FOR OWN-DATE AUTHORING',sha(target),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('date');p.add_argument('--freeze',action='store_true');a=p.parse_args();main(dt.date.fromisoformat(a.date),freeze=a.freeze)
