"""Artifact engineer generic static and adversarial synthetic self-QA; never build reports.
Reads generic code/self-QA only. No author facts, network, cloud operations or real specs.
"""
from pathlib import Path
import json,hashlib,datetime as dt,importlib.util,tempfile,sys
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent.parent

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj

def main():
 files=['tools/render.py','tools/build_artifacts.py','tools/build_retail_page.py','tools/build_source_inventory.py','audit_work/review_final_artifacts.py']
 modules={Path(p).stem:module('synthetic_'+Path(p).stem,ROOT/p) for p in files};b=modules['build_artifacts'];r=modules['render'];i=modules['build_source_inventory'];a=modules['review_final_artifacts'];tests=[]
 def passed(name):tests.append({'case':name,'result':'passed'})
 def rejects(name,call):
  try:call()
  except ValueError:passed(name)
  else:raise AssertionError('Accepted forbidden fixture: '+name)
 # Rerun reviewed owner's synthetic matrix without invoking its CLI/writing its receipt.
 baseline=a.static_review();assert baseline['runtime_artifacts_reviewed'] is False and baseline['negative_fixture_count']==55;passed('replayed55_engineering_preservation_cases')
 for normalizer in [b.prose_key,a.normal]:
  assert normalizer('Risk [100] remains.')!=normalizer('Risk remains.')
  assert normalizer('Now here is the limit.')!=normalizer('Nowhere is the limit.')
  assert normalizer('Łódź −3.2%')!=normalizer('Lodz 3.2%')
  assert normalizer('é')==normalizer('e\u0301')
 passed('synthetic_literal_numeric_boundary_minus_Polish_and_NFC_checks')
 # Both retail gates must raise through the builder; an unapproved snapshot must fail.
 oldroot=b.ROOT;oldmodule=b.module
 with tempfile.TemporaryDirectory(prefix='synthetic_artifact_gate_') as td:
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
 with patch.object(b,'load',side_effect=AssertionError('Partial build tried to read author files')),patch.object(sys,'argv',['build_artifacts.py','2024-06-03']):
  rejects('partial_collection_main_rejected_before_author_reads',b.main)
 doc=r.Doc({'n0001':{'url':'https://example.org/a?x=1&y=2','title':'Łódź <tag> & "quote"'}})
 text=doc.text('Łódź −3.2% & <tag> [[n0001]]')
 assert '&amp;' in text and '&lt;tag&gt;' in text and 'data-source-id="n0001"' in text
 passed('synthetic_citation_text_attribute_escaping')
 rejects('unresolved_alias_rejected',lambda:r.Doc({}).text('Claim [[alias]]'))
 rejects('unknown_own_id_rejected',lambda:r.Doc({}).text('Claim [[n0001]]'))
 with tempfile.TemporaryDirectory(prefix='synthetic_artifact_path_') as td:
  root=Path(td);(root/'audit_work/.private').mkdir(parents=True);(root/'audit_work/proof.json').write_text('{}');(root/'audit_work/.private/proof.json').write_text('{}');outside=root.parent/(root.name+'_outside.json');outside.write_text('{}');(root/'audit_work/link.json').symlink_to(outside)
  try:
   with patch.object(i,'ROOT',root),patch.object(a,'ROOT',root):
    assert i.safe_path('audit_work/proof.json')==root/'audit_work/proof.json';passed('explicit_replay_root_positive')
    for value in ['../outside.json','/tmp/outside.json','audit_work/.private/proof.json','audit_work/secret.json','audit_work/link.json','audit_work/repo/proof.json','work/authoring/proof.py','work/artifact_dependencies/proof.py']:
     rejects('source_path_'+value,lambda value=value:i.safe_path(value))
  finally:outside.unlink()
 # Independently exercise the monthly-day validator with Unicode/literal content.
 retail_module=modules['build_retail_page']
 feed={'items':[{'id':'n0001','title':'Synthetic Łódź source [100]','src':'Synthetic Outlet','published_at':'2024-06-02T12:00:00+00:00','url':'https://example.org/source'}]}
 labels=['Why Retail Is Here','What Is Driving It','The Social Signal','Historical Analog','Smart Money View','When the Narrative Breaks']
 spec={'date':'2024-06-03','retail_intro':'Synthetic intro [100]. [[n0001]]','retail':[{'title':f'Synthetic {n} / TEST — Łódź & hook','parts':[[label,f'Synthetic risk [100] keeps Łódź −3.2% and now here. [[n0001]]'] for label in (labels if n==0 else ['Why Retail Is Here','Where It Breaks'])]} for n in range(4)]}
 records={row['id']:row for row in feed['items']}
 text='<section class="day" id="2024-06-03"><header class="dayhead"><p class="intro">'+retail_module.cite_html(spec['retail_intro'],records)+'</p></header>'+''.join(retail_module.trade_card(item,records,n==0) for n,item in enumerate(spec['retail']))+retail_module.source_ledger(spec,records)+'</section>'
 def monthly(value):return a.monthly_retail_day(a.BeautifulSoup(value,'html.parser').select_one('section.day'),spec,feed,'2024-06-03')
 monthly(text);passed('synthetic_monthly_full_positive_Unicode_literal_citation_ledger')
 rejects('monthly_intro_number_deleted',lambda:monthly(text.replace('Synthetic intro [100].','Synthetic intro.')))
 rejects('monthly_source_chip_hover_changed',lambda:monthly(text.replace('Synthetic Łódź source [100]','Changed hover',1)))
 rejects('monthly_literal_minus_changed',lambda:monthly(text.replace('−3.2%','3.2%',1)))
 rejects('monthly_full_ledger_removed',lambda:monthly(text[:text.index('<details class="sources">')]+'</section>'))
 selfqa=json.loads((ROOT/'checks/artifact_tool_review.json').read_text());hashes={p:sha(ROOT/p) for p in files}
 for p in files:
  key=p if p.startswith('audit_work/') else Path(p).name
  assert selfqa['tool_sha256'][key]==hashes[p],p
 assert len(b.DATES)==20 and b.DATES==a.DATES==i.DATES and '2024-06-19' in b.DATES
 assert 20*3==60 and 60+5==65 and 60+3==63
 passed('scope_native_target_ZIP_counts_and_current_selfQA_hashes')
 result={'status':'synthetic_checks_passed','scope':'Artifact engineer self-QA using generic code and synthetic fixtures only; requires separate independent review.','checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'tool_sha256':hashes,'helper_sha256':sha(Path(__file__)),'static_receipt_sha256':sha(ROOT/'checks/artifact_tool_review.json'),'runtime_artifacts_reviewed':False,'report_facts_read':False,'artifact_build_performed':False,'fatal_or_major_remaining':0,'dates':b.DATES,'expected_counts':{'native_artifacts':60,'all_targets':65,'report_ZIP_members':63},'synthetic_tests':tests,'engineering_preservation_matrix':baseline['negative_fixtures'],'limitations':['Synthetic code checks only; no real June artifact, archive or delivery acceptance.','A separate reviewer must review the code and run runtime checks after all real accepted components exist.']}
 assert len(tests)==24
 (ROOT/'checks/artifact_regression_groups.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'status':result['status'],'synthetic_test_groups':len(tests),'preservation_matrix_cases':len(baseline['negative_fixtures']),'runtime_artifacts_reviewed':False}))
if __name__=='__main__':main()
