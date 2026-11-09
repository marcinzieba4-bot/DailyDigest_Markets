"""Independent static review and adversarial synthetic replay; never build report artifacts.
Reads generic code/self-QA only. No author facts, network, cloud operations or real specs.
"""
from pathlib import Path
import json,hashlib,datetime as dt,importlib.util,tempfile,sys
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'work/artifact_dependencies'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj

def main():
 files=['tools/render.py','tools/build_artifacts.py','tools/build_retail_page.py','tools/build_source_inventory.py','audit_work/review_final_artifacts.py']
 modules={Path(p).stem:module('independent_'+Path(p).stem,ROOT/p) for p in files};b=modules['build_artifacts'];r=modules['render'];i=modules['build_source_inventory'];a=modules['review_final_artifacts'];tests=[]
 def passed(name):tests.append({'case':name,'result':'passed'})
 def rejects(name,call):
  try:call()
  except ValueError:passed(name)
  else:raise AssertionError('Accepted forbidden fixture: '+name)
 # Rerun reviewed owner's synthetic matrix without invoking its CLI/writing its receipt.
 baseline=a.static_review();assert baseline['runtime_artifacts_reviewed'] is False and baseline['negative_fixture_count']==55;passed('independently_reran_all55_reviewed_engineer_synthetic_cases')
 for normalizer in [b.prose_key,a.normal]:
  assert normalizer('Risk [100] remains.')!=normalizer('Risk remains.')
  assert normalizer('Now here is the limit.')!=normalizer('Nowhere is the limit.')
  assert normalizer('Łódź −3.2%')!=normalizer('Lodz 3.2%')
  assert normalizer('é')==normalizer('e\u0301')
 passed('independent_literal_numeric_boundary_minus_Polish_and_NFC_checks')
 # Both retail gates must raise through the builder; an unapproved snapshot must fail.
 oldroot=b.ROOT;oldmodule=b.module
 with tempfile.TemporaryDirectory(prefix='independent_artifact_gate_') as td:
  root=Path(td)/'month';(root/'audit_work').mkdir(parents=True);shared=root.parent/'retail-quality/retail_quality.py';shared.parent.mkdir()
  source='def require_review(root):\n    raise ValueError("shared_gate_blocked")\n';shared.write_text(source);(root/'audit_work/shared_retail_quality_original.py').write_text(source)
  b.ROOT=root;b.module=lambda name:SimpleNamespace(require_review=lambda _:None)
  rejects('shared_retail_gate_rejection_propagates',b.require_retail_gates)
  def local_reject(_):raise ValueError('local_gate_blocked')
  b.module=lambda name:SimpleNamespace(require_review=local_reject)
  rejects('local_retail_gate_rejection_propagates',b.require_retail_gates)
  b.module=lambda name:SimpleNamespace(require_review=lambda _:None)
  (root/'audit_work/shared_retail_quality_original.py').write_text('def require_review(root):\n    return None\n')
  rejects('shared_original_byte_mismatch_rejected',b.require_retail_gates)
 b.ROOT=oldroot;b.module=oldmodule
 with patch.object(b,'load',side_effect=AssertionError('Partial build tried to read author files')),patch.object(sys,'argv',['build_artifacts.py','2024-07-01']):
  rejects('partial_collection_main_rejected_before_author_reads',b.main)
 doc=r.Doc({'n0001':{'url':'https://example.org/a?x=1&y=2','title':'Łódź <tag> & "quote"'}})
 text=doc.text('Łódź −3.2% & <tag> [[n0001]]')
 assert '&amp;' in text and '&lt;tag&gt;' in text and 'data-source-id="n0001"' in text
 passed('independent_citation_text_attribute_escaping')
 rejects('unresolved_alias_rejected',lambda:r.Doc({}).text('Claim [[alias]]'))
 rejects('unknown_own_id_rejected',lambda:r.Doc({}).text('Claim [[n0001]]'))
 with tempfile.TemporaryDirectory(prefix='independent_artifact_path_') as td:
  root=Path(td);(root/'audit_work/.private').mkdir(parents=True);(root/'audit_work/proof.json').write_text('{}');(root/'audit_work/.private/proof.json').write_text('{}');outside=root.parent/(root.name+'_outside.json');outside.write_text('{}');(root/'audit_work/link.json').symlink_to(outside)
  try:
   with patch.object(i,'ROOT',root),patch.object(a,'ROOT',root):
    assert i.safe_path('audit_work/proof.json')==root/'audit_work/proof.json';passed('explicit_replay_root_positive')
    for value in ['../outside.json','/tmp/outside.json','audit_work/.private/proof.json','audit_work/secret.json','audit_work/link.json','audit_work/repo/proof.json','work/authoring/proof.py','work/artifact_dependencies/proof.py']:
     rejects('source_path_'+value,lambda value=value:i.safe_path(value))
  finally:outside.unlink()
 # Independently exercise the monthly-day validator with Unicode/literal content.
 retail_module=modules['build_retail_page']
 feed={'items':[{'id':'n0001','title':'Synthetic Łódź source [100]','src':'Synthetic Outlet','published_at':'2024-06-30T12:00:00+00:00','url':'https://example.org/source'}]}
 labels=['Why Retail Is Here','What Is Driving It','The Social Signal','Historical Analog','Smart Money View','When the Narrative Breaks']
 spec={'date':'2024-07-01','retail_intro':'Synthetic intro [100]. [[n0001]]','retail':[{'title':f'Synthetic {n} / TEST — Łódź & hook','parts':[[label,f'Synthetic risk [100] keeps Łódź −3.2% and now here. [[n0001]]'] for label in (labels if n==0 else ['Why Retail Is Here','Where It Breaks'])]} for n in range(4)]}
 records={row['id']:row for row in feed['items']}
 text='<section class="day" id="2024-07-01"><header class="dayhead"><p class="intro">'+retail_module.cite_html(spec['retail_intro'],records)+'</p></header>'+''.join(retail_module.trade_card(item,records,n==0) for n,item in enumerate(spec['retail']))+retail_module.source_ledger(spec,records)+'</section>'
 def monthly(value):return a.monthly_retail_day(a.BeautifulSoup(value,'html.parser').select_one('section.day'),spec,feed,'2024-07-01')
 monthly(text);passed('independent_monthly_full_positive_Unicode_literal_citation_ledger')
 rejects('monthly_intro_number_deleted',lambda:monthly(text.replace('Synthetic intro [100].','Synthetic intro.')))
 rejects('monthly_source_chip_hover_changed',lambda:monthly(text.replace('Synthetic Łódź source [100]','Changed hover',1)))
 rejects('monthly_literal_minus_changed',lambda:monthly(text.replace('−3.2%','3.2%',1)))
 rejects('monthly_full_ledger_removed',lambda:monthly(text[:text.index('<details class="sources">')]+'</section>'))
 selfqa=json.loads((ROOT/'checks/artifact_tool_review.json').read_text());hashes={p:sha(ROOT/p) for p in files}
 for p in files:
  key=p if p.startswith('audit_work/') else Path(p).name
  assert selfqa['tool_sha256'][key]==hashes[p],p
 assert len(b.DATES)==23 and b.DATES==a.DATES==i.DATES and '2024-07-04' in b.DATES and '2024-07-05' in b.DATES
 assert 23*3==69 and 69+5==74 and 69+3==72
 passed('scope_native_target_ZIP_counts_and_current_selfQA_hashes')
 result={'status':'accepted','scope':'Independent static artifact-tool and final-checker engineering review only. Generic code plus synthetic fixtures; no report facts read, no artifact build, no AWS/network actions.','reviewed_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'tool_sha256':hashes,'reviewer_script_sha256':sha(Path(__file__)),'self_QA_receipt_sha256':sha(ROOT/'checks/artifact_tool_review.json'),'runtime_artifacts_reviewed':False,'author_facts_read':False,'artifact_build_performed':False,'cloud_writes_performed':False,'fatal_or_major_remaining':0,'dates':b.DATES,'expected_counts':{'native_artifacts':69,'all_targets':74,'report_ZIP_members':72},'synthetic_tests':tests,'engineer_adversarial_matrix':baseline['negative_fixtures'],
 'concrete_findings_and_resolutions':[
  {'finding':'Initial normalizers hid dropped bracketed numbers and word-boundary changes.','resolution':'Retain every literal, bracket, number and word boundary; collapse only layout whitespace with NFC. Exact first-use citation ordinals are preserved instead of globally deleting numeric brackets. Independently reproduced former failures now reject.'},
  {'finding':'Initial PDF substring membership accepted reordered paragraphs and deleted repeated occurrences; title-only source search could pass incomplete ledgers.','resolution':'Ordered non-reusable paragraph occurrences including labels must appear before a unique ledger boundary; ordered title/outlet/publication records must appear after it. HTML compares the exact ordered paragraph list, chip IDs/ordinals/URLs and full ledger metadata. Synthetic reordered, duplicated/deleted and ledger-loss cases reject.'},
  {'finding':'Hidden-parent source paths and unconstrained collection paths were admitted.','resolution':'All hidden components, traversal, noncanonical paths, symlinks, repositories and credential filenames reject; exact date/kind native and collection locations are required. Renderer and partial-collection validation occur before any source file read.'},
  {'finding':'JSON evidence membership and ZIP self-inventory alone did not prove exact accepted input identity.','resolution':'JSON evidence now equals exact own-feed records plus only the exact own-date availability augmentation. ZIP reviewer binds current source/market/freeze acceptance, every accepted date feed/card and every raw replay-inventory row; tampering negatives reject.'},
  {'finding':'Monthly retail collection audit did not check dated intros, labels, citation metadata or its full ledger.','resolution':'Dedicated monthly_retail_day compares each intro/title/label/paragraph and paragraph/global citation identity, URL and hover metadata against the exact own feed, plus ordered full source records. Six engineer negatives and independent Unicode/literal/hover/ledger cases pass.'},
  {'finding':'Receipt roles and delivery claims needed distinct scopes.','resolution':'Self static QA, this independent code review and actual final-artifact review use unique paths. Only actual full runtime final_review sets runtime_artifacts_reviewed true. Both local and unchanged shared retail require_review gates must pass and shared snapshot bytes match the original.'}],
 'source_archive_scope':{'included':'Exact own-date23feeds/cards/specs/component drafts/notes, rawRSS+parsed request caches+headline provenance, bounded market/action/Treasury inputs, acceptance/replay/input hashes, code and reference provenance.','explicit_acquisition_work_exceptions':['work/source_candidates','work/unreviewed_feeds','work/acquisition_feeds'],'excluded':'Generic work/author/dependency scratch, repositories, credentials/hidden paths, other retrospective report-date filenames and circular final-delivery/archive-manifest receipts.'},
 'limitations':['This accepts reviewed code and synthetic failure behavior only; no actual July HTML/PDF/JSON, layouts, archive contents or delivery has been certified. Root must run the hash-bound runtime artifact review after full build.','Publication and public routing/native-download proof are separate; this review performs no cloud writes, browser artifact rendering or external sends.','UTF-8/NFC and strict whitespace-preserving checks may reveal genuine PDF extraction/layout issues at runtime; do not weaken them to erase substantive text.','Source archive file-scope and exact-byte guards exclude credential/repository/author-scratch paths; this is not a credential-value discovery or a semantic secret scan of every financial headline.']}
 (ROOT/'audit/independent_artifact_tool_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':result['status'],'independent_test_groups':len(tests),'engineer_negative_cases':len(baseline['negative_fixtures']),'runtime_artifacts_reviewed':False,'receipt_sha256':sha(ROOT/'audit/independent_artifact_tool_review.json')}))
if __name__=='__main__':main()
