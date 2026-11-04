"""Bind already independently replayed candidate bytes to final immutable destinations.
Avoids repeating physical RSS reparse after a byte-identical destination copy.
"""
from pathlib import Path
import json,gzip,hashlib,datetime as dt
R=Path('/workspace/work/sep2024/repo/corrections/2024-09');W=Path(__file__).resolve().parent
D=[dt.date(2024,9,n).isoformat()for n in range(1,31)if dt.date(2024,9,n).weekday()<5]
def read(p):return json.loads(gzip.decompress(p.read_bytes())if p.suffix=='.gz' else p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
s=read(W/'stage_review.json');assert s['passed'] and s['status']=='staged_infrastructure_verified'
errors=[];n=0
def ck(v,m):
 global n;n+=1
 if not v:errors.append(m)
f=read(R/'audit/source_freeze.json');m=read(R/'work/source_candidates/comparison_manifest.json');pm=read(W/'accepted_candidate_manifest.json')
ck(m==pm,'Finalizer preserved exact already-reviewed candidate manifest')
ck(f['status']=='all_21_ready' and f['frozen_feeds_immutable'] and f['candidates_all_compared_before_any_write'],'Global immutable source freeze')
ck([r['date']for r in s['dates']]==[r['date']for r in f['dates']]==D,'Exact21 weekday dates')
ck(s['query_plan_sha256']==f['query_plan_sha256']==sha(R/'audit/news_query_plan.json'),'Exact physical queryplan binding')
ck(f['candidate_manifest_sha256']==sha(R/'work/source_candidates/comparison_manifest.json')==sha(W/'accepted_candidate_manifest.json'),'Exact prefreeze manifest binding')
ck(f['coverage_sha256']==sha(R/'audit/news_coverage.json'),'Finalcoverage hash binding')
for name,h in s['tool_sha256'].items():ck(sha(R/'tools'/name)==h,'Owner source tool unchanged since independent replay '+name)
for name,h in s['contract_sha256'].items():ck(sha(R/name)==h,'Contract unchanged since independent replay '+name)
for row in s['dates']:
 d=row['date'];feed=R/'feeds'/f'{d}.json.gz';raw=R/'work/unreviewed_feeds'/f'{d}.json.gz';prov=R/'audit/news_provenance'/f'{d}.json.gz';ready=R/'audit'/f'news_ready_{d}.json';fr=read(R/'audit'/f'news_frozen_{d}.json');rr=read(ready);sr=read(R/'work/source_candidates/ready_receipts'/f'news_ready_{d}.json')
 ck(sha(feed)==row['feed_sha256']==rr['ready_sha256']==fr['feed_sha256']==sha(R/'work/source_candidates/feeds'/f'{d}.json.gz'),d+' byte-identical frozen feed')
 ck(sha(raw)==row['raw_sha256']==rr['unreviewed_sha256']==sha(R/'work/source_candidates/unreviewed_feeds'/f'{d}.json.gz'),d+' byte-identical raw feed')
 ck(sha(prov)==row['provenance_sha256']==sha(R/'work/source_candidates/news_provenance'/f'{d}.json.gz'),d+' byte-identical provenance')
 ck(rr==sr,d+' exact staged exclusion/ready receipt')
 ck(fr['full_month_replay_verified'] and not fr['full_month_replay_pending'] and fr['query_plan_sha256']==s['query_plan_sha256'],d+' immutable completion receipt')
 ck(len(read(feed)['items'])==row['ready_items'] and rr['excluded_items']==row['excluded'],d+' independently reconstructed retained/excluded counts')
 row['ready_receipt_sha256']=sha(ready)
s.update(status='accepted_for_authoring_with_semantic_exclusions'if not errors else 'failed',passed=not errors,infrastructure_status='accepted'if not errors else 'failed',source_freeze_sha256=sha(R/'audit/source_freeze.json'),card_sha256={d:sha(R/'cards'/f'{d}.json')for d in D},prefreeze_candidate_manifest_sha256=sha(W/'accepted_candidate_manifest.json'),stage_replay_checks=s['checks'],postfreeze_binding_checks=n,checks=s['checks']+n,checks_by_scope=s['checks_by_scope']|{'postfreeze_exact_binding':n},errors=errors,physical_replay_repeated_after_copy=False,postfreeze_method='Every frozen feed/raw/provenance and ready receipt byte-matches the already independently replayed and physically compared candidates. The global freeze binds exact plan, coverage and candidate manifest.')
(W/'source_review_draft.json').write_text(json.dumps(s,indent=2)+'\n');print(json.dumps({'status':s['status'],'checks':s['checks'],'binding_checks':n,'errors':errors},indent=2));raise SystemExit(bool(errors))
