"""Independently read local artifacts. --available writes per-PDF receipts; --final requires root-authorized full22 build.
No artifact/prose changes, acquisition, network or publication calls. Only checker receipts are written.
"""
from pathlib import Path,PurePosixPath
import argparse,concurrent.futures as cf,datetime as dt,gzip,hashlib,json,re,unicodedata,zipfile
from bs4 import BeautifulSoup
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parent.parent
DATES=[dt.date(2024,8,n).isoformat() for n in range(1,32) if dt.date(2024,8,n).weekday()<5]
SECTIONS=['geo','sectors','earnings','underowned','crypto','flows','anticipatory','catalysts','retail']
FOOTER=re.compile(r'\d{4}-\d{2}-\d{2}\s*·\s*Market Intelligence Briefing\s*·\s*\d+\s*/\s*\d+')
CITES=re.compile(r'\[\[n\d+\]\]|\[\s*\d+\s*\]')

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def atomic(p,value):
 p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.check.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');tmp.replace(p)
def normalize(text,remove_citations=False):
 # NFKC expands ligatures/compatibility forms. Unicode word tokens ignore typography and whitespace;
 # every word and numeral, including decimal components, remains ordered. No fuzzy matching/waivers.
 text=unicodedata.normalize('NFKC',text).replace('\u00ad','').replace('\u200b','')
 # CJK words may wrap between glyphs in PDF extraction; preserve every character while joining only CJK-to-CJK whitespace.
 cjk=r'[\u2e80-\u2fff\u3040-\u30ff\u31f0-\u31ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]'
 text=re.sub(r'(?<='+cjk+r')\s+(?='+cjk+r')','',text)
 if remove_citations:text=CITES.sub(' ',text)
 return ' '.join(re.findall(r'\w+',text.lower()))
def paragraphs(spec):
 result=[]
 def walk(x,path):
  if isinstance(x,dict):
   if isinstance(x.get('parts'),list):
    for n,pair in enumerate(x['parts']):result.append((path+'.parts.'+str(n),pair[1]))
   for k,v in x.items():
    if k!='parts':walk(v,path+'.'+k)
  elif isinstance(x,list):
   for n,v in enumerate(x):walk(v,path+'.'+str(n))
 walk(spec,'spec');result.append(('spec.retail_intro',spec['retail_intro']));return result

def check_pdf(date):
 errors=[];checks=0
 def ck(ok,message,detail=None):
  nonlocal checks
  checks+=1
  if not ok:errors.append({'error':message,**({'detail':detail} if detail is not None else {})})
 rp=ROOT/'checks/artifacts'/f'{date}.json';receipt=read(rp);paths={'spec':ROOT/'specs'/f'{date}.json','feed':ROOT/'feeds'/f'{date}.json.gz','card':ROOT/'cards'/f'{date}.json','layout_receipt':rp,**{ext:ROOT/row['path'] for ext,row in receipt['files'].items()}};bindings={k:{'path':str(p.relative_to(ROOT)),'sha256':sha(p),'bytes':p.stat().st_size} for k,p in paths.items()};tool_hash=sha(Path(__file__));cached=ROOT/'checks/independent_pdf'/f'{date}.json'
 if cached.is_file():
  old=read(cached)
  if old.get('input_bindings')==bindings and old.get('reviewer_tool_sha256')==tool_hash:return old
 ck(set(receipt['files'])=={'html','json','pdf'},'three native formats');ck(receipt['date']==date,'receipt date');ck(all(receipt[k+'_sha256']==bindings[k]['sha256'] for k in ['spec','feed','card']),'spec/feed/card layout bindings');ck(receipt['renderer_sha256']==sha(ROOT/'tools/render.py') and receipt['builder_sha256']==sha(ROOT/'tools/build_artifacts.py'),'renderer/builder layout bindings')
 for ext,row in receipt['files'].items():ck(row['sha256']==bindings[ext]['sha256'] and row['bytes']==bindings[ext]['bytes'],ext+' body matches receipt')
 spec=read(paths['spec']);data=read(paths['json']);feed={x['id']:x for x in read(paths['feed'])['items']};soup=BeautifulSoup(paths['html'].read_text(),'html.parser');pdf=PdfReader(paths['pdf']);page_texts=[p.extract_text() or '' for p in pdf.pages];cleaned_pages=[FOOTER.sub(' ',s) for s in page_texts];pdf_text=' '.join(cleaned_pages);pdf_norm=normalize(pdf_text,True);head_norm=normalize(pdf_text);cited=set(re.findall(r'\[\[(n\d+)\]\]',json.dumps(spec,ensure_ascii=False)))
 ck(spec['date']==date and data['report_date']==date and data['news_cutoff_utc']==date+'T00:00:00Z','spec/JSON own date');ck(data['spec']==spec,'JSON preserves exact spec');ck(set(data['evidence'])==cited,'JSON evidence exactly all cited IDs');ck(cited<=set(feed),'all cited IDs in own feed');ck(len(pdf.pages)==receipt['pdf_pages'] and all(page_texts),'PDF actual pages match layout receipt and all pages have text')
 headings=soup.select('h2[id]');ck([h['id'] for h in headings]==SECTIONS,'HTML exact nine sections')
 for h in headings:ck(normalize(h.get_text(' ',strip=True)) in head_norm,'PDF section heading '+h['id'])
 ledger=soup.select_one('details.ledger');ck(ledger is not None,'final source ledger in HTML');ledger_rows=ledger.select('ol li') if ledger else [];ck(len(ledger_rows)==len(cited)==receipt['distinct_sources'],'source counts HTML/JSON/receipt agree');marker=normalize('Dated evidence '+str(len(cited))+' sources');ck(marker in head_norm,'PDF final dated-source ledger marker/count');ledger_norm=head_norm.rsplit(marker,1)[-1] if marker in head_norm else '';missing_headlines=[]
 for key,item in data['evidence'].items():
  title_norm=normalize(item['title']);ck(title_norm in ledger_norm,'full cited headline in PDF final ledger',{'id':key,'title':item['title']})
  if title_norm not in ledger_norm:missing_headlines.append(key)
  ck(all(item.get(k)==feed[key].get(k) for k in ['title','url','src','source_url','published_at']),'JSON evidence equals dated feed '+key);ck(dt.datetime.fromisoformat(item['published_at'])<dt.datetime.fromisoformat(date).replace(tzinfo=dt.timezone.utc),'cited source before cutoff '+key)
 if ledger:ledger.decompose()
 for anchor in soup.select('.source-cite'):anchor.decompose()
 html_norm=normalize(soup.get_text(' ',strip=True),True);expected=paragraphs(spec);missing_pdf=[];missing_html=[]
 for path,body in expected:
  target=normalize(body,True);inpdf=target in pdf_norm;inhtml=target in html_norm
  ck(inpdf,'full paragraph in PDF',{'path':path,'text_sha256':hashlib.sha256(body.encode()).hexdigest(),'excerpt':body[:240]});ck(inhtml,'full paragraph in HTML '+path)
  if not inpdf:missing_pdf.append(path)
  if not inhtml:missing_html.append(path)
 ck(receipt['layout']['headings']==9 and receipt['layout']['scroll']<=receipt['layout']['width'] and receipt['mobile_overflow'] is False,'recorded desktop/mobile layout success');ck(not soup.select('.snapshot,.metric,.momentum'),'no removed dashboard selectors in HTML')
 for k,p in paths.items():ck(sha(p)==bindings[k]['sha256'],'input unchanged during independent check '+k)
 out={'date':date,'passed':not errors,'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'checks':checks,'errors':errors,'input_bindings':bindings,'pdf_pages':len(pdf.pages),'source_count':len(cited),'section_count':len(headings),'full_paragraphs_checked':len(expected),'full_paragraphs_found_in_pdf':len(expected)-len(missing_pdf),'full_paragraphs_found_in_html':len(expected)-len(missing_html),'missing_pdf_paragraphs':missing_pdf,'missing_html_paragraphs':missing_html,'missing_pdf_headlines':missing_headlines,'reviewer_tool_sha256':tool_hash,'scope':'One local saved edition; all cited full headlines in final PDF ledger, all nine headings, and every spec parts-body plus retail intro compared with extracted PDF and HTML. Existing desktop/mobile execution receipts are hash-bound and inspected; no browser render rerun.','normalization':'Unicode NFKC, invisible soft-hyphen/zero-width removal, CJK-to-CJK line-wrap whitespace joining, ordered Unicode word/numeral tokens and whitespace folding. Citation-number chips and exact repeated PDF footer removed for paragraph matching; no fuzzy or partial-text exceptions. Typography/punctuation differences are outside this text-completeness check.','limits':['Full paragraph matching verifies every textual word/numeral sequence, not identical punctuation, visual glyph shape or economic meaning.','PDF page geometry is represented by the builder layout receipt; visual styling is separately reviewed.']};atomic(cached,out);print(date,'PDF',len(pdf.pages),'pages',len(cited),'sources',len(expected),'full paragraphs','PASS' if out['passed'] else 'FAIL',flush=True);return out

def safe_name(name):
 p=PurePosixPath(name)
 return not p.is_absolute() and '..' not in p.parts and str(p)==name and not name.endswith('/') and '\\' not in name and '\x00' not in name and not re.match(r'^[A-Za-z]:',name)
def check_final(manifest,pdf_rows):
 errors=[];checks=0
 def ck(ok,message,detail=None):
  nonlocal checks
  checks+=1
  if not ok:errors.append({'error':message,**({'detail':detail} if detail is not None else {})})
 mp=ROOT/'checks/artifact_manifest.json';manifest_hash=sha(mp);ck(manifest['dates']==DATES and manifest['complete_month'] is True,'exact complete22 manifest');ck([r['date'] for r in manifest['reports']]==DATES,'22 unique ordered report rows');ck(all(r['passed'] for r in pdf_rows) and [r['date'] for r in pdf_rows]==DATES,'all22 independent PDF receipts pass');ck(manifest['artifact_targets']==71 and manifest['report_zip_members']==69,'71 targets69 report ZIP members')
 native={p for d in DATES for p in (f'html/{d}.html',f'json/{d}_Market_Intelligence.json',f'pdf/{d}_Market_Intelligence.pdf')};actual={f['path'] for row in manifest['reports'] for f in row['files'].values()};ck(len(native)==66 and actual==native,'exact66 native file paths');collections={'2024-08.html','methodology.txt','August_2024_Weekday_Reports.zip','August_2024_Frozen_Sources.zip','What_Retail_Is_Playing_2024-08.html'};ck(set(manifest['collection'])==collections,'exact five collection artifacts')
 source_accept=read(ROOT/'audit/independent_source_review.json');market_accept=read(ROOT/'audit/independent_market_review.json');freeze=read(ROOT/'audit/source_freeze.json');accepted={r['date']:r['feed_sha256'] for r in source_accept['dates']}
 ck(source_accept['source_freeze_sha256']==market_accept['source_freeze_sha256']==sha(ROOT/'audit/source_freeze.json'),'acceptances bind current freeze')
 for row,ind in zip(manifest['reports'],pdf_rows):
  d=row['date'];ck(read(ROOT/'checks/artifacts'/f'{d}.json')==row,'manifest equals layout receipt '+d)
  ck(row['feed_sha256']==accepted[d]==freeze['current_feed_sha256'][d]==ind['input_bindings']['feed']['sha256'],'final feed binding '+d);ck(row['card_sha256']==source_accept['card_sha256'][d]==market_accept['card_sha256'][d]==ind['input_bindings']['card']['sha256'],'final card binding '+d);ck(row['spec_sha256']==ind['input_bindings']['spec']['sha256'],'final spec binding '+d)
 for name,item in manifest['collection'].items():
  p=ROOT/item['path'];ck(safe_name(item['path']) and p.resolve().is_relative_to(ROOT) and not p.is_symlink() and p.is_file(),'collection path safe '+name);ck(sha(p)==item['sha256'] and p.stat().st_size==item['bytes'],'collection hash/size '+name)
 bundle=ROOT/manifest['collection']['August_2024_Weekday_Reports.zip']['path'];expected=native|{'index.html','methodology.txt','What_Retail_Is_Playing_2024-08.html'};zip_members=[]
 with zipfile.ZipFile(bundle) as z:
  names=z.namelist();ck(len(names)==69 and len(names)==len(set(names)) and set(names)==expected and all(safe_name(n) for n in names),'exact safe unique69 report ZIP names');ck(z.testzip() is None,'report ZIP CRC')
  for row in manifest['reports']:
   for ext,item in row['files'].items():
    body=z.read(item['path']);ok=hashlib.sha256(body).hexdigest()==item['sha256'] and len(body)==item['bytes'];ck(ok,'report ZIP full member hash '+item['path']);zip_members.append({'path':item['path'],'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()})
  for name in ['methodology.txt','What_Retail_Is_Playing_2024-08.html']:ck(z.read(name)==(ROOT/manifest['collection'][name]['path']).read_bytes(),'report ZIP collection copy '+name)
  offline=BeautifulSoup(z.read('index.html'),'html.parser');offline_dates=[a['href'][5:-5] for a in offline.select('a.day[href]') if a['href'].startswith('html/')];ck(offline_dates==DATES,'offline index exact22 daily HTML links')
 index=BeautifulSoup((ROOT/manifest['collection']['2024-08.html']['path']).read_text(),'html.parser');links=[a['href'][8:-5] for a in index.select('a.day[href]') if a['href'].startswith('archive/')];ck(links==DATES,'collection exact22 daily HTML links')
 retail=BeautifulSoup((ROOT/manifest['collection']['What_Retail_Is_Playing_2024-08.html']['path']).read_text(),'html.parser');sections=retail.select('section.day[id]');ck([s['id'] for s in sections]==DATES,'retail exact22 dates in order');ck('1–30 August 2024' in retail.get_text(' ',strip=True),'retail date-range label startsAug1')
 for section in sections:
  d=section['id'];spec=read(ROOT/'specs'/f'{d}.json')
  expected_ids=set(re.findall(r'\[\[(n\d+)\]\]',json.dumps({'retail':spec['retail'],'retail_intro':spec['retail_intro']},ensure_ascii=False)))
  chips=section.select('sup.cite');ledger_ids={node.get_text(strip=True) for node in section.select('.sources li strong')}
  ck({node.get_text(strip=True) for node in chips}==ledger_ids==expected_ids,'retail collection exact citation chips/ledger IDs '+d)
  # These are UI source chips, not prose. Remove their DOM nodes before the same full-word comparison.
  for node in chips:node.decompose()
  for node in section.select('.sources'):node.decompose()
  norm=normalize(section.get_text(' ',strip=True),True)
  for n,item in enumerate(spec['retail']):
   for k,body in item['parts']:ck(normalize(body,True) in norm,'retail collection full paragraph '+d+' '+str(n)+' '+k)
  ck(normalize(spec['retail_intro'],True) in norm,'retail collection intro '+d)
 source_zip=ROOT/manifest['collection']['August_2024_Frozen_Sources.zip']['path'];inventory_count=0;source_members=0
 with zipfile.ZipFile(source_zip) as z:
  names=z.namelist();source_members=len(names);rows=json.loads(z.read('source_inventory.json'));inventory_count=len(rows);ck(len(names)==len(set(names)) and all(safe_name(n) for n in names),'source ZIP safe unique names');ck(len(rows)==len({r['path'] for r in rows}) and set(names)=={r['path'] for r in rows}|{'source_inventory.json'},'source ZIP exact inventory membership');ck(z.testzip() is None,'source ZIP CRC')
  for item in rows:
   body=z.read(item['path']);ck(hashlib.sha256(body).hexdigest()==item['sha256'] and len(body)==item['bytes'],'source ZIP inventory body '+item['path'])
  included={r['path']:r for r in rows};critical={f'{folder}/{d}{suffix}' for d in DATES for folder,suffix in [('specs','.json'),('cards','.json'),('feeds','.json.gz'),('retail_drafts','.json')]};critical|={str(p.relative_to(ROOT)) for p in (ROOT/'tools').glob('*.py')};critical|={str(p.relative_to(ROOT)) for p in (ROOT/'audit_work').glob('*.py')};critical|={'audit/independent_source_review.json','audit/independent_market_review.json','audit/source_freeze.json','audit/source_amendments/amendment.json','audit/independent_source_amendment_review.json','audit/news_replay_inventory.json','checks/independent_artifact_delivery_tool_review.json'}
  for path in sorted(critical):ck(path in included and included[path]['sha256']==sha(ROOT/path),'source ZIP current critical input '+path)
  expected_inv=manifest['frozen_source_archive'];ck(expected_inv['files']==len(rows) and expected_inv['inventory_sha256']==hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest(),'source inventory manifest binding')
 ck(sha(mp)==manifest_hash,'manifest stable during review');tool_hashes={p.name:sha(p) for p in (ROOT/'tools').glob('*.py')}
 result={'status':'complete_local_artifacts_checked' if not errors else 'local_artifact_errors','passed':not errors,'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'checks':checks,'errors':errors,'scope':'All22 completed local HTML/JSON/PDF editions,69-member report ZIP, source ZIP inventory,22-date report/retail collections, accepted inputs and saved layout receipts. No prose-meaning, live origin/public delivery or publication approval.','manifest_sha256':manifest_hash,'dates':DATES,'native_files':66,'report_zip_members':69,'source_zip_members':source_members,'source_zip_inventory_files':inventory_count,'pdf_pages':sum(r['pdf_pages'] for r in pdf_rows),'dated_source_entries':sum(r['source_count'] for r in pdf_rows),'full_paragraphs_checked':sum(r['full_paragraphs_checked'] for r in pdf_rows),'reports':[{'date':r['date'],'receipt_path':'checks/independent_pdf/'+r['date']+'.json','receipt_sha256':sha(ROOT/'checks/independent_pdf'/f'{r["date"]}.json'),'pages':r['pdf_pages'],'sources':r['source_count'],'paragraphs':r['full_paragraphs_checked'],'input_bindings':r['input_bindings']} for r in pdf_rows],'report_zip_member_hashes':zip_members,'tool_sha256':tool_hashes,'reviewer_tool_sha256':sha(Path(__file__)),'limits':['Unicode word/numeral completeness does not certify identical punctuation, visual glyphs, financial semantics or factual claims.','Desktop/mobile geometry checks are existing hash-bound browser receipts; no independent browser rerender was performed.','The independent final review receipt is created after packaging and is intentionally external to the self-contained source ZIP to avoid self-referential hashes.','No S3, public HTTPS, Lambda, invalidation or external send executed.']};atomic(ROOT/'checks/independent_full_artifact_review.json',result);print(json.dumps({'passed':result['passed'],'checks':checks,'errors':errors,'pdf_pages':result['pdf_pages'],'dated_source_entries':result['dated_source_entries'],'paragraphs':result['full_paragraphs_checked']},indent=2));return result

def main():
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--available',action='store_true');g.add_argument('--final',action='store_true');p.add_argument('--workers',type=int,default=4);args=p.parse_args()
 dates=[d for d in DATES if (ROOT/'checks/artifacts'/f'{d}.json').is_file()]
 manifest=read(ROOT/'checks/artifact_manifest.json') if args.final else None
 if args.final and (manifest.get('dates')!=DATES or manifest.get('complete_month') is not True):raise SystemExit('Final review refuses a partial manifest')
 with cf.ProcessPoolExecutor(max_workers=args.workers) as pool:rows=list(pool.map(check_pdf,dates))
 bad=[{'date':r['date'],'errors':r['errors']} for r in rows if not r['passed']]
 if args.available:
  print(json.dumps({'scope':'partial per-PDF only','dates_checked':len(rows),'pdf_pages':sum(r['pdf_pages'] for r in rows),'sources':sum(r['source_count'] for r in rows),'paragraphs':sum(r['full_paragraphs_checked'] for r in rows),'errors':bad},indent=2));return
 result=check_final(manifest,rows)
 if not result['passed'] or bad:raise SystemExit(1)
if __name__=='__main__':main()
