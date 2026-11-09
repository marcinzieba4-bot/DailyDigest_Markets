from pathlib import Path
import datetime as dt,hashlib,importlib.util,json,re,sys
from playwright.sync_api import sync_playwright
from pypdf import PdfReader
from bs4 import BeautifulSoup
ROOT=Path('/workspace/work/july2024');DATE='2024-07-24';OUT=ROOT/'work/july24_pdf_probe';STAGE=OUT/'staged'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def module(name,path):
 info=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(info);sys.modules[name]=m;info.loader.exec_module(m);return m
render=module('july24_fixed_render',ROOT/'tools/render.py');builder=module('july24_builder',ROOT/'tools/build_artifacts.py');reviewer=module('july24_reviewer',ROOT/'audit_work/review_final_artifacts.py')
prior=json.loads((ROOT/'audit/review_history/independent_artifact_tool_review_before_U2011_fix.json').read_text())
for name in ['tools/build_artifacts.py','audit_work/review_final_artifacts.py']:
 assert sha(ROOT/name)==prior['tool_sha256'][name],name+' changed unexpectedly'
builder.accepted_components([DATE])
inputs={}
for folder,suffix in [('specs','.json'),('feeds','.json.gz'),('cards','.json')]:
 src=ROOT/folder/(DATE+suffix);dest=STAGE/folder/src.name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(src.read_bytes());inputs[str(src.relative_to(ROOT))]=sha(src)
exception=ROOT/'audit/canonical_source_exceptions.json'
if exception.exists():
 dest=STAGE/'audit'/exception.name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(exception.read_bytes())
render.C=str(STAGE);render.render(DATE)
hp=STAGE/'html'/(DATE+'.html');jp=STAGE/'json'/(DATE+'_Market_Intelligence.json');pp=OUT/(DATE+'_after_U2011_fix.pdf');payload=json.loads(jp.read_text())
with sync_playwright()as p:
 browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':1440,'height':1000});page.set_content(hp.read_text());page.evaluate("document.querySelectorAll('details').forEach(x=>x.open=true)")
 page.pdf(path=str(pp),format='A4',print_background=True,margin={'top':'14mm','bottom':'16mm','left':'14mm','right':'14mm'},display_header_footer=True,header_template='<span></span>',footer_template='<div style="font-family:Arial;font-size:8px;width:100%;text-align:center;color:#8993a2">'+DATE+' · Market Intelligence Briefing · <span class="pageNumber"></span> / <span class="totalPages"></span></div>')
 layouts=[]
 for width,height in [(1440,1000),(390,844)]:
  page.set_viewport_size({'width':width,'height':height});page.set_content(hp.read_text());value=page.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth})');assert value['scroll']<=value['width'];layouts.append(value)
 browser.close()
pdf=PdfReader(pp);check=builder.check_pdf_prose(DATE,pdf,payload['spec'],payload['evidence'])
footer=re.compile(r'(?m)^'+DATE+r'\s*·\s*Market Intelligence Briefing\s*·\s*\d+\s*/\s*\d+\s*$');text='\n'.join(footer.sub('',x.extract_text()or'')for x in pdf.pages)
assert reviewer.pdf_preservation(DATE,text,payload['spec'],payload['evidence'])==149
assert reviewer.html_preservation(BeautifulSoup(hp.read_text(),'html.parser'),payload['spec'],payload['evidence'],DATE)==149
expected=payload['evidence']['n1020']['title'];assert reviewer.normal(expected)in reviewer.normal(text)
fonts=['Arial','DejaVu Sans','Noto Sans','Noto Sans Display','Noto Serif','Liberation Sans','Liberation Serif','OpenAI Sans','Times New Roman','Courier New','Noto Sans Mono']
rows=PdfReader(OUT/'font_matrix.pdf').pages[0].extract_text().splitlines();matrix=[]
for font,row in zip(fonts,rows):matrix.append({'font_family':font,'pdf_extracted_text':row,'hyphen_codepoints':[f'U+{ord(c):04X}'for c in row if c in '‑‐-'],'literal_2011_preserved':'Coca‑Cola'in row})
(OUT/'font_matrix_results.json').write_text(json.dumps({'font_matrix_pdf_sha256':sha(OUT/'font_matrix.pdf'),'rows':matrix},ensure_ascii=False,indent=2)+'\n')
for path,digest in inputs.items():assert sha(ROOT/path)==digest
result={'status':'accepted_single_date_render_regression_proof','date':DATE,'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'month_artifacts_reviewed':False,'publication_performed':False,'renderer_sha256':sha(ROOT/'tools/render.py'),'old_renderer_sha256':sha(ROOT/'audit/review_history/render_before_U2011_fix.py'),'unchanged_gate_sha256':{name:sha(ROOT/name)for name in ['tools/build_artifacts.py','audit_work/review_final_artifacts.py']},'input_sha256':inputs,'paragraphs_and_ledger':check,'pdf_pages':len(pdf.pages),'layouts':layouts,'n1020_title_exact_unicode_preserved':True,'expected_nonbreaking_hyphen':'U+2011','normalizers_changed':False,'files':{str(path.relative_to(ROOT)):sha(path)for path in [hp,jp,pp,OUT/'font_matrix.pdf',OUT/'font_matrix_results.json',Path(__file__)]}}
(OUT/'after_fix_receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
