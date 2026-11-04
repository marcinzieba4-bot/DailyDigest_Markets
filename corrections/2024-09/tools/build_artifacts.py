"""Build validated September2024 HTML/JSON/PDF editions and collection locally.

Run with default Python (Playwright, Chromium and pypdf installed); report-tools Python is used for publication. No AWS calls
or model calls. Publication and independent editorial signoff are separate.
"""
from pathlib import Path
import datetime as dt
import hashlib
import html
import importlib.util
import json
import sys
import zipfile
from pathlib import PurePosixPath
from playwright.sync_api import sync_playwright
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parent.parent
DATES=[dt.date(2024,9,n).isoformat() for n in range(1,31) if dt.date(2024,9,n).weekday()<5]
ZIP_NAME='September_2024_Weekday_Reports.zip'
SOURCE_NAME='September_2024_Frozen_Sources.zip'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def module(name):
    spec=importlib.util.spec_from_file_location('sep_'+name,ROOT/'tools'/f'{name}.py')
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj
def load(path):return json.loads(path.read_text())
def atomic(path,data):
    temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(data,indent=2)+'\n');temp.replace(path)
def file_row(path):return {'path':str(path.relative_to(ROOT)),'sha256':sha(path),'bytes':path.stat().st_size}

def collection(dates,offline=False):
    cards=[]
    for date in dates:
        spec=load(ROOT/'specs'/f'{date}.json');us=spec['geo'][0]
        label=dt.date.fromisoformat(date).strftime('%a %d %B')
        dest=('html/' if offline else 'archive/')+date+'.html'
        cards.append('<a class="day" href="'+dest+'"><span class="date">'+label+'</span><span class="stance">US: '+html.escape(us['stance'])+'</span><h2>'+html.escape(spec['retail'][0]['title'])+'</h2><span>Read the briefing &rarr;</span></a>')
    root='' if offline else '2024-09/'
    reports_href=('https://zembihf.xyz/reports/2024-09/' if offline else root)+ZIP_NAME
    sources_href=('https://zembihf.xyz/reports/2024-09/' if offline else root)+SOURCE_NAME
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>September 2024 · Market Intelligence Archive</title><style>
*{box-sizing:border-box}body{font-family:Arial,sans-serif;background:#f4f6fc;color:#243047;margin:auto;max-width:1400px;padding:60px 48px;line-height:1.6}h1{font-size:clamp(42px,6vw,76px);letter-spacing:-3px;line-height:1.05;margin:20px 0}h2{font-size:19px;line-height:1.45}p{max-width:850px;color:#64718b}.kicker{font-size:13px;text-transform:uppercase;letter-spacing:.12em;color:#285daf;font-weight:bold}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px;margin-top:40px}.day{color:inherit;text-decoration:none;border:1px solid #dce4f1;border-top:4px solid #1a73e8;border-radius:10px;padding:24px;background:white;display:flex;flex-direction:column;align-items:flex-start;min-height:230px;box-shadow:0 7px 30px #1c315408}.day:hover{border-color:#3972bf;transform:translateY(-2px)}.date{font-weight:bold}.stance{font-size:12px;color:#526a90;background:#edf2fc;border-radius:4px;padding:3px 7px;margin-top:12px}.day>span:last-child{font-size:12px;color:#185eb8;margin-top:auto}.button{display:inline-block;background:#1e58a7;color:white;text-decoration:none;padding:11px 18px;border-radius:6px;margin:12px 10px 12px 0}.button.retail{background:#d45627}.note{margin-top:45px;padding:25px;background:#eaf0fa;border-radius:10px;font-size:13px}.note p{max-width:1100px}footer{margin-top:30px;font-size:12px;color:#7a879e}@media(max-width:900px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){body{padding:30px 20px}.grid{grid-template-columns:1fr}h1{letter-spacing:-1.5px}}
</style></head><body><div class="kicker">DailyDigest Markets · Historical editions</div><h1>September 2024.<br>The information, day by day.</h1><p>'''+str(len(dates))+''' weekday Market Intelligence Briefings in the wide August-style layout: six macro regions, thirteen sectors, earnings, thematic opportunities, crypto, liquidity, scenarios, stock catalysts and retail narratives.</p><a class="button" href="'''+reports_href+'''">Download all reports · HTML, PDF & JSON</a><a class="button" href="'''+sources_href+'''">Download dated sources &amp; audit</a><a class="button retail" href="'''+root+'''What_Retail_Is_Playing_2024-09.html">What Retail Is Playing · the full month</a><a class="button" href="'''+root+'''methodology.txt">Sources & historical method</a><div class="grid">'''+''.join(cards)+'''</div><div class="note"><strong>The historical boundary</strong><p>Each edition uses its own dated information before 00:00 UTC and completed prior market sessions. News-index timestamps are screened for release-date conflicts; original publisher vintages are not independently archived. Current-vintage market histories may contain later vendor revisions. Historical share units are mechanically restored using split events. Later outcomes are excluded from the analysis.</p></div><footer>Report dates: 2–30 September 2024. All Monday–Friday dates receive editions, including exchange holidays. No weekend editions. Price changes exclude dividends.</footer></body></html>'''

def methodology(dates):
    return f'''September 2024 Market Intelligence Briefings
{len(dates)} weekday editions, {dates[0]} through {dates[-1]}.

Historical boundary
Every edition uses its own information cutoff at 00:00 UTC on the report date.
News and previews use a seven-day lookback, company results fourteen days,
and monthly economic releases / policy baselines thirty-five days. The sources
are dated Google News RSS headline records, not full article bodies or an
independently archived contemporaneous publication corpus. Obvious early-release
outcomes and rolling live pages are excluded. Source receipts and editorial
reviews record the actual checks and their limits.

Market data
Yahoo Finance daily chart histories supply completed exchange-local sessions;
crypto uses the completed preceding UTC daily candle. Returns are price changes,
excluding dividends, over one, five and twenty observations. Historical quoted
share units are mechanically reconstructed using split metadata; later price
observations are not retained. Numeric spot-FX marks and returns are excluded
because the provider's dated daily Close may represent an opening reference
quote rather than a verified completed close. Currency discussion uses eligible
dated reporting. DXY remains a separate dollar index. Comcast and Western Digital levels are suppressed because their
spin-off distributions are not ordinary share splits. Nebius was halted throughout
September and has no trading metrics in this set; later listings have none either.
MSTR lookbacks crossing its August split retain an explicit older-share-unit warning;
only comparable percentage returns are used across that boundary. Current-vintage vendor
histories can include later corrections. The official US Treasury daily par
curve supplies yield levels, changes and spreads in basis points. Equity and
bond-market holidays differ. September 2 is a US equity and Treasury holiday.
Actual exchange-local sessions govern all regional observations, including the
September Asian-market holidays and exceptional closures.

Layout and files
Each report has nine sections, six macro regions, thirteen sectors, four themes,
four event scenarios, six company catalysts and four retail narratives. The
retail lead has six parts; each of three smaller trades has motivation and
invalidation. Conditional market interpretation is distinguished from observed
crowd activity. Price moves alone do not establish retail-flow rankings.
HTML and JSON retain the dated citation ledger. Browser PDFs include the full
report and source ledger. The retail collection reproduces the saved per-date
sections. The frozen-source archive contains the exact dated inputs, author
specifications, tool source and audit receipts used for this set.

Prepared retrospectively in November 2026. These are historical research editions,
not an assertion of original unrevised article or market-data vintages.
'''

def source_archive(dates):
    # Preserve the exact shared editorial gate executed by the final pipeline.
    gate = ROOT.parent/'retail-quality/retail_quality.py'
    snapshot = ROOT/'tools/retail_quality_snapshot.py'
    snapshot.write_bytes(gate.read_bytes())
    if snapshot.read_bytes() != gate.read_bytes() or sha(snapshot) != sha(gate):
        raise ValueError('Shared retail gate snapshot mismatch')
    paths=set()
    for date in dates:
        for folder,pattern in [('specs',date+'.json'),('cards',date+'.json'),('feeds',date+'.json.gz'),('notes',date+'.json')]:
            p=ROOT/folder/pattern
            if p.is_file():paths.add(p)
        if not (ROOT/'feeds'/f'{date}.json.gz').is_file():raise ValueError('Missing frozen feed '+date)
    for folder,pattern in [('tools','*.py'),('data','*.json'),('audit','*.json'),('audit','*.json.gz'),('checks','*review*.json'),('checks','*quality*.json')]:
        paths.update((ROOT/folder).glob(pattern))
    # Keep all selection-note naming conventions and the independently authored retail component.
    paths.update((ROOT/'notes').glob('*.json'))
    paths.update((ROOT/'retail_drafts').glob('*.json'))
    # Include nested per-date editorial and artifact receipts; exclude self-referential collection manifests.
    excluded_receipts = {'source_archive_build.json', 'artifact_manifest.json', 'delivery_verification.json'}
    paths.update(p for p in (ROOT/'checks').rglob('*.json') if p.name not in excluded_receipts)
    for p in [ROOT/'BRIEF.md',ROOT/'AUTHORING.md',ROOT/'README.md']:
        if p.is_file():paths.add(p)
    paths.update((ROOT/'reference').glob('*.txt'))
    # The acquisition agent's replay inventory may contain additional cached
    # query responses. Include only its exact hash-bound safe relative paths.
    replay=ROOT/'audit/news_replay_inventory.json'
    if not replay.is_file():raise ValueError('Explicit hash-bound news replay inventory required')
    replay_rows=load(replay).get('files',[])
    if not replay_rows or len({row['path'] for row in replay_rows})!=len(replay_rows):
        raise ValueError('Empty or duplicate source replay inventory')
    for row in replay_rows:
        relative=PurePosixPath(row['path'])
        p=(ROOT/relative).resolve()
        if relative.is_absolute() or '..' in relative.parts or str(relative)!=row['path'] or not p.is_relative_to(ROOT) or not p.is_file():
            raise ValueError('Invalid source inventory path')
        if not isinstance(row.get('sha256'),str) or len(row['sha256'])!=64 or sha(p)!=row['sha256']:
            raise ValueError('Source inventory hash mismatch: '+row['path'])
        if row.get('bytes')!=p.stat().st_size:raise ValueError('Source inventory size mismatch: '+row['path'])
        paths.add(p)
    paths.add(replay)
    inventory=[file_row(p) for p in sorted(paths) if p.is_file()]
    out=ROOT/'collection'/SOURCE_NAME
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for row in inventory:z.write(ROOT/row['path'],row['path'])
        z.writestr('source_inventory.json',json.dumps(inventory,indent=2))
    result={'status':'complete','archive':file_row(out),'files':len(inventory),'inventory_sha256':hashlib.sha256(json.dumps(inventory,sort_keys=True).encode()).hexdigest()}
    atomic(ROOT/'checks/source_archive_build.json',result)
    return result

def main():
    dates=sys.argv[1:] or DATES
    if dates!=sorted(set(dates)) or any(d not in DATES for d in dates):raise ValueError('Expected sorted unique September2024 weekdays')
    audit=load(ROOT/'audit/market_validation.json')
    if audit.get('passed') is not True:raise ValueError('Passing market audit required')
    for date in dates:
        if audit['card_sha256'].get(date)!=sha(ROOT/'cards'/f'{date}.json'):raise ValueError('Changed audited card '+date)
    for folder in ['pdf','collection','checks/artifacts']:(ROOT/folder).mkdir(parents=True,exist_ok=True)
    verify=module('verify');render=module('render')
    manifest={'dates':dates,'complete_month':dates==DATES,'reports':[]}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
        for date in dates:
            fails,warns,source_count,words=verify.verify(date)
            if fails:raise ValueError(date+' validation failed: '+repr(fails))
            fp=ROOT/'feeds'/f'{date}.json.gz'
            inputs={'spec_sha256':sha(ROOT/'specs'/f'{date}.json'),'feed_sha256':sha(fp),'card_sha256':sha(ROOT/'cards'/f'{date}.json'),'renderer_sha256':sha(ROOT/'tools/render.py'),'builder_sha256':sha(Path(__file__))}
            receipt=ROOT/'checks/artifacts'/f'{date}.json'
            if receipt.is_file():
                old=load(receipt)
                if all(old.get(k)==v for k,v in inputs.items()) and all((ROOT/x['path']).is_file() and sha(ROOT/x['path'])==x['sha256'] for x in old.get('files',{}).values()):
                    old.update(warnings=warns,words=words,distinct_sources=source_count);manifest['reports'].append(old);print(date,'reused unchanged checked artifacts',flush=True);continue
            render.render(date)
            hp=ROOT/'html'/f'{date}.html';jp=ROOT/'json'/f'{date}_Market_Intelligence.json';pp=ROOT/'pdf'/f'{date}_Market_Intelligence.pdf'
            page.set_content(hp.read_text(),wait_until='load')
            layout=page.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth,headings:document.querySelectorAll("h2[id]").length,citations:document.querySelectorAll(".source-cite").length})')
            if layout['scroll']>layout['width'] or layout['headings']!=9:raise ValueError(date+' desktop layout failure')
            if page.locator('.snapshot,.metric,.momentum').count():raise ValueError(date+' removed dashboard remains')
            if date==dates[0]:
                page.screenshot(path=str(ROOT/'checks/desktop-preview.png'))
                page.locator('#retail').scroll_into_view_if_needed();page.screenshot(path=str(ROOT/'checks/retail-preview.png'))
                page.evaluate('window.scrollTo(0,0)')
            page.evaluate("document.querySelectorAll('details').forEach(x=>x.open=true)")
            page.pdf(path=str(pp),format='A4',print_background=True,margin={'top':'14mm','bottom':'16mm','left':'14mm','right':'14mm'},display_header_footer=True,header_template='<span></span>',footer_template='<div style="font-family:Arial;font-size:8px;width:100%;text-align:center;color:#8993a2">'+date+' · Market Intelligence Briefing · <span class="pageNumber"></span> / <span class="totalPages"></span></div>')
            pdf=PdfReader(pp);text=' '.join(x.extract_text() or '' for x in pdf.pages)
            for marker in ['Geographic Macro Overview','Sector Deep Dive','What Retail Is Playing','Dated evidence']:
                if marker not in text:raise ValueError(date+' PDF missing '+marker)
            page.set_viewport_size({'width':390,'height':844});page.set_content(hp.read_text(),wait_until='load')
            overflow=page.evaluate('document.documentElement.scrollWidth>innerWidth')
            if overflow:raise ValueError(date+' mobile overflow')
            if date==dates[0]:page.screenshot(path=str(ROOT/'checks/mobile-preview.png'))
            page.set_viewport_size({'width':1440,'height':1000})
            row={'date':date,**inputs,'words':words,'distinct_sources':source_count,'warnings':warns,'pdf_pages':len(pdf.pages),'layout':layout,'mobile_overflow':False,'files':{k:file_row(path) for k,path in [('html',hp),('json',jp),('pdf',pp)]}}
            atomic(receipt,row);manifest['reports'].append(row);print(date,words,'words',source_count,'sources',len(pdf.pages),'PDF pages',flush=True)
        browser.close()
    module('build_retail_page').build()
    retail=ROOT/'retail/What_Retail_Is_Playing_2024-09.html'
    (ROOT/'collection'/retail.name).write_bytes(retail.read_bytes())
    (ROOT/'collection/methodology.txt').write_text(methodology(dates))
    (ROOT/'collection/2024-09.html').write_text(collection(dates))
    frozen=source_archive(dates);manifest['frozen_source_archive']=frozen
    zp=ROOT/'collection'/ZIP_NAME
    with zipfile.ZipFile(zp,'w',zipfile.ZIP_DEFLATED) as z:
        for row in manifest['reports']:
            for f in row['files'].values():z.write(ROOT/f['path'],f['path'])
        z.write(ROOT/'collection/methodology.txt','methodology.txt');z.write(retail,retail.name)
        z.writestr('index.html',collection(dates,offline=True))
        expected_members=len(dates)*3+3
        if len(z.namelist())!=expected_members or len(set(z.namelist()))!=expected_members:
            raise ValueError('Unexpected report ZIP membership')
        manifest['report_zip_members']=expected_members
    names=['2024-09.html','methodology.txt',ZIP_NAME,SOURCE_NAME,retail.name]
    manifest['collection']={n:file_row(ROOT/'collection'/n) for n in names}
    manifest['artifact_targets']=len(manifest['reports'])*3+len(names)
    if manifest['complete_month'] and (manifest['artifact_targets']!=68 or manifest['report_zip_members']!=66):
        raise ValueError('September full-month artifact count mismatch')
    atomic(ROOT/'checks/artifact_manifest.json',manifest)
    print('Artifacts complete; complete month:',manifest['complete_month'],flush=True)

if __name__=='__main__':main()
