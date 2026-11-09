"""Controlled retained-item omissions; immutable news/card/source proofs are read-only."""
from pathlib import Path
import datetime as dt,gzip,hashlib,json,re,shutil
from zoneinfo import ZoneInfo
R=Path(__file__).resolve().parent.parent
sha=lambda b:hashlib.sha256(b).hexdigest()
js=lambda x:(json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode()
now=dt.datetime.now(dt.timezone.utc);stamp=now.strftime('%Y%m%dT%H%M%SZ')
def preserve(rel,label):
 p=R/rel;b=p.read_bytes();target=R/'audit/review_history'/f'{label}_{stamp}.json';assert not target.exists();target.write_bytes(b);assert target.read_bytes()==b
 return {'path':rel,'sha256':sha(b),'backup_path':str(target.relative_to(R)),'backup_sha256':sha(target.read_bytes()),'bytes':len(b)}
source=json.loads((R/'audit/independent_source_review.json').read_bytes());freeze=json.loads((R/'audit/source_freeze.json').read_bytes());accept_bytes=(R/'audit/authoring_inputs_acceptance.json').read_bytes();accept=json.loads(accept_bytes)
assert source['passed']and source['authoring_acceptance']and accept['passed']
immutable={p:sha((R/p).read_bytes())for p in source['input_bindings']}
immutable.update({'audit/independent_source_review.json':sha((R/'audit/independent_source_review.json').read_bytes()),'audit/authoring_inputs_acceptance.json':sha(accept_bytes)})
for rel,expected in source['input_bindings'].items():assert sha((R/rel).read_bytes())==expected,rel
feedpath=R/'feeds/2024-06-17.json.gz';feedsha=sha(feedpath.read_bytes());feed=json.loads(gzip.decompress(feedpath.read_bytes()));byid={x['id']:x for x in feed['items']}
assert feedsha=='064f0e18017bdf95650d04828ffa6b71daf7c87ca83c6d823a738f1d92e5e7a3'
oldex=json.loads((R/'exclusions/2024-06-17.json').read_bytes());registry=json.loads((R/'audit/additional_release_exclusions.json').read_bytes());assert oldex['date']=='2024-06-17'and oldex['feed_sha256']==feedsha
assert not oldex['exclusions']and not registry['exclusions'],'Unexpected concurrent editorial amendment; preserve and reconcile before extending'
backups=[preserve('exclusions/2024-06-17.json','exclusions_2024-06-17_before_china_actuals'),preserve('audit/additional_release_exclusions.json','additional_release_exclusions_before_2024-06-17_china_actuals'),preserve('audit/authoring_inputs_acceptance.json','authoring_inputs_acceptance_original_before_2024-06-17_china_actuals')]
proofs=['audit_work/june17_china_release_timing_search.json','audit_work/june17_nbs_primary_release_search.json','audit_work/june17_nbs_primary_release_pages.json'];proofmap={p:sha((R/p).read_bytes())for p in proofs}
events={'n0298':('China Home-Price Slump Accelerates Despite More Stimulus - Bloomberg.com','2024-06-17T09:30:00','https://www.stats.gov.cn/sj/zxfb/202406/t20240617_1954705.html','May2024 sales prices in70cities'), 'n0299':("China's factory output disappoints, property sector stuck in doldrums - Reuters",'2024-06-17T10:00:00','https://www.stats.gov.cn/sj/zxfb/202406/t20240617_1954712.html','May2024 industrialproduction')}
rows=[]
for identity,(title,local,url,event)in events.items():
 item=byid[identity];assert item['title']==title and item['published_at']=='2024-06-16T07:00:00+00:00'
 release=dt.datetime.fromisoformat(local).replace(tzinfo=ZoneInfo('Asia/Shanghai')).astimezone(dt.timezone.utc);assert release>dt.datetime(2024,6,17,tzinfo=dt.timezone.utc)
 rows.append({'date':'2024-06-17','id':identity,'feed_sha256':feedsha,'title':title,'src':item['src'],'published_at':item['published_at'],'screen_kind':'timing','reason':'Headline describes a completed May China data outcome released after the June17 00:00UTC cutoff. Normalized June16 RSS timestamp cannot establish pre-release availability; omit this retained item only for June17.','release_event':event,'release_local':local+'+08:00','release_utc':release.isoformat(),'release_clock_evidence_url':url,'release_clock_evidence_sha256':proofmap['audit_work/june17_nbs_primary_release_pages.json'],'evidence_paths':proofs,'source_cutoff_utc':'2024-06-17T00:00:00+00:00','disposition':'exclude_from_report_claims_no_frozen_feed_mutation'})
oldex['exclusions'].extend(rows);registry['exclusions'].extend(rows)
(R/'exclusions/2024-06-17.json').write_bytes(js(oldex));(R/'audit/additional_release_exclusions.json').write_bytes(js(registry))
affected=next(x for x in accept['inputs']if x['date']=='2024-06-17');assert affected['feed_sha256']==feedsha and affected['exclusions_sha256']==backups[0]['sha256']
newexsha=sha((R/'exclusions/2024-06-17.json').read_bytes());component=R/'nonretail_drafts/2024-06-17.json';component_check={'exists':component.is_file(),'status':'not_yet_written'if not component.is_file()else'checked_current_component_for_excluded_citations','no_prose_approval':True}
if component.is_file():
 body=component.read_bytes();data=json.loads(body);cites=set(re.findall(r'\[\[(n\d{4,6})\]\]',json.dumps(data,ensure_ascii=False)));component_check.update(sha256=sha(body),excluded_citations=sorted(cites&set(events)),passed=not bool(cites&set(events)))
for rel,digest in immutable.items():assert sha((R/rel).read_bytes())==digest,rel
out={'schema':'controlled-retained-item-editorial-omission-amendment-v1','recorded_at_utc':now.isoformat(),'status':'applied_controlled_own_date_timing_exclusions','authorizing_scope':'Root delegated narrow independent June17 timing adjudication and editorial exclusions; no author messages or prose changes.','affected_date':'2024-06-17','new_excluded_ids':list(events),'immutable_source_review_sha256':sha((R/'audit/independent_source_review.json').read_bytes()),'immutable_source_freeze_sha256':sha((R/'audit/source_freeze.json').read_bytes()),'feed_sha256':feedsha,'card_sha256':sha((R/'cards/2024-06-17.json').read_bytes()),'original_authoring_acceptance':backups[2],'original_records_preserved':backups,'current_records':{'exclusions/2024-06-17.json':newexsha,'audit/additional_release_exclusions.json':sha((R/'audit/additional_release_exclusions.json').read_bytes())},'effective_authoring_input_delta':{'date':'2024-06-17','supersedes_only_field':'exclusions_sha256','original_value':backups[0]['sha256'],'current_value':newexsha,'feed_and_card_unchanged':True,'all_other_original_authoring_input_rows_unchanged':True,'original_authoring_acceptance_file_not_rewritten':True},'new_rows':rows,'proof_bindings':proofmap,'current_component_check':component_check,'all_144_immutable_source_bindings_unchanged':True,'limits':['China-local NBS display clocks are interpreted in Asia/Shanghai UTC+08:00. No original earlier article/headline vintage is certified.','Only exactJune17 retaineditemIDs n0298/n0299 are omitted. Frozenfeeds/cards/guards/sourcefreeze/sourceacceptance remain byte-identical.','This amends mutableeditorial exclusions and the effectiveJune17 authoring-input exclusionbinding only; it is not factual/prose acceptance.']}
receipt=R/'audit/release_exclusions_amendment_2024-06-17_china_actuals.json';assert not receipt.exists();receipt.write_bytes(js(out));print(json.dumps({'receipt':str(receipt.relative_to(R)),'receipt_sha256':sha(receipt.read_bytes()),'current_records':out['current_records'],'component_check':component_check,'original_authoring_gate_sha256':backups[2]['sha256']},indent=2))
