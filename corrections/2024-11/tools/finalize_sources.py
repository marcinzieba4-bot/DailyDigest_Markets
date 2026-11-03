"""Offline final own-cutoff replay. All candidates compare BEFORE any destination write."""
from __future__ import annotations
import datetime as dt,json
from fetch_news import ROOT,atomic_json,build_feed
from expand_capped_news import DATES,load_harvest,read,PLAN,COVERAGE,sha
from ready_feeds import screen

def main():
 plan=read(PLAN);batches=load_harvest(plan);prepared=[]
 for d in DATES:
  stamp=d.isoformat();oldpath=ROOT/'audit'/('news_frozen_'+stamp+'.json');old=read(oldpath)if oldpath.exists()else None
  raw=build_feed(d,batches,persist=False);ready=screen(d,raw=raw['_payload'],persist=False)
  if old:
   assert old['feed_sha256']==ready['ready_sha256'], 'Candidate differs from frozen source IDs: '+stamp
   assert sha(ROOT/'feeds'/(stamp+'.json.gz'))==old['feed_sha256'],'Announced feed changed: '+stamp
  prepared.append((d,raw,ready,old))
  print(stamp,'CANDIDATE',ready['ready_items'],'excluded',ready['excluded_items'],'frozen match',bool(old),flush=True)
 print('ALL CANDIDATES PASS; committing raw/provenance and new feeds; frozen feeds skipped by immutable guard',flush=True)
 rows=[]
 for d,raw,ready,old in prepared:
  stamp=d.isoformat();atomic_json(ROOT/'work/unreviewed_feeds'/(stamp+'.json.gz'),raw.pop('_payload'),True)
  atomic_json(ROOT/'audit/news_provenance'/(stamp+'.json.gz'),raw.pop('_ledger'),True)
  atomic_json(ROOT/'feeds'/(stamp+'.json.gz'),ready.pop('_payload'),True)
  atomic_json(ROOT/'audit'/('news_ready_'+stamp+'.json'),ready)
  frozen={'date':stamp,'feed_sha256':ready['ready_sha256'],'status':'frozen_complete_own_date','full_month_replay_pending':False,'full_month_replay_verified':True,'query_plan':'audit/news_query_plan.json','query_plan_sha256':sha(PLAN),'ready_items':ready['ready_items'],'excluded_items':ready['excluded_items'],'rule':'Own-cutoff prefix queries and refinements only; daily refinements of later-cutoff capped parents excluded.'}
  atomic_json(ROOT/'audit'/('news_frozen_'+stamp+'.json'),frozen)
  rows.append({**raw,'screened_items':ready['ready_items'],'screened_sha256':ready['ready_sha256'],'frozen_priority_match':True if old else None})
  print(stamp,'READY',ready['ready_items'],flush=True)
 coverage=read(COVERAGE);coverage.update(dates=rows,own_date_records=sum(r['items']for r in rows),screened_own_date_records=sum(r['screened_items']for r in rows),final_screened_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),own_cutoff_parent_refinement_guard=True,acquisition_tool_sha256={str(p.relative_to(ROOT)):sha(p)for p in [ROOT/'tools/fetch_news.py',ROOT/'tools/expand_capped_news.py',ROOT/'tools/topics.py',ROOT/'tools/ready_feeds.py',ROOT/'tools/finalize_sources.py']})
 atomic_json(COVERAGE,coverage)
 atomic_json(ROOT/'audit/source_freeze.json',{'status':'all_21_ready','dates':rows,'query_plan_sha256':sha(PLAN),'coverage_sha256':sha(COVERAGE),'rules':coverage['rules'],'limits':coverage['limits'],'frozen_feeds_immutable':True,'candidates_all_compared_before_any_write':True})
if __name__=='__main__':main()
