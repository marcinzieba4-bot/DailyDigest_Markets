"""Independent finite public research projection mutation controls; no ZIP/report."""
from pathlib import Path
from unittest.mock import patch
import copy,datetime as dt,hashlib,importlib.util,json
ROOT=Path(__file__).resolve().parent.parent
def sha(blob):return hashlib.sha256(blob).hexdigest()
def module(name):
 p=ROOT/'tools'/f'{name}.py';s=importlib.util.spec_from_file_location('independent_public_'+name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
policy=module('build_source_inventory')
base_names={policy.PUBLIC_RESEARCH_MANIFEST,policy.PUBLIC_CLOCK_EVIDENCE,policy.PUBLIC_RESEARCH_ATTESTATION,'audit/independent_source_review.json','audit_work/june_release_schedule.json','tools/build_source_inventory.py'}
base={name:(ROOT/name).read_bytes() for name in base_names};source=json.loads(base['audit/independent_source_review.json']);manifest=json.loads(base[policy.PUBLIC_RESEARCH_MANIFEST]);evidence=json.loads(base[policy.PUBLIC_CLOCK_EVIDENCE]);attestation=json.loads(base[policy.PUBLIC_RESEARCH_ATTESTATION]);cases=[]
def candidate(mutate_manifest=None,mutate_evidence=None,mutate_attestation=None,extras=None):
 files=dict(base);m=copy.deepcopy(manifest);e=copy.deepcopy(evidence);a=copy.deepcopy(attestation)
 if mutate_evidence:mutate_evidence(e)
 files[policy.PUBLIC_CLOCK_EVIDENCE]=(json.dumps(e,ensure_ascii=False,indent=2)+'\n').encode();m['evidence_sha256']=sha(files[policy.PUBLIC_CLOCK_EVIDENCE])
 if mutate_manifest:mutate_manifest(m)
 files[policy.PUBLIC_RESEARCH_MANIFEST]=(json.dumps(m,ensure_ascii=False,indent=2)+'\n').encode();a.update(manifest_sha256=sha(files[policy.PUBLIC_RESEARCH_MANIFEST]),evidence_sha256=sha(files[policy.PUBLIC_CLOCK_EVIDENCE]))
 if mutate_attestation:mutate_attestation(a)
 files[policy.PUBLIC_RESEARCH_ATTESTATION]=(json.dumps(a,ensure_ascii=False,indent=2)+'\n').encode()
 files.update(extras or {});return files
def exercise(name,files,reject=True,custom_source=None):
 try:policy.validate_public_research_bundle(files.__getitem__,files,custom_source or source,require_review=False);blocked=False;reason='accepted'
 except (ValueError,KeyError,TypeError) as exc:blocked=True;reason=str(exc)
 cases.append({'case':name,'passed':blocked==reject,'expected_rejection':reject,'observed':reason})
exercise('exact_finite_public_bundle_positive',candidate(),reject=False)
for name,change in [
 ('duplicate_private_path',lambda m:m['private_files'].__setitem__(1,copy.deepcopy(m['private_files'][0]))),
 ('private_path_traversal',lambda m:m['private_files'][0].update(path='../outside.json')),
 ('private_path_absolute',lambda m:m['private_files'][0].update(path='/outside.json')),
 ('private_body_count_boolean',lambda m:m.update(private_file_count=True)),
 ('private_size_boolean',lambda m:m['private_files'][0].update(bytes=True)),
 ('private_size_zero',lambda m:m['private_files'][0].update(bytes=0)),
 ('private_sha_uppercase',lambda m:m['private_files'][0].update(sha256=m['private_files'][0]['sha256'].upper())),
 ('private_guard_membership',lambda m:m['private_files'][0].update(path='audit_work/june_release_schedule.json')),
 ('private_RSS_membership',lambda m:m['private_files'][0].update(path='cache/rss_raw/source.xml.gz')),
 ('private_proof_membership',lambda m:m['private_files'][0].update(path='audit/independent_source_review.json')),
 ('private_path_removed',lambda m:m['private_files'].pop()),
 ('private_sorted_order_changed',lambda m:m['private_files'].reverse()),
]:exercise(name,candidate(mutate_manifest=change))
unbound=next(n for n,row in enumerate(manifest['private_files']) if row['frozen_source_binding_sha256'] is None)
for value in [False,0,'',[],{}]:
 exercise('unbound_source_hash_must_be_JSON_null_'+type(value).__name__,candidate(mutate_manifest=lambda m,value=value:m['private_files'][unbound].update(frozen_source_binding_sha256=value)))
for name,change in [
 ('public_claim_original_body_replay',lambda a:a.update(public_original_research_byte_replay=True)),
 ('public_claim_financial_data_omitted',lambda a:a.update(financial_RSS_market_feed_guard_or_proof_omitted=True)),
 ('public_claim_independent_acceptance',lambda a:a.update(independent_acceptance=True)),
 ('public_claim_body_word_count_boolean',lambda a:a.update(copied_article_body_words=False)),
]:exercise(name,candidate(mutate_attestation=change))
raw={'content':[{'type':'text','text':'Synthetic document (https://example.org/private)\n【turn000】 [wordlim: 200] Total lines: 5\nSynthetic private body.'}]}
for path,payload in [
 ('audit_work/unregistered_raw.json',raw),
 ('audit/unregistered_raw.json',raw),
 ('audit/review_history/unregistered_raw.json',raw),
 ('reference/unregistered_raw.txt',raw),
 ('audit_work/raw_nested_reference.json',{'wrapper':{'response':raw}}),
 ('reference/raw_double_encoded.json',{'saved_response_json':json.dumps({'content':[{'type':'text','text':'Synthetic private https://example.org/private 【turn000】 body.'}]},ensure_ascii=True)}),
 ('audit_work/raw_with_extra_metadata.json',{**raw,'request_metadata':{'kind':'synthetic'}}),
]:exercise('raw_body_copy_rejected_'+path,candidate(extras={path:json.dumps(payload).encode()}))
exercise('raw_MCP_JSONL_copy_rejected_reference_text',candidate(extras={'reference/raw_jsonl.txt':(json.dumps({'metadata':'synthetic'})+'\n'+json.dumps(raw)+'\n').encode()}))
for private in [sorted(policy.PRIVATE_RESEARCH_PATHS)[0]]:
 exercise('registered_private_original_in_public_bundle',candidate(extras={private:json.dumps(raw).encode()}))
# Clock fields and finite metadata scope remain tied to unchanged policy bytes.
for name,change in [
 ('clock_guard_row_removed',lambda e:e['clock_rows'].pop()),
 ('clock_guard_release_changed',lambda e:e['clock_rows'][0].update(release_utc='2000-01-01T00:00:00Z')),
 ('article_body_top_level',lambda e:e.update(article_body='Synthetic private text')),
 ('article_body_source_field',lambda e:e['sources'][0].update(article_body='Synthetic private text')),
 ('nonempty_quote',lambda e:e['sources'][0].update(quote='Synthetic copied body')),
 ('unregistered_private_reference',lambda e:e['sources'][0].update(private_response_refs=['audit/unregistered.json'])),
 ('javascript_source_URL',lambda e:e['sources'][0].update(url='javascript:alert(1)')),
]:exercise(name,candidate(mutate_evidence=change))
result={'status':'independent_public_projection_controls_passed' if all(x['passed'] for x in cases) else 'independent_public_projection_controls_failed','checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'cases':cases,'case_count':len(cases),'failures':[x for x in cases if not x['passed']],'passed':all(x['passed'] for x in cases),'validator_sha256':sha((ROOT/'tools/build_source_inventory.py').read_bytes()),'reviewer_sha256':sha(Path(__file__).read_bytes()),'scope':'public_research_projection_engineering_only','archive_built':False,'full20_report_runtime_accepted':False}
(ROOT/'checks/independent_public_projection_controls.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'cases':len(cases),'passed':sum(x['passed'] for x in cases),'failures':[x['case'] for x in cases if not x['passed']]}))
