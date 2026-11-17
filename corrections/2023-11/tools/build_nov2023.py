"""build_nov2023.py — build the validated November 2023 HTML/JSON/PDF editions and the month collection.

Gates (fail closed): every final spec passes verify.py; each spec equals the reviewed nonretail draft plus the
reviewed retail draft; both independent receipts bind the current feed, card, exclusions and component hashes;
the retail-quality snapshot passes with --require-reviewed. Then: render.py → html/ + json/, Node Playwright → pdf/
(desktop/mobile layout checks), pypdf text checks, retail collection page, archive page, methodology, report ZIP.
No AWS, publication, Lambda, e-mail or Telegram calls."""
import datetime as dt, hashlib, html, importlib.util, json, subprocess, sys, zipfile
from pathlib import Path
from pypdf import PdfReader
ROOT = Path(__file__).resolve().parent.parent
DATES = [dt.date(2023, 11, n).isoformat() for n in range(1, 31) if dt.date(2023, 11, n).weekday() < 5]
MONTH = '2023-11'
ZIP_NAME = 'November_2023_Weekday_Reports.zip'
RETAIL_NAME = 'What_Retail_Is_Playing_2023-11.html'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
load = lambda p: json.loads(p.read_text())
def module(name):
    spec = importlib.util.spec_from_file_location('nov2023_' + name, ROOT / 'tools' / f'{name}.py')
    obj = importlib.util.module_from_spec(spec); spec.loader.exec_module(obj); return obj
def content_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
def file_row(p): return {'path': str(p.relative_to(ROOT)), 'sha256': sha(p), 'bytes': p.stat().st_size}

def accepted(date):
    feed, card, excl = ROOT/'feeds'/f'{date}.json.gz', ROOT/'cards'/f'{date}.json', ROOT/'exclusions'/f'{date}.json'
    spec = load(ROOT/'specs'/f'{date}.json')
    nonretail = load(ROOT/'nonretail_drafts'/f'{date}.json'); rpath = ROOT/'retail_drafts'/f'{date}.json'; retail = load(rpath)
    if {k: v for k, v in spec.items() if k not in ('retail', 'retail_intro')} != nonretail: raise ValueError(date + ' spec differs from nonretail draft')
    if spec.get('retail') != retail.get('retail') or spec.get('retail_intro') != retail.get('retail_intro'): raise ValueError(date + ' spec differs from retail draft')
    for kind in ('nonretail', 'retail'):
        r = load(ROOT/'audit'/f'independent_{kind}_{date}.json')
        ok = (r.get('date') == date and r.get('status') in ('accepted', 'passed') and r.get('fatal_or_major_remaining') == 0
              and r.get('feed_sha256') == sha(feed) and r.get('card_sha256') == sha(card) and r.get('exclusions_sha256') == sha(excl))
        if kind == 'nonretail': ok = ok and r.get('nonretail_content_sha256') == content_sha(nonretail)
        else: ok = ok and r.get('retail_draft_sha256') == sha(rpath)
        if not ok: raise ValueError(f'{date} {kind} review receipt stale or not accepted')

def collection(dates, offline=False):
    cards = []
    for date in dates:
        spec = load(ROOT/'specs'/f'{date}.json'); us = spec['geo'][0]
        label = dt.date.fromisoformat(date).strftime('%a %d %B')
        dest = ('html/' if offline else 'archive/') + date + '.html'
        cards.append('<a class="day" href="' + dest + '"><span class="date">' + label + '</span><span class="stance">US: ' + html.escape(us['stance']) + ' · ' + html.escape(us['label']) + '</span><h2>' + html.escape(spec['retail'][0]['title']) + '</h2><span>Read the briefing &rarr;</span></a>')
    root = '' if offline else MONTH + '/'
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>November 2023 · Market Intelligence Archive</title><style>
*{box-sizing:border-box}body{font-family:Arial,sans-serif;background:#f4f6fc;color:#243047;margin:auto;max-width:1400px;padding:60px 48px;line-height:1.6}h1{font-size:clamp(42px,6vw,76px);letter-spacing:-3px;line-height:1.05;margin:20px 0}h2{font-size:19px;line-height:1.45}p{max-width:850px;color:#64718b}.kicker{font-size:13px;text-transform:uppercase;letter-spacing:.12em;color:#285daf;font-weight:bold}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px;margin-top:40px}.day{color:inherit;text-decoration:none;border:1px solid #dce4f1;border-top:4px solid #1a73e8;border-radius:10px;padding:24px;background:white;display:flex;flex-direction:column;align-items:flex-start;min-height:230px;box-shadow:0 7px 30px #1c315408}.day:hover{border-color:#3972bf;transform:translateY(-2px)}.date{font-weight:bold}.stance{font-size:12px;color:#526a90;background:#edf2fc;border-radius:4px;padding:3px 7px;margin-top:12px}.day>span:last-child{font-size:12px;color:#185eb8;margin-top:auto}.button{display:inline-block;background:#1e58a7;color:white;text-decoration:none;padding:11px 18px;border-radius:6px;margin:12px 10px 12px 0}.button.retail{background:#d45627}.note{margin-top:45px;padding:25px;background:#eaf0fa;border-radius:10px;font-size:13px}.note p{max-width:1100px}footer{margin-top:30px;font-size:12px;color:#7a879e}@media(max-width:900px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){body{padding:30px 20px}.grid{grid-template-columns:1fr}h1{letter-spacing:-1.5px}}
</style></head><body><div class="kicker">DailyDigest Markets · Historical editions</div><h1>November 2023.<br>The information, day by day.</h1><p>''' + str(len(dates)) + ''' weekday Market Intelligence Briefings in the wide August 2026 style: six macro regions, thirteen sectors, earnings, thematic opportunities, crypto, liquidity, scenarios, stock catalysts and retail narratives.</p><a class="button" href="''' + root + ZIP_NAME + '''">Download all reports · HTML, PDF & JSON</a><a class="button retail" href="''' + root + RETAIL_NAME + '''">What Retail Is Playing · the full month</a><a class="button" href="''' + root + '''methodology.txt">Sources & historical method</a><div class="grid">''' + ''.join(cards) + '''</div><div class="note"><strong>The historical boundary</strong><p>Each edition uses its own dated information before 00:00 UTC and completed prior market sessions. News-index timestamps are screened for release-date conflicts; original publisher vintages are not independently archived. Current-vintage market histories may contain later vendor revisions. Historical share units are mechanically restored using split events. Later outcomes are excluded from the analysis.</p></div><footer>Report dates: 1–30 November 2023. All Monday–Friday dates receive editions, including exchange holidays (US Thanksgiving, 23 November). No weekend editions. Price changes exclude dividends.</footer></body></html>'''

def methodology(dates):
    cov = load(ROOT/'audit/news_coverage.json'); pc = cov['physical_attempt_counts']
    return f'''November 2023 Market Intelligence Briefings
{len(dates)} weekday editions, {dates[0]} through {dates[-1]}.

Historical boundary
Every edition uses its own information cutoff at 00:00 UTC on the report date.
News and previews use a seven-day lookback, company results fourteen days,
and monthly economic releases / policy baselines thirty-five days. The sources
are dated Google News RSS headline records, not full article bodies or an
independently archived contemporaneous publication corpus. {cov['unique_query_urls']:,} own-cutoff
query windows were requested ({pc['recorded_finished_attempts']:,} physical attempts, {pc['failed_attempts']} transient
failures retried, no unresolved query, no capped response). A release-clock screen
of {len(load(ROOT/'audit_work/nov2023_release_schedule.json')['guards'])} scheduled releases, decisions, results and staged events removed
headlines that report an outcome before it existed; reviewed preview and
different-event matches are recorded. Day-granular index timestamps can trail the
true publication time; independent editorial review checked cited headlines.

Market data
Yahoo Finance daily chart histories supply completed exchange-local sessions;
crypto uses the completed preceding UTC daily candle. Returns are price changes,
excluding dividends, over one, five and twenty observations. Historical quoted
share units are mechanically reconstructed using split metadata; later price
observations are not retained. Numeric spot-FX marks and returns are excluded
because the provider's dated daily Close may represent an opening reference
quote rather than a verified completed close. Currency discussion uses eligible
dated reporting. DXY remains a separate dollar index. Instruments without listed
history before the cutoffs are marked unavailable. Missing observations are not
estimated. Current-vintage vendor histories can include later corrections. The
official US Treasury daily par curve supplies yield levels, changes and spreads in
basis points. Equity and bond-market holidays differ; no holiday session is invented.

Layout and files
Each report has nine sections, six macro regions, thirteen sectors, four themes,
four event scenarios, six company catalysts and four retail narratives. The
retail lead has six parts; each of three smaller trades has motivation and
invalidation. Retail sections were written by a dedicated chronological writer
chain and reviewed against strictly earlier selections. Conditional market
interpretation is distinguished from observed crowd activity. Price moves alone
do not establish retail-flow rankings. HTML and JSON retain the dated citation
ledger; PDFs include the full report and source ledger.

Review
Every nonretail and retail component received an independent AI review by an
agent other than its author (not a human review); receipts bind the exact feed,
card, exclusion and component hashes.

Prepared retrospectively in November 2026. These are historical research editions,
not an assertion of original unrevised article or market-data vintages.
'''

def main():
    dates = DATES
    verify = module('verify'); render = module('render')
    for folder in ('pdf', 'collection', 'checks', 'html', 'json', 'retail'): (ROOT/folder).mkdir(exist_ok=True)
    rows = []
    for date in dates:
        accepted(date)
        fails, warns, n, words = verify.verify(date)
        if fails: raise ValueError(date + ' validation failed: ' + repr(fails[:5]))
        render.render(date)
        rows.append({'date': date, 'words': words, 'distinct_sources': n, 'warnings': warns})
    subprocess.run(['node', str(ROOT/'tools/pdf_render.js'), str(ROOT), *dates], check=True, cwd='/tmp')
    for row in rows:
        date = row['date']; hp = ROOT/'html'/f'{date}.html'; jp = ROOT/'json'/f'{date}_Market_Intelligence.json'; pp = ROOT/'pdf'/f'{date}_Market_Intelligence.pdf'
        pdf = PdfReader(pp); text = ' '.join(x.extract_text() or '' for x in pdf.pages)
        for marker in ('Geographic Macro Overview', 'Sector Deep Dive', 'What Retail Is Playing', 'Dated evidence'):
            if marker not in text: raise ValueError(date + ' PDF missing ' + marker)
        row.update(pdf_pages=len(pdf.pages), files={k: file_row(p) for k, p in (('html', hp), ('json', jp), ('pdf', pp))})
        print(date, row['words'], 'words', row['distinct_sources'], 'sources', row['pdf_pages'], 'PDF pages', flush=True)
    module('build_retail_page').build(dates)
    retail = ROOT/'retail'/RETAIL_NAME
    (ROOT/'collection'/RETAIL_NAME).write_bytes(retail.read_bytes())
    (ROOT/'collection/methodology.txt').write_text(methodology(dates))
    (ROOT/'collection'/f'{MONTH}.html').write_text(collection(dates))
    zp = ROOT/'collection'/ZIP_NAME
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
        for row in rows:
            for f in row['files'].values(): z.write(ROOT/f['path'], f['path'])
        z.write(ROOT/'collection/methodology.txt', 'methodology.txt'); z.write(retail, retail.name)
        z.writestr('index.html', collection(dates, offline=True))
    manifest = {'dates': dates, 'reports': rows, 'total_words': sum(r['words'] for r in rows), 'total_pdf_pages': sum(r['pdf_pages'] for r in rows),
                'collection': {n: file_row(ROOT/'collection'/n) for n in (f'{MONTH}.html', 'methodology.txt', ZIP_NAME, RETAIL_NAME)},
                'publication': 'Not published: no AWS credentials in this environment; artifacts built locally only.'}
    (ROOT/'checks/artifact_manifest.json').write_text(json.dumps(manifest, indent=1) + '\n')
    print('ARTIFACTS COMPLETE', manifest['total_words'], 'words', manifest['total_pdf_pages'], 'PDF pages')

if __name__ == '__main__':
    main()
