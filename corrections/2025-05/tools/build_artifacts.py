"""Render checked reports, make browser PDFs, and build the May collection.

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
DATES=[dt.date(2025,5,n).isoformat() for n in range(1,32) if dt.date(2025,5,n).weekday()<5]

def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/f'{name}.py')
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def collection(dates):
    cards=[]
    prepared=dt.datetime.now(dt.timezone.utc).strftime('%B %Y')
    for date in dates:
        spec=json.loads((ROOT/'specs'/f'{date}.json').read_text())
        us=spec['geo'][0]
        title=spec['retail'][0]['title']
        label=dt.date.fromisoformat(date).strftime('%a %d %B')
        cards.append('<a class="day" href="archive/'+date+'.html"><span class="date">'+label+'</span><span class="stance">US: '+html.escape(us['stance'])+'</span><h2>'+html.escape(title)+'</h2><span>Read the briefing</span></a>')
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>May 2025 · Market Intelligence Archive</title><style>
    *{box-sizing:border-box}body{font-family:Arial,sans-serif;background:#f4f6fc;color:#243047;margin:auto;max-width:1400px;padding:60px 48px;line-height:1.6}h1{font-size:clamp(42px,6vw,76px);letter-spacing:-3px;line-height:1.05;margin:20px 0}h2{font-size:19px;line-height:1.45}p{max-width:850px;color:#64718b}.kicker{font-size:13px;text-transform:uppercase;letter-spacing:.12em;color:#285daf;font-weight:bold}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px;margin-top:40px}.day{color:inherit;text-decoration:none;border:1px solid #dce4f1;border-top:4px solid #1a73e8;border-radius:10px;padding:24px;background:white;display:flex;flex-direction:column;align-items:flex-start;min-height:230px;box-shadow:0 7px 30px #1c315408}.day:hover{border-color:#3972bf;transform:translateY(-2px)}.date{font-weight:bold}.stance{font-size:12px;color:#526a90;background:#edf2fc;border-radius:4px;padding:3px 7px;margin-top:12px}.day>span:last-child{font-size:12px;color:#185eb8;margin-top:auto}.button{display:inline-block;background:#1e58a7;color:white;text-decoration:none;padding:11px 18px;border-radius:6px;margin:12px 10px 12px 0}.note{margin-top:45px;padding:25px;background:#eaf0fa;border-radius:10px;font-size:13px}.note p{max-width:1100px}footer{margin-top:30px;font-size:12px;color:#7a879e}@media(max-width:900px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){body{padding:30px 20px}.grid{grid-template-columns:1fr}h1{letter-spacing:-1.5px}}
    </style></head><body><div class="kicker">DailyDigest Markets · Historical editions</div><h1>May 2025.<br>The information, day by day.</h1><p>'''+str(len(dates))+''' weekday Market Intelligence Briefings, with the breadth of the August 2026 reports. Macro, 13 sectors, earnings, thematic opportunities, crypto, liquidity, scenarios, stock catalysts and retail narratives.</p><a class="button" href="2025-05/May_2025_Weekday_Reports.zip">Download all reports · HTML, PDF & JSON</a><a class="button" href="2025-05/methodology.txt">Sources & historical method</a><div class="grid">'''+''.join(cards)+'''</div><div class="note"><strong>The historical boundary</strong><p>Each report uses information indexed before its date at 00:00 UTC and completed prior market sessions. Later results are excluded. Publication timestamps from a news index are checked for obvious release-date mismatches, but original article vintages are not independently archived. Market prices use a current-vintage historical archive with later stock splits reversed for displayed price levels; later vendor revisions cannot be ruled out. These are reconstructed historical briefings, prepared in '''+html.escape(prepared)+'''.</p></div><footer>All dates are report dates. Price changes exclude dividends; instrument sessions follow their local exchanges. No weekend editions.</footer></body></html>'''

def load_json(path):
    return json.loads(path.read_text()) if path.exists() else None


def frozen_archive(dates):
    """Freeze the actual writer feeds and audit receipts used for this build."""
    path = ROOT/'collection'/'May_2025_Frozen_News_Feeds.zip'
    included = []
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for d in dates:
            fp = ROOT/'feeds'/f'{d}.json.gz'
            if not fp.exists():
                fp = ROOT/'feeds'/f'{d}.json'
            z.write(fp, str(fp.relative_to(ROOT)))
            included.append(str(fp.relative_to(ROOT)))
            initial = ROOT/'feeds_initial'/f'{d}.json.gz'
            if initial.exists():
                z.write(initial, str(initial.relative_to(ROOT)))
                included.append(str(initial.relative_to(ROOT)))
        groups = [
            ('audit', ['news_*.json', '*metadata*.json', 'market_*.json',
                       'treasury_source.json', 'vendor_session_gaps.json',
                       'frozen_canonical_screening_after_recovery.json',
                       'access_diagnosis.json', 'cited_source_dates.json',
                       'canonical_source_exceptions.json', 'canonical_all_cited_urls.json',
                       'canonical_reuters_urls.json', 'release_guard_validation.json', '*_cutoff.json', '*_cutoffs.json',
                       '*_publication_time*.json', '*_timing_proof*.json', '*_status.json', '*_exclusion.json',
                       'independent_*_review.json']),
            ('checks', ['code_discovery.json', 'access_recovery.json',
                        'source_chronology_review.json', 'independent_selected_review.json',
                        'independent_selected_review_*.json', 'independent_editor_*.json',
                        'retail_quality.json', 'retail_editorial_decisions.json',
                        'retail_editorial_changes.json', 'selected_precision_changes.json',
                        'canonical_cache_scope.json', 'validation_warning_review.json',
                        'tooling_*.json', 'source_attribution_*.json', 'source_expansion_independent_review.json']),
        ]
        paths = set()
        for directory, patterns in groups:
            for pattern in patterns:
                paths.update((ROOT/directory).glob(pattern))
        for directory in ['audit/news_initial', 'audit/news_expansion_candidates',
                          'work/news_expansion/unreviewed_initial',
                          'work/news_expansion/drafts_at_start',
                          'work/news_expansion/drafts_before_apply']:
            paths.update(fp for fp in (ROOT/directory).rglob('*') if fp.is_file())
        exceptions = load_json(ROOT/'audit/canonical_source_exceptions.json') or {}
        for row in exceptions.get('exceptions', []):
            if row['date'] in dates:
                proof = (ROOT/row['timing_proof_file']).resolve()
                if not proof.is_relative_to(ROOT) or not proof.is_file():
                    raise ValueError('Missing or out-of-scope timing proof: '+str(proof))
                if sha(proof) != row['timing_proof_sha256']:
                    raise ValueError('Timing proof changed: '+str(proof))
                paths.add(proof)
        paths.update((ROOT/'tools').glob('*.py'))
        paths.add(ROOT/'posthoc/resolve_news_url.py')
        paths.add(ROOT/'work/news_expansion/check_tools.py')
        for fp in sorted(paths):
            z.write(fp, str(fp.relative_to(ROOT)))
            included.append(str(fp.relative_to(ROOT)))
    return {'path':str(path.relative_to(ROOT)), 'key':'reports/2025-05/'+path.name,
            'bytes':path.stat().st_size, 'sha256':sha(path), 'dates':len(dates), 'files':included}


def methodology(dates, frozen):
    """Derive every month-specific statistic from this run's files."""
    import gzip
    from collections import Counter
    feeds=[]; categories=Counter(); counts=[]
    for d in dates:
        fp=ROOT/'feeds'/f'{d}.json.gz'
        feed=json.load(gzip.open(fp,'rt')) if fp.exists() else load_json(ROOT/'feeds'/f'{d}.json')
        feeds.append(feed)
        categories.update(x['cat'] for x in feed['items'])
        counts.append(len(feed['items']))
    cards=[load_json(ROOT/'cards'/f'{d}.json') for d in dates]
    instrument_counts=sorted({len(c['markets']) for c in cards})
    by_date={c['report_date']:c for c in cards}
    carryovers=[]
    for report_date, ticker, label in [
            ('2025-05-02', '000001.SS', 'Mainland China Labour Day'),
            ('2025-05-02', '^HSI', 'Hong Kong Labour Day'),
            ('2025-05-02', 'ETFBW20TR.WA', 'Polish equities Labour Day'),
            ('2025-05-07', '^N225', 'Japan Golden Week'),
            ('2025-05-07', '^KS11', 'Korean May holidays'),
            ('2025-05-27', '^GSPC', 'US equities Memorial Day')]:
        market=by_date.get(report_date, {}).get('markets', {}).get(ticker)
        if market:
            carryovers.append(f"{label}: {report_date} edition uses the {market['session']} completed local close.")
    treasury=by_date.get('2025-05-27', {}).get('treasury')
    if treasury:
        carryovers.append('US Treasury: 2025-05-27 edition uses the '+treasury['prior_close_date']+' observation.')
    session_notes='\n'.join(carryovers) or 'Instrument-specific completed sessions are recorded in each market card.'
    harvest=load_json(ROOT/'audit/news_fetch_audit.json') or {}
    ready=load_json(ROOT/'audit/news_ready_audit.json') or {}
    market=load_json(ROOT/'audit/market_validation.json') or {}
    discovery=load_json(ROOT/'checks/code_discovery.json') or {}
    expansion=load_json(ROOT/'audit/news_feed_expansion.json') or {}
    expansion_summary=(
        f"As-of-cutoff prefix requests: {expansion['prefix_requests']:,}; "
        f"additional unique query URLs: {expansion['unique_additional_request_urls']:,}; "
        f"total unique query URLs: {expansion['unique_total_request_urls']:,}; "
        f"appended eligible records: {expansion['added_records']:,}; "
        f"remaining distinct daily-capped requests: {expansion['remaining_distinct_daily_caps']:,}."
        if expansion else 'A completed versioned expansion is required before a final build.')
    acquisition=''
    for key,label in [('query_count','queries'),('shared_query_windows','shared query windows'),('possibly_capped_windows','possibly capped windows')]:
        if key in harvest: acquisition+=f"{label}: {harvest[key]}; "
    if 'failed_windows' in harvest: acquisition+=f"failed windows: {len(harvest['failed_windows'])}."
    if not acquisition: acquisition='Acquisition details are recorded in the included source audit receipts.'
    code='\n'.join(f'{key}: {value}' for key,value in discovery.items() if 'commit' in key or 'branch' in key)
    if not code: code='The source discovery receipt is included with the source archive when available.'
    prepared=dt.datetime.now(dt.timezone.utc).strftime('%B %Y')
    return f'''May 2025 retrospective briefings — methodology

Scope: {len(dates)} Monday–Friday report dates, {dates[0]} through {dates[-1]}.
Per-report news cutoff: 00:00 UTC on its report date, strictly exclusive.
Source-query lookbacks: fresh news and previews 7 days, company results 14 days,
macro releases and policy baselines 35 days. Categories originate in the query
catalogue; older background is time-qualified and is not presented as a fresh
event. Drafting and final editing use only the matching own-date feed and market card.
The initial drafting snapshots are preserved in feeds_initial/. A versioned coverage
repair adds query prefixes ending at each straddled report cutoff and splits
capped windows into daily queries. It appends eligible own-date headlines without
changing original records or citation IDs. The initial fetch_news.py/build_feed
path preserves v1 acquisition and replay; final exports require the completed
expand_capped_news.py repair and its independently reviewed feed hashes.
Final editorial checks and exports bind the expanded frozen feeds in feeds/.
The expansion audit records original/final hashes, queries, exclusions and limits.
Actual releases at or after the UTC cutoff are excluded until a later edition.

News: dated Google News historical RSS, {sum(counts):,} own-date headline records
across these {len(dates)} feeds (per-date range {min(counts):,}–{max(counts):,}).
Category totals count the same headline again when eligible on multiple dates:
{dict(sorted(categories.items()))}.
Acquisition audit: {acquisition}
Versioned coverage repair: {expansion_summary}
Search-index result limits mean coverage is broad, not exhaustive. Publication
timestamps can be approximate. Reports use cited headline facts, not details
inferred from unread article bodies. Original article vintages are not
independently archived. Readiness and chronology audit receipts, where present,
record conservative exclusions and source-date checks; metadata does not prove
an original article-body vintage. Later outcomes are excluded from writer inputs.

Some publisher URLs use a later local calendar date. Explicit source-ledger timing
notes identify original publications or underlying releases independently proved
available before the report cutoff; they do not admit later article details.

Frozen feeds and included audit receipts:
https://d7g7nkeytae81.cloudfront.net/{frozen['key']}
SHA256: {frozen['sha256']}
The report bundle contains cited evidence ledgers, not all raw feed rows.

Markets: Yahoo Finance historical daily charts, completed sessions before each
report date, exchange-local session dates; crypto uses completed UTC days.
Instruments per card: {', '.join(map(str,instrument_counts))}.
Returns compare split-adjusted closes over 1, 5 and 20 observations and exclude
dividends. Displayed price levels restore historical share units by reversing
later split factors. CMCSA levels are suppressed because its adjustment includes
a spin-off. Corporate-action metadata is used only for unit conversion; later
price rows are excluded from writer inputs. Current-vintage prices may include
later vendor revisions; original contemporaneous vendor snapshots were not found.
Futures series may be affected by contract rolls.
Instrument-specific gaps and split/restoration limits are recorded in this month's
market provenance and validation audits. Local closures use the last completed
session, without inventing a holiday-session quote. Selected observations derived
from the final cards:
{session_notes}
Crypto has completed UTC daily candles.
Returns compare 20 valid observations, rather than calendar days, and exclude
dividends. Treasury uses actual two- and ten-year par yields; yield changes and
curve spreads are basis points.

Style: August 2026 nine-section structure, geographic and sector cards,
1280px desktop width, responsive navigation and linked evidence ledger.
Each HTML edition has a PDF and machine-readable JSON with its source evidence.
Prepared retrospectively in {prepared}; these are historical reconstructions.

Code provenance:
{code}
Each edition uses its own dated historical inputs. Source acquisition, exclusions,
chronology checks and retrieval limits are recorded in the included audit receipts.
'''


def main():
    review_spec=importlib.util.spec_from_file_location('may_review_gate',ROOT/'tools'/'review_gate.py')
    review_module=importlib.util.module_from_spec(review_spec);review_spec.loader.exec_module(review_module)
    # A new validated build may replace a stale manifest. Other callers require
    # the current proof to match the manifest produced here.
    review_proof=review_module.require_review(check_manifest=False)
    retail_quality_gate=importlib.util.spec_from_file_location('retail_quality_gate',ROOT.parent/'retail-quality'/'retail_quality.py')
    retail_quality_module=importlib.util.module_from_spec(retail_quality_gate);retail_quality_gate.loader.exec_module(retail_quality_module)
    retail_quality_module.require_review(ROOT)
    dates=sys.argv[1:] or DATES
    if any(d not in DATES for d in dates):raise ValueError('Only May 2025 weekdays')
    if len(dates)!=len(set(dates)):raise ValueError('Duplicate report dates')
    market_audit=load_json(ROOT/'audit/market_validation.json') or {}
    if market_audit.get('passed') is not True:raise ValueError('Passing market validation required')
    for d in dates:
        if market_audit.get('card_sha256',{}).get(d)!=sha(ROOT/'cards'/f'{d}.json'):
            raise ValueError(d+' market card changed after validation')
    verify=module('verify');render=module('render')
    manifest={'dates':dates,'reports':[],'complete_month':dates==DATES,
              'review_receipts':review_proof}
    (ROOT/'pdf').mkdir(exist_ok=True)
    (ROOT/'collection').mkdir(exist_ok=True)
    (ROOT/'checks'/'artifacts').mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
        for d in dates:
            fail,warn,n,words=verify.verify(d)
            if fail:raise ValueError(d+' validation failed: '+repr(fail))
            inputs={'spec_sha256':sha(ROOT/'specs'/f'{d}.json'),'card_sha256':sha(ROOT/'cards'/f'{d}.json'),'feed_sha256':sha(ROOT/'feeds'/f'{d}.json.gz'),'renderer_sha256':sha(ROOT/'tools'/'render.py'),'builder_sha256':sha(Path(__file__)), 'timing_exceptions_sha256':sha(ROOT/'audit/canonical_source_exceptions.json')}
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
    frozen=frozen_archive(dates)
    manifest['frozen_source_archive']=frozen
    (ROOT/'checks'/'source_archive_build.json').write_text(json.dumps(frozen,indent=2))
    (ROOT/'collection'/'methodology.txt').write_text(methodology(dates,frozen))
    (ROOT/'collection'/'2025-05.html').write_text(collection(dates))
    zip_path=ROOT/'collection'/'May_2025_Weekday_Reports.zip'
    with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
        for row in manifest['reports']:
            for f in row['files'].values():z.write(ROOT/f['path'],f['path'])
        z.write(ROOT/'collection'/'methodology.txt','methodology.txt')
        offline=collection(dates).replace('href="archive/','href="html/').replace('href="2025-05/methodology.txt"','href="methodology.txt"').replace('href="2025-05/May_2025_Weekday_Reports.zip"','href="https://d7g7nkeytae81.cloudfront.net/reports/2025-05/May_2025_Weekday_Reports.zip"')
        z.writestr('index.html',offline)
    manifest['collection']={n:{'path':'collection/'+n,'sha256':sha(ROOT/'collection'/n),'bytes':(ROOT/'collection'/n).stat().st_size} for n in ['2025-05.html','methodology.txt','May_2025_Weekday_Reports.zip']}
    (ROOT/'checks'/'artifact_manifest.json').write_text(json.dumps(manifest,indent=2))
    print('Artifacts checked; complete month:',manifest['complete_month'])

if __name__=='__main__':main()
