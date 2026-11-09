"""Root-only serial editorial omission helper; never alters immutable sources."""
from pathlib import Path
import datetime,gzip,hashlib,json
R=Path(__file__).resolve().parent.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();load=lambda p:json.loads(p.read_text())
def append(date,identity,evidence_path,reason,screen_kind='timing_uncertainty',extra=None,previous='audit/release_exclusions_amendment_2024-06-17_ing.json'):
 source=R/'audit/independent_source_review.json';freeze=R/'audit/source_freeze.json';gate=R/'audit/authoring_inputs_acceptance.json'
 assert sha(source)=='28c6fc6470cd3376055f6f447774509f3b6f863f550ce82858889ea4d85be170'
 for name,h in load(source)['input_bindings'].items():assert sha(R/name)==h,name
 immutable={str(p.relative_to(R)):sha(p)for p in[source,freeze,gate,R/'feeds'/f'{date}.json.gz',R/'cards'/f'{date}.json']}
 fp=R/'feeds'/f'{date}.json.gz';item=next(x for x in json.loads(gzip.decompress(fp.read_bytes()))['items']if x['id']==identity);proof=R/evidence_path
 row={'date':date,'id':identity,'feed_sha256':sha(fp),**{k:item[k]for k in['title','src','published_at']},'screen_kind':screen_kind,'reason':reason,'source_cutoff_utc':date+'T00:00:00Z','evidence_paths':[evidence_path],'evidence_sha256':{evidence_path:sha(proof)},'disposition':'exclude_from_report_claims_no_frozen_feed_mutation',**(extra or {})}
 registry=R/'audit/additional_release_exclusions.json';ep=R/'exclusions'/f'{date}.json';reg=load(registry);ex=load(ep);prior_rows=json.loads(json.dumps(reg['exclusions']));before=[]
 assert not any(x['id']==identity and x.get('date')==date for x in reg['exclusions'])
 assert not any(x['id']==identity for x in ex['exclusions'])
 for p in[registry,ep]:
  h=sha(p);bp=R/'audit/review_history'/f'{p.stem}_before_{date}_{identity}_{h}.json';assert not bp.exists();bp.write_bytes(p.read_bytes());before.append({'path':str(p.relative_to(R)),'sha256':h,'backup_path':str(bp.relative_to(R)),'backup_sha256':sha(bp)})
 reg['exclusions'].append(row);ex['exclusions'].append(row)
 registry.write_text(json.dumps(reg,ensure_ascii=False,indent=2)+'\n');ep.write_text(json.dumps(ex,ensure_ascii=False,indent=2)+'\n')
 assert load(registry)['exclusions'][:-1]==prior_rows
 for name,h in immutable.items():assert sha(R/name)==h,name
 for name,h in load(source)['input_bindings'].items():assert sha(R/name)==h,name
 amend={'schema':'controlled-retained-item-editorial-omission-amendment-v1','recorded_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'applied_controlled_own_date_timing_exclusion','affected_date':date,'new_excluded_ids':[identity],'feed_sha256':sha(fp),'card_sha256':sha(R/'cards'/f'{date}.json'),'original_source_review_sha256':sha(source),'original_source_freeze_sha256':sha(freeze),'original_authoring_acceptance_sha256':sha(gate),'previous_registry_amendment_path':previous,'previous_registry_amendment_sha256':sha(R/previous),'original_records_preserved':before,'current_records':{str(p.relative_to(R)):sha(p)for p in[registry,ep]},'effective_authoring_input_delta':{'date':date,'supersedes_only_field':'exclusions_sha256','original_value':before[1]['sha256'],'current_value':sha(ep),'feed_and_card_unchanged':True,'other_date_input_rows_not_modified':True,'prior_amendments_remain_in_effect':True,'original_authoring_gate_file_not_rewritten':True},'new_rows':[row],'proof_bindings':{evidence_path:sha(proof)},'checks':{'all144_immutable_source_bindings_unchanged':True,'prior_registry_rows_preserved_exactly':True,'per_date_registry_agree':True},'limits':['No automatic contentfix or acceptance. Independent own-date reviewer must separately bind current content/exclusions.','Only named own-date retained ID is excluded; frozenfinancialinputs stay immutable.']}
 p=R/'audit'/f'release_exclusions_amendment_{date}_{identity}.json';assert not p.exists();p.write_text(json.dumps(amend,indent=2)+'\n');print(date,identity,'exclusions',sha(ep),'amendment',sha(p));return p
