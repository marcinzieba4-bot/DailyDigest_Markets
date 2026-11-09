"""Independent exact-Unicode renderer delta and existing July24 regression review.
No source/author edits, no artifact generation, no normalization exceptions.
"""
from pathlib import Path
import json,hashlib,ast,importlib.util,sys,re,difflib,datetime as dt
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'work/artifact_dependencies'))
from bs4 import BeautifulSoup
from pypdf import PdfReader
from playwright.sync_api import sync_playwright
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);obj=importlib.util.module_from_spec(spec);sys.modules[name]=obj;spec.loader.exec_module(obj);return obj

def main():
 old=ROOT/'audit/review_history/render_before_U2011_fix.py';new=ROOT/'tools/render.py';oldtext=old.read_text();newtext=new.read_text();expected=oldtext.replace('.verbatim-token{white-space:nowrap}.part-label{font-family:"DejaVu Sans",sans-serif;white-space:nowrap}', '.verbatim-token{white-space:nowrap}.part-label{font-family:"DejaVu Sans",sans-serif;white-space:nowrap}\n.literal-nbhyphen{font-family:"DejaVu Sans",sans-serif}')
 oldline="        chunks.append('<span class=\"verbatim-token\">'+html.escape(value,quote=False)+'</span>')"
 newline="        token_class='verbatim-token literal-nbhyphen' if '\\u2011' in value else 'verbatim-token'\n        chunks.append('<span class=\"'+token_class+'\">'+html.escape(value,quote=False)+'</span>')"
 expected=expected.replace(oldline,newline);assert expected==newtext,'Renderer diff exceeds approved CSS/class patch'
 owner=json.loads((ROOT/'audit/U2011_render_fix.json').read_text());proof=json.loads((ROOT/'work/july24_pdf_probe/after_fix_receipt.json').read_text());assert owner['renderer_sha256']==proof['renderer_sha256']==sha(new);assert owner['old_renderer_sha256']==sha(old)
 for name,digest in proof['unchanged_gate_sha256'].items():assert sha(ROOT/name)==digest
 normalizer_hashes={}
 for name,fn,digest in [('tools/build_artifacts.py','prose_key','db7800ddfa8191f4a8761423541c9ef4d1bf5ef8f81cbdd1c2b9c604fd68f90b'),('audit_work/review_final_artifacts.py','normal','10d09eae78045fe268de172a032b3ac274c8a61e46278a6529d20e157ed1e78b')]:
  s=(ROOT/name).read_text();n=next(n for n in ast.parse(s).body if isinstance(n,ast.FunctionDef)and n.name==fn);actual=hashlib.sha256(ast.get_source_segment(s,n).encode()).hexdigest();assert actual==digest;normalizer_hashes[name+':'+fn]=actual
 r=module('u2011_renderer',new);b=module('u2011_builder',ROOT/'tools/build_artifacts.py');a=module('u2011_auditor',ROOT/'audit_work/review_final_artifacts.py');checks=[]
 for literal in ['non\u2011breaking','non\u2010breaking','non-breaking','ordinary','2024-07-24T07:00:00+00:00','Łódź −3.2% & <tag>']:
  node=BeautifulSoup(r.esc(literal),'html.parser');assert node.get_text()==literal
  assert bool(node.select('.literal-nbhyphen'))==('\u2011' in literal);checks.append('Exact text/class control '+repr(literal))
 for norm in [b.prose_key,a.normal]:
  assert norm('non\u2011breaking')!=norm('non\u2010breaking');assert norm('Risk [100]')!=norm('Risk');assert norm('Now here')!=norm('Nowhere')
 checks.append('Both unchanged strict normalizers distinguish2011/2010, numeric literals and word boundaries')
 for name,digest in proof['input_sha256'].items():assert sha(ROOT/name)==digest
 for name,digest in proof['files'].items():assert sha(ROOT/name)==digest
 matrix=PdfReader(ROOT/'work/july24_pdf_probe/font_matrix.pdf');matrix_text=' '.join(p.extract_text()or''for p in matrix.pages);matrix_results=json.loads((ROOT/'work/july24_pdf_probe/font_matrix_results.json').read_text());assert matrix_results['font_matrix_pdf_sha256']==sha(ROOT/'work/july24_pdf_probe/font_matrix.pdf')
 selected={}
 for row in matrix_results['rows']:
  if row['font_family'] in ['Arial','DejaVu Sans','Noto Sans']:
   text=row['pdf_extracted_text'];assert a.normal(text) in a.normal(matrix_text);selected[row['font_family']]={'literal_2011_preserved':row['literal_2011_preserved'],'distinct_2011_and_2010_present':'\u2011'in text and'\u2010'in text}
 assert selected['Arial']['literal_2011_preserved']is False;assert selected['DejaVu Sans']['literal_2011_preserved']is True and selected['DejaVu Sans']['distinct_2011_and_2010_present'];assert selected['Noto Sans']['distinct_2011_and_2010_present']
 date='2024-07-24';payload=json.loads((ROOT/f'work/july24_pdf_probe/staged/json/{date}_Market_Intelligence.json').read_text());spec=json.loads((ROOT/f'specs/{date}.json').read_text());assert payload['spec']==spec
 import gzip
 feed=json.loads(gzip.decompress((ROOT/f'feeds/{date}.json.gz').read_bytes()));ex=ROOT/'audit/canonical_source_exceptions.json';exceptions=json.loads(ex.read_text()).get('exceptions',[])if ex.exists()else[];a.validate_evidence(payload['evidence'],spec,feed,exceptions,date)
 hp=ROOT/f'work/july24_pdf_probe/staged/html/{date}.html';html_count=a.html_preservation(BeautifulSoup(hp.read_text(),'html.parser'),spec,payload['evidence'],date);pdf=PdfReader(ROOT/f'work/july24_pdf_probe/{date}_after_U2011_fix.pdf');preservation=b.check_pdf_prose(date,pdf,spec,payload['evidence']);footer=re.compile(r'(?m)^'+date+r'\s*·\s*Market Intelligence Briefing\s*·\s*\d+\s*/\s*\d+\s*$');text='\n'.join(footer.sub('',p.extract_text()or'')for p in pdf.pages);count=a.pdf_preservation(date,text,spec,payload['evidence']);assert count==html_count==preservation['paragraphs_preserved']==149;assert preservation['ledger_headlines_preserved']==107 and len(pdf.pages)==29
 assert '\u2011'in payload['evidence']['n1020']['title'] and a.normal(payload['evidence']['n1020']['title'])in a.normal(text)
 try:a.pdf_preservation(date,text.replace('\u2011','\u2010'),spec,payload['evidence'])
 except ValueError:checks.append('ActualJuly24 strict PDF gate rejects2011→2010 mutation')
 else:raise AssertionError('Unicode-loss negative unexpectedly accepted')
 layouts=[]
 with sync_playwright()as p:
  browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page()
  for w,h in [(1440,1000),(390,844)]:
   page.set_viewport_size({'width':w,'height':h});page.set_content(hp.read_text(),wait_until='load');z=page.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth,headings:document.querySelectorAll("h2[id]").length})');assert z['scroll']<=w and z['headings']==9;layouts.append(z)
  browser.close()
 static=a.static_review();assert static['negative_fixture_count']==55
 retained=ROOT/'audit/U2011_render_fix_retained_proof.json';assert retained.is_file()
 for name in ['font_matrix_results.json','reproduce_after_fix.py']:assert (ROOT/'audit_work/u2011_render_fix'/name).read_bytes()==(ROOT/'work/july24_pdf_probe'/name).read_bytes()
 out={'status':'accepted','reviewed_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'scope':'Narrow renderer-only U+2011 PDF ToUnicode correction, unchanged strict normalizers and existing actual July24 transport/layout proof.','fatal_or_major_remaining':0,'old_renderer_sha256':sha(old),'new_renderer_sha256':sha(new),'renderer_changes':'Only DejaVu Sans class for an already-nowrap compound containing literal U+2011. No substitution, source/headline/card/spec edit, numeric claim or normalization exception.','normalizer_source_sha256':normalizer_hashes,'unchanged_gate_sha256':proof['unchanged_gate_sha256'],'static_adversarial_cases_replayed':55,'literal_controls':checks,'independently_read_font_matrix':selected,'actual_July24':{'ordered_paragraphs':count,'complete_ordered_ledger_records':107,'pdf_pages':29,'n1020_literal_U2011_preserved':True,'layouts':layouts,'input_sha256':proof['input_sha256'],'proof_file_sha256':proof['files']},'source_owner_delta_receipt_sha256':sha(ROOT/'audit/U2011_render_fix.json'),'source_retained_proof_sha256':sha(retained),'review_script_sha256':sha(Path(__file__)),'month_artifacts_reviewed':False,'public_delivery_reviewed':False,'new_artifacts_generated':False,'limits':['Only the accepted renderer delta and July24 regression are certified here; full23-edition rebuild and strict month audit remain required.','Financial/source-claim interpretation is not reconsidered; existing accepted prose and immutable feed/card identities are preserved.']}
 path=ROOT/'audit/independent_U2011_render_delta_review.json';path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':out['status'],'renderer_sha256':sha(new),'paragraphs':count,'ledger_records':107,'pdf_pages':29,'static_cases':55,'receipt_sha256':sha(path)}))
if __name__=='__main__':main()
