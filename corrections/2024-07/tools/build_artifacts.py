"""Build validated July2024 HTML/JSON/PDF editions and collection locally.

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
import re
import unicodedata
import zipfile
from pathlib import PurePosixPath
from playwright.sync_api import sync_playwright
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parent.parent
DATES=[dt.date(2024,7,n).isoformat() for n in range(1,32) if dt.date(2024,7,n).weekday()<5]
ZIP_NAME='July_2024_Weekday_Reports.zip'
SOURCE_NAME='July_2024_Frozen_Sources.zip'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def module(name):
    spec=importlib.util.spec_from_file_location('july_'+name,ROOT/'tools'/f'{name}.py')
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj
def load(path):return json.loads(path.read_text())
def atomic(path,data):
    temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(data,indent=2)+'\n');temp.replace(path)
def file_row(path):return {'path':str(path.relative_to(ROOT)),'sha256':sha(path),'bytes':path.stat().st_size}

def prose_key(text):
    """Collapse layout whitespace; preserve word boundaries and every literal."""
    return ' '.join(unicodedata.normalize('NFC',text).split())

def report_paragraphs(spec):
    for name in ['geo','sectors','earnings_pattern','underowned','crypto','flows','anticipatory','catalysts']:
        blocks=spec[name] if isinstance(spec[name],list) else [spec[name]]
        for i,block in enumerate(blocks):
            for label,text in block['parts']:yield f'{name}.{i}.{label}',label,text
    yield 'retail_intro',None,spec['retail_intro']
    for i,block in enumerate(spec['retail']):
        for label,text in block['parts']:yield f'retail.{i}.{label}',label,text

def citation_order(spec):
    order={}
    for _,_,text in report_paragraphs(spec):
        for key in re.findall(r'\[\[(n\d{4,6})\]\]',text):order.setdefault(key,len(order)+1)
    return order

def rendered_prose(text,order):
    return re.sub(r'\[\[(n\d{4,6})\]\]',lambda m:f' [{order[m[1]]}] ',text)

def ordered_matches(haystack,expected,description):
    cursor=0
    for label,text in expected:
        needle=prose_key(text)
        start=haystack.find(needle,cursor)
        if not needle or start<0:raise ValueError(description+' lost/reordered occurrence '+label)
        cursor=start+len(needle)
    return cursor

def check_pdf_prose(date,pdf,spec,evidence):
    footer=re.compile(r'(?m)^'+re.escape(date)+r'\s*·\s*Market Intelligence Briefing\s*·\s*\d+\s*/\s*\d+\s*$')
    text=' '.join(footer.sub('',page.extract_text() or '') for page in pdf.pages)
    if '\ufffd' in text or '\x00' in text:raise ValueError(date+' PDF contains replacement characters')
    key=prose_key(text);order=citation_order(spec)
    if list(evidence)!=list(order):raise ValueError(date+' Wrong evidence order/membership')
    boundary=prose_key(f'Dated evidence · {len(order)} sources')
    if key.count(boundary)!=1:raise ValueError(date+' PDF ledger boundary missing/ambiguous')
    body,ledger=key.split(boundary)
    expected=[]
    for location,label,paragraph in report_paragraphs(spec):
        expected.append((location,('' if label is None else label+': ')+rendered_prose(paragraph,order)))
    ordered_matches(body,expected,date+' PDF body')
    entries=[(source_id,item['title']+' — '+item['src']+' · '+item['published_at']) for source_id,item in evidence.items()]
    ordered_matches(ledger,entries,date+' PDF source ledger')
    return {'paragraphs_preserved':len(expected),'ledger_headlines_preserved':len(entries),
            'ordered_occurrences_preserved':True,'unicode_prose_preserved':True}

def accepted_components(dates):
    """Build only current independently accepted July inputs and components."""
    source=load(ROOT/'audit/independent_source_review.json')
    market=load(ROOT/'audit/independent_market_review.json')
    if (source.get('passed') is not True or market.get('passed') is not True
            or source.get('errors') or market.get('errors')):
        raise ValueError('Independent source and market acceptance required before building')
    rows={row['date']:row for row in source.get('dates',[])}
    for date in dates:
        feed_hash=sha(ROOT/'feeds'/f'{date}.json.gz');card_hash=sha(ROOT/'cards'/f'{date}.json')
        if (rows.get(date,{}).get('feed_sha256')!=feed_hash
                or any(review.get('card_sha256',{}).get(date)!=card_hash for review in (source,market))):
            raise ValueError('Independent input acceptance stale: '+date)
        spec=load(ROOT/'specs'/f'{date}.json')
        component={k:v for k,v in spec.items() if k not in {'retail','retail_intro'}}
        content_hash=hashlib.sha256(json.dumps(component,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        for kind in ('nonretail','retail'):
            review=load(ROOT/'audit'/f'independent_{kind}_{date}.json')
            if (type(review.get('fatal_or_major_remaining')) is not int or review['fatal_or_major_remaining']!=0
                    or review.get('date')!=date or review.get('feed_sha256')!=feed_hash or review.get('card_sha256')!=card_hash):
                raise ValueError('Independent component acceptance stale: '+date+' '+kind)
            if kind=='nonretail' and review.get('nonretail_content_sha256')!=content_hash:
                raise ValueError('Nonretail changed after review: '+date)
            if kind=='retail':
                draft_path=ROOT/'retail_drafts'/f'{date}.json';draft=load(draft_path)
                if (review.get('retail_draft_sha256',review.get('draft_sha256'))!=sha(draft_path)
                        or draft.get('date')!=date or any(draft.get(k)!=spec.get(k) for k in ('retail','retail_intro'))):
                    raise ValueError('Retail changed after review: '+date)

def require_retail_gates():
    module('retail_quality_snapshot').require_review(ROOT)
    original=ROOT/'audit_work/shared_retail_quality_original.py'
    gate=ROOT.parent/'retail-quality/retail_quality.py'
    if not original.is_file() or original.read_bytes()!=gate.read_bytes():
        raise ValueError('Original shared retail gate provenance changed')
    info=importlib.util.spec_from_file_location('july_original_retail_gate',original)
    shared=importlib.util.module_from_spec(info);info.loader.exec_module(shared)
    shared.require_review(ROOT)

def collection(dates,offline=False):
    if dates!=DATES:raise ValueError('Collection generation requires all 23 July weekdays')
    cards=[]
    for date in dates:
        spec=load(ROOT/'specs'/f'{date}.json');us=spec['geo'][0]
        label=dt.date.fromisoformat(date).strftime('%a %d %B')
        dest=('html/' if offline else 'archive/')+date+'.html'
        cards.append('<a class="day" href="'+dest+'"><span class="date">'+label+'</span><span class="stance">US: '+html.escape(us['stance'])+'</span><h2>'+html.escape(spec['retail'][0]['title'])+'</h2><span>Read the briefing &rarr;</span></a>')
    root='' if offline else '2024-07/'
    reports_href=('https://zembihf.xyz/reports/2024-07/' if offline else root)+ZIP_NAME
    sources_href=('https://zembihf.xyz/reports/2024-07/' if offline else root)+SOURCE_NAME
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>July 2024 · Market Intelligence Archive</title><style>
*{box-sizing:border-box}body{font-family:Arial,sans-serif;background:#f4f6fc;color:#243047;margin:auto;max-width:1400px;padding:60px 48px;line-height:1.6}h1{font-size:clamp(42px,6vw,76px);letter-spacing:-3px;line-height:1.05;margin:20px 0}h2{font-size:19px;line-height:1.45}p{max-width:850px;color:#64718b}.kicker{font-size:13px;text-transform:uppercase;letter-spacing:.12em;color:#285daf;font-weight:bold}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px;margin-top:40px}.day{color:inherit;text-decoration:none;border:1px solid #dce4f1;border-top:4px solid #1a73e8;border-radius:10px;padding:24px;background:white;display:flex;flex-direction:column;align-items:flex-start;min-height:230px;box-shadow:0 7px 30px #1c315408}.day:hover{border-color:#3972bf;transform:translateY(-2px)}.date{font-weight:bold}.stance{font-size:12px;color:#526a90;background:#edf2fc;border-radius:4px;padding:3px 7px;margin-top:12px}.day>span:last-child{font-size:12px;color:#185eb8;margin-top:auto}.button{display:inline-block;background:#1e58a7;color:white;text-decoration:none;padding:11px 18px;border-radius:6px;margin:12px 10px 12px 0}.button.retail{background:#d45627}.note{margin-top:45px;padding:25px;background:#eaf0fa;border-radius:10px;font-size:13px}.note p{max-width:1100px}footer{margin-top:30px;font-size:12px;color:#7a879e}@media(max-width:900px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){body{padding:30px 20px}.grid{grid-template-columns:1fr}h1{letter-spacing:-1.5px}}
</style></head><body><div class="kicker">DailyDigest Markets · Historical editions</div><h1>July 2024.<br>The information, day by day.</h1><p>'''+str(len(dates))+''' weekday Market Intelligence Briefings in the wide August 2026 style: six macro regions, thirteen sectors, earnings, thematic opportunities, crypto, liquidity, scenarios, stock catalysts and retail narratives.</p><a class="button" href="'''+reports_href+'''">Download all reports · HTML, PDF & JSON</a><a class="button" href="'''+sources_href+'''">Download dated sources &amp; audit</a><a class="button retail" href="'''+root+'''What_Retail_Is_Playing_2024-07.html">What Retail Is Playing · the full month</a><a class="button" href="'''+root+'''methodology.txt">Sources & historical method</a><div class="grid">'''+''.join(cards)+'''</div><div class="note"><strong>The historical boundary</strong><p>Each edition uses its own dated information before 00:00 UTC and completed prior market sessions. News-index timestamps are screened for release-date conflicts; original publisher vintages are not independently archived. Current-vintage market histories may contain later vendor revisions. Historical share units are mechanically restored using split events. Later outcomes are excluded from the analysis.</p></div><footer>Report dates: 1–31 July 2024. All Monday–Friday dates receive editions, including exchange holidays. No weekend editions. Price changes exclude dividends.</footer></body></html>'''

def methodology(dates):
    return f'''July 2024 Market Intelligence Briefings
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
dated reporting. DXY remains a separate dollar index. Corporate-action restrictions,
missing-history limitations and each instrument's actual session are recorded in
the dated market cards and market audit. Missing observations are not estimated.
Current-vintage vendor histories can include later corrections. The official
US Treasury daily par curve supplies yield levels, changes and spreads in basis
points. Equity and bond-market holidays differ; no holiday session is invented.

Layout and files
Each report has nine sections, six macro regions, thirteen sectors, four themes,
four event scenarios, six company catalysts and four retail narratives. The
retail lead has six parts; each of three smaller trades has motivation and
invalidation. Conditional market interpretation is distinguished from observed
crowd activity. Price moves alone do not establish retail-flow rankings.
HTML and JSON retain the dated citation ledger. Native PDF and JSON files are
delivered within the report ZIP. Browser PDFs include the full
report and source ledger. The retail collection reproduces the saved per-date
sections. The frozen-source archive contains the exact dated inputs, author
specifications, tool source and audit receipts used for this set.

Prepared retrospectively in November 2026. These are historical research editions,
not an assertion of original unrevised article or market-data vintages.
'''

def source_archive(dates):
    # Preserve the exact shared gate actually executed by the final pipeline.
    gate=ROOT.parent/'retail-quality/retail_quality.py'
    snapshot=ROOT/'audit_work/shared_retail_quality_original.py'
    if not snapshot.is_file() or snapshot.read_bytes()!=gate.read_bytes():
        raise ValueError('Original shared retail gate provenance missing or changed')
    paths={snapshot}
    for date in dates:
        for folder,suffix in [('specs','.json'),('cards','.json'),('feeds','.json.gz'),('nonretail_drafts','.json'),('retail_drafts','.json')]:
            path=ROOT/folder/(date+suffix)
            if not path.is_file():raise ValueError('Missing frozen source component '+str(path))
            paths.add(path)
    for folder,pattern in [('tools','*.py'),('data','*.json'),('audit','*.json'),('audit','*.jsonl'),('audit','*.json.gz')]:
        paths.update((ROOT/folder).glob(pattern))
    paths.update((ROOT/'notes').glob('*.json'))
    # Final delivery/ZIP receipts would create a circular source-archive digest.
    excluded={'source_archive_build.json','artifact_manifest.json','delivery_verification.json',
              'final_artifact_review.json','publication.json','archive_index_reconciliation.json'}
    paths.update(p for p in (ROOT/'checks').rglob('*.json') if p.name not in excluded)
    for name in ('BRIEF.md','AUTHORING.md','README.md'):
        path=ROOT/name
        if path.is_file():paths.add(path)
    paths.update((ROOT/'reference').glob('*.txt'))
    paths.update((ROOT/'reference').glob('*.json'))
    replay=ROOT/'audit/news_replay_inventory.json'
    if not replay.is_file():raise ValueError('Explicit hash-bound July replay inventory required')
    replay_data=load(replay);rows=replay_data.get('files',[])
    if (replay_data.get('report_month')!='2024-07' or replay_data.get('dates')!=DATES
            or not rows or len({row['path'] for row in rows})!=len(rows)):
        raise ValueError('Incomplete, duplicate or non-July replay inventory')
    for field,name in [('source_acceptance_sha256','independent_source_review.json'),('market_acceptance_sha256','independent_market_review.json')]:
        if replay_data.get(field)!=sha(ROOT/'audit'/name):raise ValueError('Replay acceptance changed: '+name)
    replay_tool=module('build_source_inventory')
    for row in rows:
        path=replay_tool.safe_path(row['path'])
        if row.get('sha256')!=sha(path) or row.get('bytes')!=path.stat().st_size:
            raise ValueError('Replay inventory hash/size mismatch: '+row['path'])
        paths.add(path)
    paths.add(replay)
    required=('cache/news/','cache/rss_raw/','audit/news_provenance/','audit/market_raw/')
    members={path.relative_to(ROOT).as_posix() for path in paths}
    for prefix in required:
        if not any(name.startswith(prefix) for name in members):raise ValueError('Missing replay family '+prefix)
    for name in ('data/treasury_par.json','audit/treasury_retained.csv','audit/market_raw_retention.json'):
        if name not in members:raise ValueError('Missing exact market replay member '+name)
    for name,digest in load(ROOT/'audit/independent_market_review.json').get('input_sha256',{}).items():
        if name not in members or sha(ROOT/name)!=digest:
            raise ValueError('Independent market replay input missing or changed: '+name)
    source=load(ROOT/'audit/independent_source_review.json')
    bindings=source.get('input_bindings')
    if not isinstance(bindings,dict) or not bindings:raise ValueError('Current source input_bindings required')
    dependencies=list(bindings.items())
    for field,prefix in [('tool_sha256','tools/'),('contract_sha256',''),('reviewer_dependency_sha256','audit_work/')]:
        rows=source.get(field)
        if not isinstance(rows,dict) or not rows:raise ValueError('Missing source dependency map '+field)
        for name,digest in rows.items():
            if '/' in name:raise ValueError('Unexpected source dependency name '+name)
            dependencies.append((prefix+name,digest))
    dependencies.extend([('audit_work/review_sources.py',source.get('reviewer_tool_sha256')),
                         ('audit/news_physical_requests.jsonl',source.get('ledger_sha256')),
                         ('audit_work/physical_source_inventory.json',source.get('physical_source_inventory_sha256'))])
    for name,digest in dependencies:
        if name not in members or sha(ROOT/name)!=digest:raise ValueError('Source dependency missing or changed: '+name)
    ledger=[json.loads(line) for line in (ROOT/'audit/news_physical_requests.jsonl').read_text().splitlines() if line.strip()]
    for row in ledger:
        name=row.get('raw_response_path')
        if name and (name not in members or not name.startswith('cache/rss_raw/attempts/')
                     or sha(ROOT/name)!=row.get('raw_compressed_sha256')):
            raise ValueError('Physical source attempt missing or changed: '+str(name))
    for path in paths:
        relative=path.relative_to(ROOT).as_posix();parts=PurePosixPath(relative).parts
        if (not path.resolve().is_relative_to(ROOT) or not path.is_file() or path.is_symlink()
                or any(p.is_symlink() for p in path.parents if p.is_relative_to(ROOT))
                or set(parts)&replay_tool.FORBIDDEN_PARTS or any(part.startswith('.') for part in parts)
                or any(x in path.name.lower() for x in ('secret','credential','.pem','.key'))
                or any(month!='2024-07' for month in re.findall(r'20\d{2}-\d{2}(?=-\d{2}(?:\D|$))',relative))):
            raise ValueError('Unsafe final source-archive input: '+relative)
    inventory=[file_row(path) for path in sorted(paths)]
    out=ROOT/'collection'/SOURCE_NAME
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as archive:
        for row in inventory:archive.write(ROOT/row['path'],row['path'])
        archive.writestr('source_inventory.json',json.dumps(inventory,ensure_ascii=False,indent=2))
        if len(archive.namelist())!=len(inventory)+1 or len(set(archive.namelist()))!=len(inventory)+1:
            raise ValueError('Duplicate source ZIP members')
    result={'status':'complete','archive':file_row(out),'files':len(inventory),
            'inventory_sha256':hashlib.sha256(json.dumps(inventory,sort_keys=True).encode()).hexdigest()}
    atomic(ROOT/'checks/source_archive_build.json',result)
    return result

def main():
    dates=sys.argv[1:] or DATES
    if dates!=DATES:raise ValueError('Artifact collection build requires all 23 July weekdays')
    accepted_components(dates)
    require_retail_gates()
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
                if (all(old.get(k)==v for k,v in inputs.items()) and set(old.get('files',{}))=={'html','json','pdf'}
                        and old.get('pdf_preservation',{}).get('unicode_prose_preserved') is True
                        and old.get('pdf_preservation',{}).get('ordered_occurrences_preserved') is True
                        and all((ROOT/x['path']).is_file() and sha(ROOT/x['path'])==x['sha256'] for x in old['files'].values())):
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
            payload=load(jp)
            pdf_preservation=check_pdf_prose(date,pdf,payload['spec'],payload['evidence'])
            for marker in ['Geographic Macro Overview','Sector Deep Dive','What Retail Is Playing','Dated evidence']:
                if marker not in text:raise ValueError(date+' PDF missing '+marker)
            page.set_viewport_size({'width':390,'height':844});page.set_content(hp.read_text(),wait_until='load')
            overflow=page.evaluate('document.documentElement.scrollWidth>innerWidth')
            if overflow:raise ValueError(date+' mobile overflow')
            if date==dates[0]:page.screenshot(path=str(ROOT/'checks/mobile-preview.png'))
            page.set_viewport_size({'width':1440,'height':1000})
            row={'date':date,**inputs,'words':words,'distinct_sources':source_count,'warnings':warns,'pdf_pages':len(pdf.pages),'layout':layout,'mobile_overflow':False,'pdf_preservation':pdf_preservation,'files':{k:file_row(path) for k,path in [('html',hp),('json',jp),('pdf',pp)]}}
            atomic(receipt,row);manifest['reports'].append(row);print(date,words,'words',source_count,'sources',len(pdf.pages),'PDF pages',flush=True)
        browser.close()
    module('build_retail_page').build(dates)
    retail=ROOT/'retail/What_Retail_Is_Playing_2024-07.html'
    (ROOT/'collection'/retail.name).write_bytes(retail.read_bytes())
    (ROOT/'collection/methodology.txt').write_text(methodology(dates))
    (ROOT/'collection/2024-07.html').write_text(collection(dates))
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
    names=['2024-07.html','methodology.txt',ZIP_NAME,SOURCE_NAME,retail.name]
    manifest['collection']={n:file_row(ROOT/'collection'/n) for n in names}
    manifest['artifact_targets']=len(manifest['reports'])*3+len(names)
    if manifest['complete_month'] and (manifest['artifact_targets']!=74 or manifest['report_zip_members']!=72):
        raise ValueError('July full-month artifact count mismatch')
    atomic(ROOT/'checks/artifact_manifest.json',manifest)
    print('Artifacts complete; complete month:',manifest['complete_month'],flush=True)

if __name__=='__main__':main()
