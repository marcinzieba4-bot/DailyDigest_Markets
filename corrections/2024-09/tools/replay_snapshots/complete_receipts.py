"""Bind independently verified staging, semantic exclusions and final immutable infrastructure bytes."""
from pathlib import Path
import json,hashlib,shutil,datetime as dt,gzip,re
R=Path('/workspace/work/sep2024/repo/corrections/2024-09');W=Path('/workspace/work/sep2024/audit_work');SN=R/'tools/replay_snapshots';SN.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2)+'\n')
D=[dt.date(2024,9,n).isoformat()for n in range(1,31)if dt.date(2024,9,n).weekday()<5]
stage=read(W/'stage_review.json');source=read(W/'source_review_draft.json');sem=read(W/'semantic_exclusions.json');market=read(R/'audit/independent_market_review.json')
assert stage['passed'] and source['passed'] and market['passed']
assert [x['date']for x in source['dates']]==D and market['dates']==D
assert source['source_freeze_sha256']==market['source_freeze_sha256']==sha(R/'audit/source_freeze.json')
for d in D:
 assert source['card_sha256'][d]==market['card_sha256'][d]==sha(R/'cards'/f'{d}.json')
 row=next(x for x in source['dates']if x['date']==d);st=next(x for x in stage['dates']if x['date']==d)
 assert row['feed_sha256']==st['feed_sha256']==sem['by_date'][d]['feed_sha256']==sha(R/'feeds'/f'{d}.json.gz')
 assert row['raw_sha256']==st['raw_sha256'] and row['provenance_sha256']==st['provenance_sha256']
for name,h in source['contract_sha256'].items():assert sha(R/name)==h==market['contract_sha256'][name]
def strings(x):
 if isinstance(x,dict):
  for v in x.values():yield from strings(v)
 elif isinstance(x,list):
  for v in x:yield from strings(v)
 elif isinstance(x,str):yield x
for d in D:
 assert not [q for q in strings(read(R/'cards'/f'{d}.json'))for q in re.findall(r'20\d\d-\d\d-\d\d',q)if q>d],d+' future date leakage in writer metadata'
market['checks']+=len(D)
market['checks_by_scope']['writer_metadata_date_isolation']=len(D)
market['writer_metadata_date_isolation']='Every ISO date string in every final writer card is at or before its own report date; future action dates remain audit-only.'

for name in ['review_sources.py','semantic_exclusions.py','review_market.py','bind_source_freeze.py','complete_receipts.py','independent_treasury_2024_through_2024-09-27.csv','independent_treasury_request.json']:
 shutil.copyfile(W/name,SN/name)
shutil.copyfile(W/'physical_source_inventory.json',R/'audit/independent_physical_source_inventory.json')
shutil.copyfile(W/'stage_review.json',R/'audit/independent_stage_review.json')
shutil.copyfile(W/'accepted_candidate_manifest.json',R/'audit/independent_prefreeze_candidate_manifest.json')
shutil.copyfile(W/'semantic_exclusions.json',R/'audit/independent_headline_exclusions.json')
shutil.copyfile(W/'selected_boundary_checks.json',R/'audit/independent_selected_boundary_checks.json')
author_files={}
for d in D:
 path=R/'audit/author_exclusions'/f'{d}.json'
 row={'date':d,'status':'selected_exclusions_only_requires_own_claim_review','cutoff_utc':d+'T00:00:00Z','feed_sha256':sem['by_date'][d]['feed_sha256'],'card_sha256':source['card_sha256'][d],'scope':'Current-date selected exclusions/advisories only. Every other exact claim still requires this own frozen headline/card review. No original publication vintage is certified.','exclusions':sem['by_date'][d]['exclusions'],'advisories':sem['by_date'][d]['advisories']}
 if d in read(W/'selected_boundary_checks.json'):row['selected_boundary_check']=read(W/'selected_boundary_checks.json')[d]
 write(path,row);author_files[str(path.relative_to(R))]=sha(path)
source.update({'status':'accepted_for_authoring_with_semantic_exclusions','infrastructure_status':'accepted','semantic_status':'requires_own_claim_review','stage_review_path':'audit/independent_stage_review.json','stage_review_sha256':sha(R/'audit/independent_stage_review.json'),'headline_exclusions_path':'audit/independent_headline_exclusions.json','headline_exclusions_sha256':sha(R/'audit/independent_headline_exclusions.json'),'prefreeze_candidate_manifest_path':'audit/independent_prefreeze_candidate_manifest.json','physical_source_inventory_path':'audit/independent_physical_source_inventory.json','physical_source_inventory_sha256':sha(R/'audit/independent_physical_source_inventory.json'),'replay_tool_sha256':{str(p.relative_to(R)):sha(p)for p in sorted(SN.iterdir())if p.is_file()},'known_semantic_exclusions':{'status':sem['status'],'scope':sem['scope'],'by_date':sem['by_date'],'counts':sem['counts'],'finite_rule_count':sem['finite_rule_count'],'limits':sem['limits']},'known_timing_exclusions':{'scope':'Selected impossible actuals and nominal publication-date anomalies; by-date only. Absence from this list is not semantic acceptance.','by_date':{d:{'feed_sha256':sem['by_date'][d]['feed_sha256'],'exclusions':[x for x in sem['by_date'][d]['exclusions']if any('actual' in q or 'cutoff' in q or 'released' in q or 'session' in q for q in x['reasons'])],'advisories':sem['by_date'][d]['advisories']}for d in D}},'original_publication_vintage_status':'not_certified','selected_boundary_checks':read(W/'selected_boundary_checks.json'),'selected_boundary_checks_path':'audit/independent_selected_boundary_checks.json','selected_boundary_checks_sha256':sha(R/'audit/independent_selected_boundary_checks.json'),'independent_replay_tool':{'path':str(W/'review_sources.py'),'sha256':sha(W/'review_sources.py')},'reviewed_report_claims':0,'author_exclusion_path_pattern':'audit/author_exclusions/YYYY-MM-DD.json','author_exclusion_sha256':author_files,'author_access_rule':'Authors receive only their current date row of known exclusions/advisories and may inspect only their own frozen feed/card. No later-date reviewer data is evidence.','final_exact_binding_checked':True})
# Rebind replay metadata after snapshots are preserved; source feeds/cards remain immutable.
market.update({'independent_replay_tool':{'path':str(W/'review_market.py'),'sha256':sha(W/'review_market.py')},'infrastructure_status':'accepted','replay_tool_sha256':{str(p.relative_to(R)):sha(p)for p in sorted(SN.iterdir())if p.is_file()},'source_review_infrastructure_status':'accepted','semantic_status':'requires_own_claim_review','original_publication_vintage_status':'not_certified','final_exact_binding_checked':True})
write(R/'audit/independent_source_review.json',source);write(R/'audit/independent_market_review.json',market)
print(json.dumps({'source_status':source['status'],'source_checks':source['checks'],'semantic_exclusions':sum(sem['counts'].values()),'market_status':market['status'],'market_checks':market['checks'],'source_receipt_sha256':sha(R/'audit/independent_source_review.json'),'market_receipt_sha256':sha(R/'audit/independent_market_review.json')},indent=2))
