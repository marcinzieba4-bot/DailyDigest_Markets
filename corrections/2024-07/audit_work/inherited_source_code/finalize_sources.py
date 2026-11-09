"""Offline final own-cutoff replay, physical staging, then all-date comparison before destination writes."""
from __future__ import annotations
import argparse,datetime as dt,json,hashlib
from fetch_news import ROOT,atomic_json,build_feed,json_bytes
from expand_capped_news import DATES,load_harvest,read,PLAN,COVERAGE,sha
from ready_feeds import screen

def main(stage_only=False):
 acceptance=ROOT/'audit/independent_source_review.json'
 if acceptance.exists() and read(acceptance).get('passed'):
  raise SystemExit('Accepted source set is immutable; finalization is closed')
 plan=read(PLAN);coverage=read(COVERAGE)
 assert plan['dates']==[d.isoformat()for d in DATES] and coverage['report_dates']==22 and coverage['failed_requests']==0
 batches=load_harvest(plan);prepared=[];stage=ROOT/'work/source_candidates'
 # Candidate files remain separate from announced feeds and provenance.
 for d in DATES:
  stamp=d.isoformat();oldpath=ROOT/'audit'/('news_frozen_'+stamp+'.json');old=read(oldpath)if oldpath.exists()else None
  raw=build_feed(d,batches,persist=False);ready=screen(d,raw=raw['_payload'],persist=False)
  candidates={
   'raw':(stage/'unreviewed_feeds'/(stamp+'.json.gz'),json_bytes(raw['_payload'],True)),
   'provenance':(stage/'news_provenance'/(stamp+'.json.gz'),json_bytes(raw['_ledger'],True)),
   'ready':(stage/'feeds'/(stamp+'.json.gz'),json_bytes(ready['_payload'],True))}
  for path,data in candidates.values():path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
  atomic_json(stage/'ready_receipts'/('news_ready_'+stamp+'.json'),{k:v for k,v in ready.items()if k!='_payload'})
  prepared.append((d,raw,ready,old,candidates))
  print(stamp,'STAGED',ready['ready_items'],'excluded',ready['excluded_items'],'existing frozen',bool(old),flush=True)
 # Inspect every actual staged byte before changing any destination.
 comparisons=[]
 for d,raw,ready,old,candidates in prepared:
  stamp=d.isoformat()
  for kind,(path,data)in candidates.items():assert path.read_bytes()==data,(stamp,kind,'staging mismatch')
  assert sha(candidates['raw'][0])==raw['feed_sha256'],stamp
  assert sha(candidates['provenance'][0])==raw['provenance_sha256'],stamp
  assert sha(candidates['ready'][0])==ready['ready_sha256'],stamp
  if old:
   assert old['feed_sha256']==ready['ready_sha256'],'Candidate differs from frozen source IDs: '+stamp
   assert sha(ROOT/'feeds'/(stamp+'.json.gz'))==old['feed_sha256'],'Announced feed changed: '+stamp
  comparisons.append({'date':stamp,'raw_candidate_sha256':sha(candidates['raw'][0]),'provenance_candidate_sha256':sha(candidates['provenance'][0]),'ready_candidate_sha256':sha(candidates['ready'][0]),'prior_frozen_match':bool(old),'all_stage_bytes_verified':True})
 atomic_json(stage/'comparison_manifest.json',{'status':'all_22_compared_before_destination_write','dates':comparisons,'query_plan_sha256':sha(PLAN),'tool_sha256':{p.name:sha(p)for p in [ROOT/'tools/fetch_news.py',ROOT/'tools/topics.py',ROOT/'tools/expand_capped_news.py',ROOT/'tools/ready_feeds.py',ROOT/'tools/finalize_sources.py']}})
 if stage_only:
  print('ALL 66 CANDIDATES COMPARED; stage-only, no frozen destinations written',flush=True);return
 print('ALL CANDIDATES PASS; committing raw/provenance and new feeds; immutable feeds remain byte identical',flush=True)
 rows=[]
 for d,raw,ready,old,candidates in prepared:
  stamp=d.isoformat();atomic_json(ROOT/'work/unreviewed_feeds'/(stamp+'.json.gz'),raw.pop('_payload'),True)
  atomic_json(ROOT/'audit/news_provenance'/(stamp+'.json.gz'),raw.pop('_ledger'),True)
  atomic_json(ROOT/'feeds'/(stamp+'.json.gz'),ready.pop('_payload'),True)
  atomic_json(ROOT/'audit'/('news_ready_'+stamp+'.json'),ready)
  frozen={'date':stamp,'feed_sha256':ready['ready_sha256'],'status':'frozen_complete_own_date','full_month_replay_pending':False,'full_month_replay_verified':True,'query_plan':'audit/news_query_plan.json','query_plan_sha256':sha(PLAN),'ready_items':ready['ready_items'],'excluded_items':ready['excluded_items'],'candidate_manifest':'work/source_candidates/comparison_manifest.json','rule':'Own-cutoff prefix queries and refinements only; daily refinements of later-cutoff capped parents excluded.'}
  atomic_json(ROOT/'audit'/('news_frozen_'+stamp+'.json'),frozen)
  rows.append({**raw,'screened_items':ready['ready_items'],'screened_sha256':ready['ready_sha256'],'frozen_priority_match':True if old else None})
  print(stamp,'READY',ready['ready_items'],flush=True)
 coverage=read(COVERAGE);coverage.update(dates=rows,own_date_records=sum(r['items']for r in rows),screened_own_date_records=sum(r['screened_items']for r in rows),final_screened_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),own_cutoff_parent_refinement_guard=True,acquisition_tool_sha256={str(p.relative_to(ROOT)):sha(p)for p in [ROOT/'tools/fetch_news.py',ROOT/'tools/expand_capped_news.py',ROOT/'tools/topics.py',ROOT/'tools/ready_feeds.py',ROOT/'tools/finalize_sources.py']})
 atomic_json(COVERAGE,coverage)
 atomic_json(ROOT/'audit/source_freeze.json',{'status':'all_22_ready','dates':rows,'query_plan_sha256':sha(PLAN),'coverage_sha256':sha(COVERAGE),'rules':coverage['rules'],'limits':coverage['limits'],'frozen_feeds_immutable':True,'candidates_all_compared_before_any_write':True,'candidate_manifest':'work/source_candidates/comparison_manifest.json','candidate_manifest_sha256':sha(stage/'comparison_manifest.json')})
if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--stage-only',action='store_true');args=ap.parse_args();main(stage_only=args.stage_only)
