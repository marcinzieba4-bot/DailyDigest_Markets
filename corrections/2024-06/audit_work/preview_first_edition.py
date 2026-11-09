"""Build only the explicitly authorized accepted June 3 presentation preview."""
from pathlib import Path
import datetime as dt,hashlib,importlib.util,json,re,sys
from playwright.sync_api import sync_playwright
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parent.parent
DATE='2024-06-03'
def module(name,path):
 info=importlib.util.spec_from_file_location(name,path);obj=importlib.util.module_from_spec(info);sys.modules[name]=obj;info.loader.exec_module(obj);return obj

def main():
 builder=module('june_preview_builder',ROOT/'tools/build_artifacts.py')
 render=module('june_preview_render',ROOT/'tools/render.py')
 reviewer=module('june_preview_reviewer',ROOT/'audit_work/review_final_artifacts.py')
 verifier=module('june_preview_verifier',ROOT/'tools/verify.py')
 builder.accepted_components([DATE]);fail,warn,sources,words=verifier.verify(DATE)
 if fail:raise ValueError(fail)
 render.render(DATE)
 directory=ROOT/'work/first_edition_preview';directory.mkdir(parents=True,exist_ok=True)
 html_path=ROOT/'html'/f'{DATE}.html';payload=json.loads((ROOT/'json'/f'{DATE}_Market_Intelligence.json').read_text())
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
  page.set_content(html_path.read_text(),wait_until='load')
  page.screenshot(path=str(directory/'desktop.png'))
  page.locator('#retail').scroll_into_view_if_needed();page.screenshot(path=str(directory/'retail.png'));page.evaluate('window.scrollTo(0,0)')
  page.evaluate("document.querySelectorAll('details').forEach(x=>x.open=true)")
  pdf_path=directory/(DATE+'.pdf')
  page.pdf(path=str(pdf_path),format='A4',print_background=True,margin={'top':'14mm','bottom':'16mm','left':'14mm','right':'14mm'},display_header_footer=True,header_template='<span></span>',footer_template='<div style="font-family:Arial;font-size:8px;width:100%;text-align:center;color:#8993a2">'+DATE+' · Market Intelligence Briefing · <span class="pageNumber"></span> / <span class="totalPages"></span></div>')
  desktop=page.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth,headings:document.querySelectorAll("h2[id]").length})')
  page.set_viewport_size({'width':390,'height':844});page.set_content(html_path.read_text(),wait_until='load');page.screenshot(path=str(directory/'mobile.png'))
  mobile=page.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth})')
  if desktop['scroll']>desktop['width'] or mobile['scroll']>mobile['width'] or desktop['headings']!=9:raise ValueError('Preview layout failure')
  browser.close()
 pdf=PdfReader(pdf_path)
 preservation=builder.check_pdf_prose(DATE,pdf,payload['spec'],payload['evidence'])
 footer=re.compile(r'(?m)^'+re.escape(DATE)+r'\s*·\s*Market Intelligence Briefing\s*·\s*\d+\s*/\s*\d+\s*$')
 text='\n'.join(footer.sub('',page.extract_text() or '') for page in pdf.pages)
 independent_count=reviewer.pdf_preservation(DATE,text,payload['spec'],payload['evidence'])
 from bs4 import BeautifulSoup
 html_count=reviewer.html_preservation(BeautifulSoup(html_path.read_text(),'html.parser'),payload['spec'],payload['evidence'],DATE)
 sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
 receipt={'status':'accepted_single_edition_preview','report_date':DATE,'month_artifacts_reviewed':False,'public_delivery_reviewed':False,'created_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'words':words,'distinct_sources':sources,'warnings':warn,'pdf_pages':len(pdf.pages),'pdf_preservation':preservation,'independent_pdf_paragraphs':independent_count,'html_paragraphs':html_count,'desktop':desktop,'mobile':mobile,'input_sha256':{str(path.relative_to(ROOT)):sha(path) for path in [ROOT/'specs'/f'{DATE}.json',ROOT/'feeds'/f'{DATE}.json.gz',ROOT/'cards'/f'{DATE}.json',ROOT/'tools/render.py',ROOT/'tools/build_artifacts.py',ROOT/'audit_work/review_final_artifacts.py']},'files':{str(path.relative_to(ROOT)):sha(path) for path in [html_path,ROOT/'json'/f'{DATE}_Market_Intelligence.json',pdf_path,directory/'desktop.png',directory/'retail.png',directory/'mobile.png']}}
 (directory/'preview_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(receipt,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
