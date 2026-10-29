"""Render checked reports, make browser PDFs, and build the September collection.

No AWS calls. Run with the system Python (Playwright and pypdf installed).
The separate publish.py requires a complete passing manifest before upload.
"""
from pathlib import Path
import datetime as dt
import hashlib
import html
import importlib.util
import json
import sys
import zipfile
from playwright.sync_api import sync_playwright
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parent.parent
DATES=[dt.date(2025,9,n).isoformat() for n in range(1,31) if dt.date(2025,9,n).weekday()<5]

def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/f'{name}.py')
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def collection(dates):
    cards=[]
    for date in dates:
        spec=json.loads((ROOT/'specs'/f'{date}.json').read_text())
        us=spec['geo'][0]
        title=spec['retail'][0]['title']
        label=dt.date.fromisoformat(date).strftime('%a %d September')
        cards.append('<a class="day" href="archive/'+date+'.html"><span class="date">'+label+'</span><span class="stance">US: '+html.escape(us['stance'])+'</span><h2>'+html.escape(title)+'</h2><span>Read the briefing</span></a>')
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>September 2025 · Market Intelligence Archive</title><style>
    *{box-sizing:border-box}body{font-family:Arial,sans-serif;background:#f4f6fc;color:#243047;margin:auto;max-width:1400px;padding:60px 48px;line-height:1.6}h1{font-size:clamp(42px,6vw,76px);letter-spacing:-3px;line-height:1.05;margin:20px 0}h2{font-size:19px;line-height:1.45}p{max-width:850px;color:#64718b}.kicker{font-size:13px;text-transform:uppercase;letter-spacing:.12em;color:#285daf;font-weight:bold}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px;margin-top:40px}.day{color:inherit;text-decoration:none;border:1px solid #dce4f1;border-top:4px solid #1a73e8;border-radius:10px;padding:24px;background:white;display:flex;flex-direction:column;align-items:flex-start;min-height:230px;box-shadow:0 7px 30px #1c315408}.day:hover{border-color:#3972bf;transform:translateY(-2px)}.date{font-weight:bold}.stance{font-size:12px;color:#526a90;background:#edf2fc;border-radius:4px;padding:3px 7px;margin-top:12px}.day>span:last-child{font-size:12px;color:#185eb8;margin-top:auto}.button{display:inline-block;background:#1e58a7;color:white;text-decoration:none;padding:11px 18px;border-radius:6px;margin:12px 10px 12px 0}.note{margin-top:45px;padding:25px;background:#eaf0fa;border-radius:10px;font-size:13px}.note p{max-width:1100px}footer{margin-top:30px;font-size:12px;color:#7a879e}@media(max-width:900px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){body{padding:30px 20px}.grid{grid-template-columns:1fr}h1{letter-spacing:-1.5px}}
    </style></head><body><div class="kicker">DailyDigest Markets · Historical editions</div><h1>September 2025.<br>The information, day by day.</h1><p>22 weekday Market Intelligence Briefings, with the breadth of the August 2026 reports. Macro, 13 sectors, earnings, thematic opportunities, crypto, liquidity, scenarios, stock catalysts and retail narratives.</p><a class="button" href="2025-09/September_2025_Weekday_Reports.zip">Download all reports · HTML, PDF & JSON</a><a class="button" href="2025-09/methodology.txt">Sources & historical method</a><div class="grid">'''+''.join(cards)+'''</div><div class="note"><strong>The historical boundary</strong><p>Each report uses information indexed before its date at 00:00 UTC and completed prior market sessions. Later results are excluded. Publication timestamps from a news index are checked for obvious release-date mismatches, but original article vintages are not independently archived. Market prices use a current-vintage historical archive with later stock splits reversed for displayed price levels; later vendor revisions cannot be ruled out. These are reconstructed historical briefings, prepared in October 2026.</p></div><footer>All dates are report dates. Price changes exclude dividends; instrument sessions follow their local exchanges. No weekend editions.</footer></body></html>'''

METHOD='''September 2025 retrospective briefings — methodology

Scope: all 22 Monday–Friday dates, September 1–30, 2025.
Per-report news cutoff: 00:00 UTC on its report date, strictly exclusive.
Eligible source ages: news/policy/previews 7 days, earnings results 14 days,
monthly releases 35 days. Writers use only their report date's frozen feed and
market card. Same-day Asian releases and rolling/live headlines are excluded
when their release timing conflicts with the nominal index timestamp.

News: broad dated Google News historical RSS harvest, using shared query
windows. Eligibility is checked again after deduplication. Search-index result
limits mean coverage is broad, not exhaustive. Reports use headline facts,
not facts inferred from unread article bodies. Cited items retain outlet, title,
indexed timestamp and URL. Original article vintages are not independently
archived. Canonical publisher dates of cited direct Reuters stories are checked
through Google News metadata; date conflicts receive explicit UTC timing review
or conservative exclusion. URL metadata is not full article-body vintage proof.

Markets: Yahoo Finance daily historical chart data, completed sessions before
the report date, exchangeTimezoneName interpreted with ZoneInfo. Crypto uses
completed UTC days. 292 instruments per date. Percentage changes compare
split-adjusted closes over 1, 5 and 20 observations and exclude dividends.
Displayed price levels reverse later split factors to restore historical share
units. CMCSA levels are suppressed because its adjustment includes a spin-off.
Later corporate-action metadata is used only for unit conversion; later price
rows are excluded from writers' inputs. Current-vintage prices may contain later
vendor revisions; no original contemporaneous vendor snapshots were found.
Futures series may be affected by contract rolls.

Rates: US Treasury daily par yield curve, actual 2Y and 10Y instruments.
Yield changes and curve spreads are basis points, not percentage-of-yield
changes. Labor Day September 1 closes US stock and Treasury markets, so the
September 2 report retains August 29 US closes. Japan holidays and individual
exchange calendars follow the dated observations. Crypto trades every day.

Style: August 2026 nine-section structure, geographic and sector cards,
expanded desktop width, responsive navigation and linked evidence ledger.
Each HTML edition has a PDF and machine-readable JSON with its source evidence.

Code base: newest remote task branch at discovery, commit
f407a8c46170fd03d491dda933da72fc61816dad (October 29, 2026).
The underlying source branch 75f12ededa072406eb74b841f6b971b2977119fe
was rechecked; September uses the validated November pipeline and the requested
wide August layout without opening price widgets or sector leadership chart.
Historical execution is local and does not invoke the live current-time Lambda.

Access: runtime AWS_KEY/AWS_SECRET bindings explicitly select the ordinary boto3
session through the managed HTTPS proxy. No credentials are saved here. Only
report/archive objects are published; email and Telegram are not invoked.

'''

def main():
    dates=sys.argv[1:] or DATES
    if any(d not in DATES for d in dates):raise ValueError('Only September weekdays')
    verify=module('verify');render=module('render')
    manifest={'dates':dates,'reports':[],'complete_month':dates==DATES}
    (ROOT/'pdf').mkdir(exist_ok=True)
    (ROOT/'collection').mkdir(exist_ok=True)
    (ROOT/'checks'/'artifacts').mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
        for d in dates:
            fail,warn,n,words=verify.verify(d)
            if fail:raise ValueError(d+' validation failed: '+repr(fail))
            inputs={'spec_sha256':sha(ROOT/'specs'/f'{d}.json'),'card_sha256':sha(ROOT/'cards'/f'{d}.json'),'feed_sha256':sha(ROOT/'feeds'/f'{d}.json.gz'),'renderer_sha256':sha(ROOT/'tools'/'render.py'),'builder_sha256':sha(Path(__file__))}
            receipt=ROOT/'checks'/'artifacts'/f'{d}.json'
            if receipt.exists():
                previous=json.loads(receipt.read_text())
                same=all(previous.get(k)==value for k,value in inputs.items())
                intact=all((ROOT/f['path']).exists() and sha(ROOT/f['path'])==f['sha256'] for f in previous.get('files',{}).values())
                if same and intact:
                    previous.update(warnings=warn,words=words,distinct_sources=n)
                    manifest['reports'].append(previous)
                    print(d,words,n,'sources; unchanged checked artifacts reused',flush=True)
                    continue
            render.render(d)
            hp=ROOT/'html'/f'{d}.html';jp=ROOT/'json'/f'{d}_Market_Intelligence.json'
            pp=ROOT/'pdf'/f'{d}_Market_Intelligence.pdf'
            page.set_content(hp.read_text(),wait_until='load')
            if page.locator('.snapshot, .metric, .momentum').count() or 'Sector leadership at the prior close' in hp.read_text():raise ValueError(d+' removed top dashboard/chart remains')
            layout=page.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth,headings:document.querySelectorAll("h2[id]").length,citations:document.querySelectorAll(".source-cite").length})')
            if layout['scroll']>layout['width'] or layout['headings']!=9:raise ValueError(d+' invalid desktop layout')
            if d==dates[0]:page.screenshot(path=str(ROOT/'checks'/'desktop-preview.png'),full_page=False)
            page.pdf(path=str(pp),format='A4',print_background=True,margin={'top':'14mm','bottom':'16mm','left':'14mm','right':'14mm'},display_header_footer=True,header_template='<span></span>',footer_template='<div style="font-family:Arial;font-size:8px;width:100%;text-align:center;color:#8993a2">'+d+' · Market Intelligence Briefing · <span class="pageNumber"></span> / <span class="totalPages"></span></div>')
            reader=PdfReader(pp);text=' '.join(x.extract_text() or '' for x in reader.pages)
            for marker in ['Geographic Macro Overview','Sector Deep Dive','What Retail Is Playing']:
                if marker not in text:raise ValueError(d+' PDF missing '+marker)
            page.set_viewport_size({'width':390,'height':844});page.set_content(hp.read_text(),wait_until='load')
            overflow=page.evaluate('document.documentElement.scrollWidth>innerWidth')
            if overflow:raise ValueError(d+' mobile overflow')
            if d==dates[0]:page.screenshot(path=str(ROOT/'checks'/'mobile-preview.png'),full_page=False)
            page.set_viewport_size({'width':1440,'height':1000})
            row={'date':d,'words':words,'distinct_sources':n,'warnings':warn,'pdf_pages':len(reader.pages),'layout':layout,'mobile_overflow':overflow,**inputs,'files':{}}
            for name,path in [('html',hp),('json',jp),('pdf',pp)]:row['files'][name]={'path':str(path.relative_to(ROOT)),'bytes':path.stat().st_size,'sha256':sha(path)}
            manifest['reports'].append(row);print(d,words,n,'sources',len(reader.pages),'pages',flush=True)
            receipt.write_text(json.dumps(row,indent=2))
        browser.close()
    (ROOT/'collection'/'methodology.txt').write_text(METHOD)
    (ROOT/'collection'/'2025-09.html').write_text(collection(dates))
    zip_path=ROOT/'collection'/'September_2025_Weekday_Reports.zip'
    with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
        for row in manifest['reports']:
            for f in row['files'].values():z.write(ROOT/f['path'],f['path'])
        z.write(ROOT/'collection'/'methodology.txt','methodology.txt')
        offline=collection(dates).replace('href="archive/','href="html/').replace('href="2025-09/methodology.txt"','href="methodology.txt"').replace('href="2025-09/September_2025_Weekday_Reports.zip"','href="https://d7g7nkeytae81.cloudfront.net/reports/2025-09/September_2025_Weekday_Reports.zip"')
        z.writestr('index.html',offline)
    manifest['collection']={n:{'path':'collection/'+n,'sha256':sha(ROOT/'collection'/n),'bytes':(ROOT/'collection'/n).stat().st_size} for n in ['2025-09.html','methodology.txt','September_2025_Weekday_Reports.zip']}
    (ROOT/'checks'/'artifact_manifest.json').write_text(json.dumps(manifest,indent=2))
    print('Artifacts checked; complete month:',manifest['complete_month'])

if __name__=='__main__':main()
