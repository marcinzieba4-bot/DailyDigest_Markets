"""Independent report-content preservation and artifact checks; never publish.

--static inspects only generic pipeline code/constants, without reading report
facts or building artifacts. The default reviews existing final April artifacts,
checks every saved paragraph/ledger headline and exact archive member, and tests
all HTML layouts at desktop and 390px. This is an engineering review, not an
independent verification of the article bodies or economic interpretation.
"""
from pathlib import Path, PurePosixPath
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import re
import unicodedata
import zipfile
import gzip
import io
import tempfile
from unittest.mock import patch

import fitz
from bs4 import BeautifulSoup
from pypdf import PdfReader
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DATES = [dt.date(2024, 4, day).isoformat() for day in range(1, 31)
         if dt.date(2024, 4, day).weekday() < 5]
COLLECTION = {'2024-04.html', 'methodology.txt', 'April_2024_Weekday_Reports.zip',
              'April_2024_Frozen_Sources.zip', 'What_Retail_Is_Playing_2024-04.html'}
SECTIONS = ['geo', 'sectors', 'earnings', 'underowned', 'crypto', 'flows',
            'anticipatory', 'catalysts', 'retail']


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def load(path):
    return json.loads(path.read_text())


def normal(text):
    # Collapse layout whitespace without discarding brackets, numbers or boundaries.
    return ' '.join(unicodedata.normalize('NFC', text).split())


def paragraphs(spec):
    for key in ['geo', 'sectors', 'earnings_pattern', 'underowned', 'crypto',
                'flows', 'anticipatory', 'catalysts']:
        blocks = spec[key] if isinstance(spec[key], list) else [spec[key]]
        for i, block in enumerate(blocks):
            for label, text in block['parts']:
                yield (f'{key}.{i}.{label}', label, text)
    yield ('retail_intro', None, spec['retail_intro'])
    for i, block in enumerate(spec['retail']):
        for label, text in block['parts']:
            yield (f'retail.{i}.{label}', label, text)


def expected_order(spec):
    result = {}
    for _, _, text in paragraphs(spec):
        for key in re.findall(r'\[\[(n\d{4,6})\]\]', text):
            result.setdefault(key, len(result) + 1)
    return result


def displayed(text, order):
    return re.sub(r'\[\[(n\d{4,6})\]\]', lambda m: ' [' + str(order[m[1]]) + '] ', text)


def monotonic(text, entries, context):
    cursor = 0
    for label, value in entries:
        value = normal(value)
        offset = text.find(value, cursor)
        check(bool(value) and offset >= 0, context + ' lost/reordered occurrence ' + label)
        cursor = offset + len(value)
    return cursor


def pdf_preservation(date, text, spec, evidence):
    check('\ufffd' not in text and '\x00' not in text, date + ' corrupt PDF text')
    order = expected_order(spec)
    check(list(evidence) == list(order), date + ' wrong evidence order')
    text = normal(text)
    boundary = normal(f'Dated evidence · {len(evidence)} sources')
    check(text.count(boundary) == 1, date + ' missing/ambiguous PDF ledger boundary')
    body, ledger = text.split(boundary)
    entries = [(key, (label + ': ' if label is not None else '') + displayed(value, order))
               for key, label, value in paragraphs(spec)]
    monotonic(body, entries, date + ' PDF body')
    source_entries = []
    for key, item in evidence.items():
        value = item['title'] + ' — ' + item['src'] + ' · ' + item['published_at']
        if item.get('availability_review'):
            review = item['availability_review']
            value += ' Timing: ' + review['reason'] + ' Verified available before ' + review['known_before_utc'] + '. Timing evidence.'
        source_entries.append((key, value))
    monotonic(ledger, source_entries, date + ' PDF ledger')
    return len(entries)


def own_evidence(spec, feed, exceptions, date):
    order = expected_order(spec)
    records = {item['id']: item for item in feed['items']}
    available = {item['id']: item for item in exceptions if item['date'] == date}
    result = {}
    for key in order:
        check(key in records, date + ' evidence missing from own feed: ' + key)
        result[key] = dict(records[key])
        check(records[key]['published_at'][:10] < date, date + ' evidence after cutoff')
        if key in available:
            review = available[key]
            before = dt.datetime.fromisoformat(review['known_before_utc'].replace('Z', '+00:00'))
            check(before.tzinfo is not None and before < dt.datetime.fromisoformat(date).replace(tzinfo=dt.timezone.utc),
                  date + ' timing exception available only after cutoff: ' + key)
            result[key]['availability_review'] = review
    return result


def validate_evidence(actual, spec, feed, exceptions, date):
    expected = own_evidence(spec, feed, exceptions, date)
    check(list(actual) == list(expected) and actual == expected, date + ' JSON evidence differs from own frozen records')
    return expected


def html_preservation(page, spec, evidence, date):
    order = expected_order(spec)
    actual = page.select('p.report-part,p.retail-intro')
    expected = list(paragraphs(spec))
    check(len(actual) == len(expected), date + ' wrong HTML paragraph count')
    for node, (key, label, value) in zip(actual, expected):
        text = (label + ': ' if label is not None else '') + displayed(value, order)
        check(normal(node.get_text()) == normal(text), date + ' HTML lost/reordered paragraph: ' + key)
        expected_ids = re.findall(r'\[\[(n\d{4,6})\]\]', value)
        chips = node.select('a.source-cite')
        check([chip.get('data-source-id') for chip in chips] == expected_ids, date + ' wrong source-chip order')
        for chip, source_id in zip(chips, expected_ids):
            item = evidence[source_id]
            check(chip.get('href') == item['url'] and chip.get('title') == item['title']
                  and chip.get_text() == '[' + str(order[source_id]) + ']', date + ' source chip changed: ' + source_id)
    ledger = page.select_one('details.ledger')
    check(ledger is not None, date + ' missing HTML ledger')
    rows = ledger.select('ol > li')
    check([row.get('data-source-id') for row in rows] == list(evidence), date + ' wrong HTML ledger order')
    for row, (key, item) in zip(rows, evidence.items()):
        links = row.select('a')
        check(bool(links) and links[0].get('href') == item['url'] and links[0].get_text() == item['title'], date + ' ledger link changed: ' + key)
        core = item['title'] + ' — ' + item['src'] + ' · ' + item['published_at']
        check(normal(row.get_text()).startswith(normal(core)), date + ' ledger record changed: ' + key)
        if 'availability_review' in item:
            review = item['availability_review']
            note = 'Timing: ' + review['reason'] + ' Verified available before ' + review['known_before_utc'] + '. Timing evidence.'
            check(len(links) == 2 and links[1].get('href') == review['evidence_url']
                  and links[1].get_text() == 'Timing evidence'
                  and normal(row.get_text()) == normal(core + note), date + ' timing evidence metadata changed')
        else:
            check(len(links) == 1 and normal(row.get_text()) == normal(core), date + ' ledger metadata changed')
    return len(expected)

def monthly_retail_day(section, spec, feed, date):
    """Check every saved retail word, label, link and source record for one day."""
    check(section.get('id') == date and spec.get('date') == date, date + ' monthly retail date changed')
    records = {item['id']: item for item in feed['items']}
    texts = [spec['retail_intro']] + [text for item in spec['retail'] for _, text in item['parts']]
    ids = [key for text in texts for key in re.findall(r'\[\[(n\d{4,6})\]\]', text)]
    check(all(key in records and records[key]['published_at'][:10] < date for key in ids), date + ' monthly retail source missing/late')
    def prose(node, expected, label):
        check(node is not None, date + ' missing monthly ' + label)
        expected_ids = re.findall(r'\[\[(n\d{4,6})\]\]', expected)
        check([chip.get('data-source-id') for chip in node.select('sup.cite')] == expected_ids,
              date + ' monthly paragraph citation attribution changed: ' + label)
        clean = BeautifulSoup(str(node), 'html.parser')
        for chip in clean.select('sup.cite'):
            chip.decompose()
        expected = re.sub(r'\[\[n\d{4,6}\]\]', ' ', expected)
        check(normal(clean.get_text(' ', strip=True)) == normal(expected), date + ' monthly retail prose changed: ' + label)
    intros = section.select('.dayhead .intro')
    check(len(intros) == 1, date + ' wrong monthly introduction count')
    prose(intros[0], spec['retail_intro'], 'introduction')
    articles = section.select('article.trade')
    check(len(articles) == len(spec['retail']) == 4, date + ' wrong monthly trade count')
    for i, (article, item) in enumerate(zip(articles, spec['retail'])):
        heading = article.select_one('h3')
        check(heading is not None and heading.get_text(' ', strip=True) == item['title'], date + ' monthly retail title changed')
        parts = article.select('.part')
        check(len(parts) == len(item['parts']), date + ' monthly part count changed')
        for j, (part, (label, text)) in enumerate(zip(parts, item['parts'])):
            labels = part.select('h4'); paras = part.select('p')
            check(len(labels) == 1 and labels[0].get_text(' ', strip=True) == label, date + ' monthly part label changed')
            check(len(paras) == 1, date + ' monthly part paragraph missing/duplicated')
            prose(paras[0], text, f'trade {i} part {j}')
    chips = section.select('sup.cite')
    check([chip.get('data-source-id') for chip in chips] == ids, date + ' monthly source-chip order changed')
    for chip, key in zip(chips, ids):
        item = records[key]
        tip = ' · '.join(value for value in [item.get('published_at', '')[:16].replace('T', ' '), item.get('src', ''), item.get('title', '')] if value)
        check(chip.get_text(' ', strip=True) == key and chip.get('title') == tip, date + ' monthly source chip metadata changed')
        links = chip.select('a'); url = item.get('url', '')
        if url.startswith(('https://', 'http://')):
            check(len(links) == 1 and links[0].get('href') == url, date + ' monthly source chip URL changed')
        else:
            check(not links, date + ' monthly source chip added URL')
    ledgers = section.select('details.sources')
    check(len(ledgers) == 1, date + ' missing/duplicate monthly dated ledger')
    ledger = ledgers[0]; unique_ids = sorted(set(ids))
    summary = ledger.select_one('summary')
    check(summary is not None and summary.get_text(' ', strip=True) == f'Dated sources · {len(unique_ids)} headlines', date + ' monthly ledger count changed')
    rows = ledger.select('ol > li')
    check([row.get('data-source-id') for row in rows] == unique_ids, date + ' monthly ledger order changed')
    for row, key in zip(rows, unique_ids):
        item = records[key]; strong = row.select_one('strong'); small = row.select_one('small')
        check(strong is not None and strong.get_text() == key, date + ' monthly ledger source ID changed')
        metadata = item.get('src', '') + ' · ' + item.get('published_at', '').replace('T', ' ')
        check(small is not None and normal(small.get_text()) == normal(metadata), date + ' monthly ledger outlet/timestamp changed')
        check(normal(row.get_text(' ', strip=True)) == normal(key + ' · ' + item['title'] + ' ' + metadata),
              date + ' monthly full ledger record changed')
        links = row.select('a'); url = item.get('url', '')
        if url.startswith(('https://', 'http://')):
            check(len(links) == 1 and links[0].get('href') == url and links[0].get_text() == item['title'], date + ' monthly ledger title/URL changed')
        else:
            check(not links and item['title'] in row.get_text(), date + ' monthly ledger title changed')
    return {'date': date, 'trades': len(articles), 'parts': sum(len(item['parts']) for item in spec['retail']),
            'citation_occurrences': len(ids), 'ledger_records': len(unique_ids), 'intro_labels_links_and_ledger_preserved': True}

def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');tmp.replace(path)
def check(condition,message):
    if not condition:raise ValueError(message)
def module(name):
    p=ROOT/'tools'/(name+'.py');spec=importlib.util.spec_from_file_location('april_artifact_review_'+name,p)
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj

def tool_hashes():
    return {**{name:sha((ROOT/'tools'/name).read_bytes())for name in ['render.py','build_artifacts.py','build_retail_page.py','build_source_inventory.py']},
        'audit_work/review_final_artifacts.py':sha(Path(__file__).read_bytes())}

def safe_member(name):
    p=PurePosixPath(name)
    return isinstance(name,str)and bool(name)and not p.is_absolute()and '..'not in p.parts and '\\'not in name and str(p)==name and not any(t.startswith('.')for t in p.parts)and not set(p.parts)&{'.git','.aws','.ssh','__pycache__','node_modules','repo','repository','secrets','credentials'}

def static_review():
    modules={name:module(name)for name in ['render','build_artifacts','build_retail_page','build_source_inventory','publish','verify_delivery']}
    for name,obj in modules.items():
        compile((ROOT/'tools'/(name+'.py')).read_text(),name,'exec')
        if hasattr(obj,'DATES'):check(obj.DATES==DATES,'Wrong April scope in '+name)
    check(len(DATES)==22 and DATES[0]=='2024-04-01'and DATES[-1]=='2024-04-30','Wrong April22 scope')
    check('2024-04-01'in DATES,'Weekday holiday omitted')
    builder=modules['build_artifacts'];render=modules['render']
    check(builder.ZIP_NAME=='April_2024_Weekday_Reports.zip'and builder.SOURCE_NAME=='April_2024_Frozen_Sources.zip','Wrong bundle names')
    check('max-width:1280px'in render.BODY and '.retail-lead'in render.CSS and '@media print'in render.CSS,'Wide/retail/print styles lost')
    check('22 weekday editions'in builder.methodology(DATES),'Wrong methodology count')
    check(normal('Risk [100] remains.')!=normal('Risk remains.'),'Bracketed number lost')
    check(normal('Now here.')!=normal('Nowhere.'),'Word boundary lost')
    escaped=render.Doc({'n0001':{'title':'Łódź & <title>','url':'https://example.org/?a=1&b=2'}}).text('Łódź −3.2% & <tag> [[n0001]]')
    check('Łódź −3.2% &amp; &lt;tag&gt;'in escaped,'HTML Unicode/escaping lost')
    check(BeautifulSoup(render.esc('2024-04-01T23:50:00+00:00 non‑breaking'),'html.parser').get_text()=='2024-04-01T23:50:00+00:00 non‑breaking','Literal Unicode token changed')
    rejects=[]
    def reject(name,action):
        try:action()
        except (ValueError,KeyError,FileNotFoundError):rejects.append(name)
        else:raise ValueError('Unsafe fixture accepted: '+name)
    for d in ['2024-04-06','2024-06-03','../2024-04-01','20240401']:
        with patch('builtins.open',side_effect=AssertionError('Invalid scope read a source file')):
            reject('invalid_date_'+d,lambda d=d:render.render(d))
    reject('partial_collection',lambda:builder.collection(DATES[:1]))
    for p in ['../outside.json','/outside.json','audit_work//proof.json','audit_work/.private/proof.json']:
        check(not safe_member(p),'Unsafe ZIP name accepted');rejects.append('unsafe_path_'+p)
    # Text-preservation tests prove the checks reject deletion, not just that they run.
    spec={'date':'2024-04-01','geo':[],'sectors':[],'earnings_pattern':{'parts':[['First','Risk [100] remains. [[n0001]]'],['Second','Now here is the limit.']]},'underowned':[],'crypto':{'parts':[]},'flows':{'parts':[]},'anticipatory':[],'catalysts':[],'retail_intro':'Synthetic retail introduction.','retail':[]}
    ev={'n0001':{'id':'n0001','title':'Synthetic source','src':'Synthetic Outlet','published_at':'2024-03-31T12:00:00+00:00','url':'https://example.org/'}}
    good='First: Risk [100] remains. [1] Second: Now here is the limit. Synthetic retail introduction. Dated evidence · 1 sources Synthetic source — Synthetic Outlet · 2024-03-31T12:00:00+00:00'
    pdf_preservation('2024-04-01',good,spec,ev)
    for name,bad in [('bracket_deletion',good.replace('[100]','')),('word_join',good.replace('Now here','Nowhere')),('ledger_deletion',good.replace(' — Synthetic Outlet',''))]:
        reject(name,lambda bad=bad:pdf_preservation('2024-04-01',bad,spec,ev))
    return {'status':'static_checks_passed','dates':DATES,'tool_sha256':tool_hashes(),'artifact_targets_expected':71,'report_zip_members_expected':69,
        'runtime_artifacts_reviewed':False,'negative_fixtures':rejects,'scope':'Generic April scope, escaping, literal/paragraph preservation and unsafe-path checks. No historical data accepted.'}


def pdf_link_preservation(pdf,evidence,date):
    # Inspect actual PDF annotations independently of HTML labels and prose.
    urls=set()
    for page in pdf.pages:
        for ref in page.get('/Annots',[]):
            obj=ref.get_object();action=obj.get('/A')
            if action is None:continue
            if hasattr(action,'get_object'):action=action.get_object()
            if action.get('/URI') is not None:urls.add(str(action.get('/URI')))
    expected=set()
    for key,item in evidence.items():
        check(item['url']in urls,date+' missing clickable PDF source link '+key)
        expected.add(item['url'])
        if item.get('availability_review'):
            url=item['availability_review']['evidence_url'];check(url in urls,date+' missing timing URL '+key);expected.add(url)
    return {'unique_source_and_timing_URLs':len(expected),'all_source_links_clickable':True}

def source_archive_review(manifest,inventory):
    """Verify every public source member and current independent dependencies."""
    path=ROOT/'collection/April_2024_Frozen_Sources.zip';policy=module('build_source_inventory')
    source=load(ROOT/'audit/independent_source_review.json');market=load(ROOT/'audit/independent_market_review.json')
    policy.require_ready_receipts(source);transport=policy.require_physical_ledger(source);projection=policy.public_research_export()
    archive_row=manifest['collection'][path.name]
    check(sha(path.read_bytes())==archive_row['sha256']and path.stat().st_size==archive_row['bytes'],'Source ZIP differs from manifest')
    with zipfile.ZipFile(path)as archive:
        names=archive.namelist();check(len(names)==len(set(names))and archive.testzip()is None,'Duplicate/corrupt source ZIP')
        check(all(safe_member(n)for n in names),'Unsafe source ZIP member')
        rows=json.loads(archive.read('source_inventory.json'));check(len(rows)+1==len(names),'Wrong source inventory count')
        check({r['path']for r in rows}==set(names)-{'source_inventory.json'},'Source ZIP inventory membership changed')
        for row in rows:
            blob=archive.read(row['path']);local=ROOT/row['path']
            check(sha(blob)==row['sha256']and len(blob)==row['bytes'],'Source ZIP member changed: '+row['path'])
            check(local.is_file()and not local.is_symlink()and local.resolve().is_relative_to(ROOT)and blob==local.read_bytes(),'Source ZIP differs from local retained bytes: '+row['path'])
        policy.assert_no_raw_web_candidates(archive.read,names)
        policy.validate_public_research_bundle(archive.read,names,source)
        # Independently inspect the real retained source bytes and provenance;
        # repository-file identity does not establish deployed-package equality.
        code_names = ('source/lambda_function.py', 'code_provenance.json')
        check(set(code_names) <= set(names), 'Newest retained source/provenance absent from ZIP')
        code, provenance_blob = (archive.read(name) for name in code_names)
        provenance = json.loads(provenance_blob)
        check(provenance.get('source_path') == 'lambda_function.py'
            and type(provenance.get('source_bytes')) is int
            and provenance['source_bytes'] == len(code)
            and provenance.get('source_sha256') == sha(code)
            and re.fullmatch(r'[0-9a-f]{40}', provenance.get('source_commit', '')),
            'Newest retained source/provenance mismatch')
        for name, blob in zip(code_names, (code, provenance_blob)):
            check(source.get('input_bindings', {}).get(name) == sha(blob),
                'Newest retained source not bound by independent source review: ' + name)
        # All independently accepted live dependencies must be public exact bytes;
        # original private MCP responses are committed separately, not substituted.
        bindings=dict(source.get('input_bindings',{}))
        for field,prefix in [('tool_sha256','tools/'),('contract_sha256',''),('reviewer_dependency_sha256','audit_work/')]:
            for name,digest in source.get(field,{}).items():bindings[prefix+name]=digest
        bindings['audit_work/review_sources.py']=source['reviewer_tool_sha256']
        bindings.update(market.get('input_sha256',{}))
        for name,digest in bindings.items():
            check(name in names and sha(archive.read(name))==digest,'Missing/changed accepted source dependency: '+name)
        freeze=load(ROOT/'audit/source_freeze.json');check(source['source_freeze_sha256']==sha((ROOT/'audit/source_freeze.json').read_bytes()),'Current source-freeze binding lost')
        for date in DATES:
            for folder,suffix in [('specs','.json'),('cards','.json'),('feeds','.json.gz'),('nonretail_drafts','.json'),('retail_drafts','.json'),('exclusions','.json')]:
                name=folder+'/'+date+suffix;check(name in names,'Source ZIP missing '+name)
        for row in inventory['files']:
            check(row['path']in names and sha(archive.read(row['path']))==row['sha256'],'Replay input absent/changed: '+row['path'])
        return {'members':len(names),'accepted_dependency_hashes_checked':len(bindings),'public_research_projection':{k:v for k,v in projection.items()if k!='commitments'},'transport_counts':transport}


def runtime_review():
    static=static_review();manifest_path=ROOT/'checks/artifact_manifest.json';manifest=load(manifest_path)
    check(manifest.get('dates')==DATES and manifest.get('complete_month')is True,'Complete April artifact manifest required')
    check([r.get('date')for r in manifest.get('reports',[])]==DATES,'Wrong report manifest order/membership')
    check(set(manifest.get('collection',{}))==COLLECTION and manifest.get('artifact_targets')==71,'Wrong71 artifact targets')
    rows=[];retail_rows=[]
    exceptions=load(ROOT/'audit/canonical_source_exceptions.json').get('exceptions',[])if(ROOT/'audit/canonical_source_exceptions.json').exists()else[]
    retail=BeautifulSoup((ROOT/'retail/What_Retail_Is_Playing_2024-04.html').read_text(),'html.parser')
    retail_days=retail.select('section.day');check([n.get('id')for n in retail_days]==DATES,'Monthly retail dates/order changed')
    for mrow,day in zip(manifest['reports'],retail_days):
        date=mrow['date'];spec=load(ROOT/'specs'/f'{date}.json');feed=json.loads(gzip.decompress((ROOT/'feeds'/f'{date}.json.gz').read_bytes()))
        check(mrow['spec_sha256']==sha((ROOT/'specs'/f'{date}.json').read_bytes()),'Spec changed after build '+date)
        check(mrow['feed_sha256']==sha((ROOT/'feeds'/f'{date}.json.gz').read_bytes())and mrow['card_sha256']==sha((ROOT/'cards'/f'{date}.json').read_bytes()),'Inputs changed after build '+date)
        files=mrow['files'];check(set(files)=={'html','json','pdf'},'Missing native artifact '+date)
        expected_paths={'html':f'html/{date}.html','json':f'json/{date}_Market_Intelligence.json','pdf':f'pdf/{date}_Market_Intelligence.pdf'}
        for kind,record in files.items():
            check(record['path']==expected_paths[kind]and safe_member(record['path']),'Wrong exact native path')
            p=ROOT/record['path'];check(p.is_file()and not p.is_symlink()and sha(p.read_bytes())==record['sha256']and p.stat().st_size==record['bytes'],'Native artifact changed '+date+' '+kind)
        payload=load(ROOT/files['json']['path']);check(payload['spec']==spec and payload['report_date']==date and payload['news_cutoff_utc']==date+'T00:00:00Z','JSON spec/date/cutoff changed '+date)
        evidence=validate_evidence(payload['evidence'],spec,feed,exceptions,date)
        htmlpage=BeautifulSoup((ROOT/files['html']['path']).read_text(),'html.parser')
        check([n['id']for n in htmlpage.select('h2[id]')]==SECTIONS,'Daily section order changed '+date)
        html_count=html_preservation(htmlpage,spec,evidence,date)
        pdf=PdfReader(ROOT/files['pdf']['path']);footer=re.compile(r'(?m)^'+re.escape(date)+r'\s*·\s*Market Intelligence Briefing\s*·\s*\d+\s*/\s*\d+\s*$')
        # ActualText retains literal Unicode that the placeholder glyph omits.
        with fitz.open(ROOT/files['pdf']['path']) as semantic_pdf:
            text=' '.join(footer.sub('',p.get_text(sort=False))for p in semantic_pdf)
        pdf_count=pdf_preservation(date,text,spec,evidence)
        pdf_links=pdf_link_preservation(pdf,evidence,date)
        check(html_count==pdf_count,'PDF/HTML paragraph count differs '+date)
        retail_rows.append(monthly_retail_day(day,spec,feed,date))
        rows.append({'date':date,'spec_sha256':mrow['spec_sha256'],'html_paragraphs':html_count,'pdf_paragraphs':pdf_count,'pdf_pages':len(pdf.pages),'ledger_records':len(evidence),'pdf_links':pdf_links,'prose_ledger_and_citations_preserved':True})
    for name,row in manifest['collection'].items():
        p=ROOT/row['path'];check(row['path']=='collection/'+name and p.is_file()and sha(p.read_bytes())==row['sha256']and p.stat().st_size==row['bytes'],'Collection artifact changed '+name)
    bundle=ROOT/'collection/April_2024_Weekday_Reports.zip'
    with zipfile.ZipFile(bundle)as archive:
        expected={r['path']for report in manifest['reports']for r in report['files'].values()}|{'index.html','methodology.txt','What_Retail_Is_Playing_2024-04.html'}
        check(len(archive.namelist())==69 and set(archive.namelist())==expected and archive.testzip()is None,'Wrong/corrupt69-member report bundle')
        for report in manifest['reports']:
            for record in report['files'].values():check(sha(archive.read(record['path']))==record['sha256'],'Bundled report changed')
        check(archive.read('methodology.txt')==(ROOT/'collection/methodology.txt').read_bytes(),'Bundled methodology differs')
        check(archive.read('What_Retail_Is_Playing_2024-04.html')==(ROOT/'retail/What_Retail_Is_Playing_2024-04.html').read_bytes(),'Bundled retail differs')
        check(archive.read('index.html').decode()==module('build_artifacts').collection(DATES,offline=True),'Offline collection links/content changed')
    source=source_archive_review(manifest,load(ROOT/'audit/news_replay_inventory.json'))
    layouts=[]
    with sync_playwright()as p:
        browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        page=browser.new_page()
        for name in [r['files']['html']['path']for r in manifest['reports']]+['collection/2024-04.html','retail/What_Retail_Is_Playing_2024-04.html']:
            for width,height in [(1440,1000),(390,844)]:
                page.set_viewport_size({'width':width,'height':height});page.set_content((ROOT/name).read_text(),wait_until='load')
                check(not page.evaluate('document.documentElement.scrollWidth>innerWidth'),'Horizontal overflow '+name+' '+str(width))
                if name.startswith('html/'):
                    check(page.locator('h2[id]').count()==9 and page.locator('.retail-lead').count()==1,'Daily layout lost sections/lead')
                layouts.append({'path':name,'width':width,'horizontal_overflow':False})
        browser.close()
    return {'status':'accepted','runtime_artifacts_reviewed':True,'fatal_or_major_remaining':0,'dates':DATES,
        'reports':rows,'artifact_manifest_sha256':sha(manifest_path.read_bytes()),'tool_sha256':tool_hashes(),
        'monthly_retail_checks':retail_rows,'layouts':layouts,'report_zip_members':69,'source_archive_review':source,
        'static_negative_fixtures':static['negative_fixtures'],'scope':'Engineering preservation, own-date source membership, exact artifact/source archive bytes and responsive layout. Independent source/market/editorial acceptances remain separate.'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--static',action='store_true');args=parser.parse_args()
    result=static_review()if args.static else runtime_review()
    save(ROOT/'checks'/('artifact_static_review.json'if args.static else'final_artifact_review.json'),result)
    print(json.dumps({k:v for k,v in result.items()if k not in {'reports','layouts','monthly_retail_checks','source_archive_review'}},indent=2))

if __name__=='__main__':main()
