"""Independent report-content preservation and artifact checks; never publish.

--static inspects only generic pipeline code/constants, without reading report
facts or building artifacts. The default reviews existing final July artifacts,
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

from bs4 import BeautifulSoup
from pypdf import PdfReader
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DATES = [dt.date(2024, 7, day).isoformat() for day in range(1, 32)
         if dt.date(2024, 7, day).weekday() < 5]
COLLECTION = {'2024-07.html', 'methodology.txt', 'July_2024_Weekday_Reports.zip',
              'July_2024_Frozen_Sources.zip', 'What_Retail_Is_Playing_2024-07.html'}
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
    source_entries = [(key, item['title'] + ' — ' + item['src'] + ' · ' + item['published_at'])
                      for key, item in evidence.items()]
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
            result[key]['availability_review'] = available[key]
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
            check(len(links) == 2 and links[1].get('href') == item['availability_review']['evidence_url'], date + ' timing evidence changed')
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

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def check(condition, message):
    if not condition:
        raise ValueError(message)


def negative_fixtures(modules):
    """Adversarial synthetic checks only; no historical report inputs/builds."""
    results = []
    def rejected(name, action):
        try:
            action()
        except ValueError:
            results.append({'case': name, 'result': 'rejected_as_required'})
        else:
            raise ValueError('Negative fixture was accepted: ' + name)
    builder = modules['build_artifacts']; inventory = modules['build_source_inventory']
    for name, normalizer in [('builder', builder.prose_key), ('reviewer', normal)]:
        check(normalizer('Risk [100] remains.') != normalizer('Risk remains.'), name + ' dropped literal brackets')
        check(normalizer('Now here is the limit.') != normalizer('Nowhere is the limit.'), name + ' lost word boundary')
        results += [{'case': name + '_literal_bracket_preserved', 'result': 'distinct_as_required'},
                    {'case': name + '_word_boundary_preserved', 'result': 'distinct_as_required'}]
    spec = {'date': '2024-07-01', 'geo': [], 'sectors': [],
            'earnings_pattern': {'parts': [['First', 'Risk [100] remains. [[n0001]]'],
                                           ['Second', 'Now here is the limit.'],
                                           ['Again', 'Repeat this occurrence.'], ['Again', 'Repeat this occurrence.']]},
            'underowned': [], 'crypto': {'parts': []}, 'flows': {'parts': []},
            'anticipatory': [], 'catalysts': [], 'retail_intro': 'Synthetic crowd introduction.', 'retail': []}
    evidence = {'n0001': {'id': 'n0001', 'title': 'Synthetic source title', 'src': 'Synthetic Outlet',
                         'published_at': '2024-06-30T12:00:00+00:00', 'url': 'https://example.org/source'}}
    order = expected_order(spec)
    entries = [(label + ': ' if label else '') + displayed(value, order) for _, label, value in paragraphs(spec)]
    ledger = 'Dated evidence · 1 sources Synthetic source title — Synthetic Outlet · 2024-06-30T12:00:00+00:00'
    good = ' '.join(entries) + ' ' + ledger
    class Page:
        def __init__(self, value): self.value = value
        def extract_text(self): return self.value
    class PDF:
        def __init__(self, value): self.pages = [Page(value)]
    for name, checker in [('builder', lambda value: builder.check_pdf_prose('2024-07-01', PDF(value), spec, evidence)),
                          ('reviewer', lambda value: pdf_preservation('2024-07-01', value, spec, evidence))]:
        checker(good)
        rejected(name + '_literal_bracket_deleted', lambda: checker(good.replace('[100]', '')))
        rejected(name + '_word_boundary_corrupted', lambda: checker(good.replace('Now here', 'Nowhere')))
        reversed_body = ' '.join([entries[1], entries[0], *entries[2:]]) + ' ' + ledger
        rejected(name + '_paragraphs_reordered', lambda: checker(reversed_body))
        rejected(name + '_repeated_occurrence_deleted', lambda: checker(good.replace(entries[2] + ' ', '', 1)))
        rejected(name + '_ledger_outlet_deleted', lambda: checker(good.replace(' — Synthetic Outlet', '')))
        rejected(name + '_ledger_timestamp_deleted', lambda: checker(good.replace(' · 2024-06-30T12:00:00+00:00', '')))
        rejected(name + '_ledger_missing_body_title_present', lambda: checker(good.replace(ledger, 'Synthetic source title')))
    doc = modules['render'].Doc(evidence)
    nodes = []
    for _, label, value in paragraphs(spec):
        nodes.append(doc.parts([(label, value)])[0] if label is not None else '<p class="retail-intro">' + doc.text(value) + '</p>')
    html_text = ''.join(nodes) + '<details class="ledger"><ol><li data-source-id="n0001"><a href="https://example.org/source">Synthetic source title</a> — Synthetic Outlet · 2024-06-30T12:00:00+00:00</li></ol></details>'
    html_preservation(BeautifulSoup(html_text, 'html.parser'), spec, evidence, '2024-07-01')
    rejected('html_reordered_paragraphs', lambda: html_preservation(BeautifulSoup(html_text.replace(nodes[0] + nodes[1], nodes[1] + nodes[0]), 'html.parser'), spec, evidence, '2024-07-01'))
    rejected('html_wrong_source_href', lambda: html_preservation(BeautifulSoup(html_text.replace('https://example.org/source', 'https://example.org/changed', 1), 'html.parser'), spec, evidence, '2024-07-01'))
    rejected('html_ledger_metadata_deleted', lambda: html_preservation(BeautifulSoup(html_text.replace(' — Synthetic Outlet', ''), 'html.parser'), spec, evidence, '2024-07-01'))
    check(own_evidence(spec, {'items': list(evidence.values())}, [], '2024-07-01') == evidence, 'Own-feed positive fixture')
    changed = json.loads(json.dumps(evidence)); changed['n0001']['url'] += '/changed'
    rejected('exact_own_feed_record_metadata', lambda: validate_evidence(changed, spec, {'items': list(evidence.values())}, [], '2024-07-01'))
    with tempfile.TemporaryDirectory(prefix='artifact_negative_', dir=ROOT / 'work') as temporary:
        root = Path(temporary)
        for relative in ['audit_work/proof.json', 'audit_work/.private/proof.json', 'html/2024-07-01.html', 'audit/news_physical_requests.jsonl']:
            path = root / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('{}')
        with patch.object(inventory, 'ROOT', root), patch.dict(globals(), ROOT=root):
            inventory.safe_path('audit_work/proof.json')
            inventory.safe_path('audit/news_physical_requests.jsonl')
            rejected('replay_hidden_parent_existing_file', lambda: inventory.safe_path('audit_work/.private/proof.json'))
            rejected('local_hidden_parent_existing_file', lambda: local_member('audit_work/.private/proof.json'))
            rejected('native_wrong_exact_kind_path', lambda: local_member('html/2024-07-01.html', native_path('2024-07-01', 'pdf')))
            rejected('collection_wrong_exact_path', lambda: local_member('html/2024-07-01.html', 'collection/2024-07.html'))
    for relative in ['audit_work/.private/proof.json', '../outside.json', '/outside.json', 'audit_work//proof.json']:
        check(not safe_member(relative), 'Unsafe ZIP path accepted: ' + relative)
        results.append({'case': 'zip_path_' + relative, 'result': 'rejected_as_required'})
    for date in ['../2024-07-01', '2024-08-01', '2024-07-06', '20240701']:
        with patch('builtins.open', side_effect=AssertionError('Invalid date tried to read a file')):
            rejected('renderer_invalid_date_before_read_' + date, lambda: modules['render'].render(date))
    rejected('partial_collection_scope', lambda: builder.collection(DATES[:1]))
    files = {'audit/source_freeze.json': b'{"synthetic_freeze":true}', 'cache/news/fixture.json.gz': b'synthetic response'}
    source = {'passed': True, 'errors': [], 'dates': [], 'card_sha256': {}, 'source_freeze_sha256': sha(files['audit/source_freeze.json'])}
    market = {'passed': True, 'errors': [], 'dates': DATES, 'card_sha256': {}, 'source_freeze_sha256': source['source_freeze_sha256']}
    for date in DATES:
        feed = f'feeds/{date}.json.gz'; card = f'cards/{date}.json';files[feed] = b'synthetic feed';files[card] = b'synthetic card'
        source['dates'].append({'date': date, 'feed_sha256': sha(files[feed])})
        source['card_sha256'][date] = market['card_sha256'][date] = sha(files[card])
    # Current-schema, internally bound synthetic source package.
    files.update({'tools/fetch_news.py': b'# synthetic tool', 'AUTHORING.md': b'synthetic contract',
                  'BRIEF.md': b'synthetic brief', 'audit_work/review_sources.py': b'# synthetic reviewer',
                  'audit_work/independent_guard_policy.py': b'# synthetic guard',
                  'audit/news_query_plan.json': b'{"synthetic_plan":true}', 'audit/news_coverage.json': b'{}',
                  'work/source_candidates/comparison_manifest.json': b'{}', 'audit_work/news_semantic_review.json': b'{}',
                  'newest_lambda_function.py': b'# synthetic newest source'})
    tool_digest = sha(files['tools/fetch_news.py'])
    files['audit_work/news_policy_lock.json'] = json.dumps({'files': {'tools/fetch_news.py': tool_digest}}).encode()
    raw = b'<rss><channel><title>Synthetic physical body</title></channel></rss>'
    compressed = gzip.compress(raw, mtime=0)
    attempt_path = 'cache/rss_raw/attempts/synthetic.1.xml.gz'; canonical_path = 'cache/rss_raw/synthetic.xml.gz'
    files[attempt_path] = files[canonical_path] = compressed
    ledger_row = {'signature': 'synthetic', 'attempt': 1, 'status': 'fetched', 'raw_response_path': attempt_path,
                  'raw_compressed_sha256': sha(compressed), 'raw_sha256': sha(raw)}
    files['audit/news_physical_requests.jsonl'] = (json.dumps(ledger_row) + '\n').encode()
    physical_row = {'signature': 'synthetic', 'physical_attempts': 1, 'parsed_cache_path': 'cache/news/fixture.json.gz',
                    'parsed_cache_sha256': sha(files['cache/news/fixture.json.gz']), 'raw_xml_path': canonical_path,
                    'raw_xml_compressed_sha256': sha(compressed), 'raw_xml_uncompressed_sha256': sha(raw)}
    query_digest = sha(files['audit/news_query_plan.json'])
    files['audit_work/physical_source_inventory.json'] = json.dumps({'query_plan_sha256': query_digest, 'files': [physical_row]}).encode()
    freeze = {'query_plan_sha256': query_digest, 'coverage_sha256': sha(files['audit/news_coverage.json']),
              'candidate_manifest': 'work/source_candidates/comparison_manifest.json',
              'candidate_manifest_sha256': sha(files['work/source_candidates/comparison_manifest.json']),
              'semantic_review_sha256': sha(files['audit_work/news_semantic_review.json']),
              'physical_request_ledger_sha256': sha(files['audit/news_physical_requests.jsonl'])}
    files['audit/source_freeze.json'] = json.dumps(freeze).encode()
    source.update(source_freeze_sha256=sha(files['audit/source_freeze.json']), input_bindings={'audit/news_query_plan.json': query_digest},
                  tool_sha256={'fetch_news.py': tool_digest}, contract_sha256={'AUTHORING.md': sha(files['AUTHORING.md']), 'BRIEF.md': sha(files['BRIEF.md'])},
                  reviewer_dependency_sha256={'independent_guard_policy.py': sha(files['audit_work/independent_guard_policy.py'])},
                  reviewer_tool_sha256=sha(files['audit_work/review_sources.py']), ledger_sha256=sha(files['audit/news_physical_requests.jsonl']),
                  physical_source_inventory_sha256=sha(files['audit_work/physical_source_inventory.json']), query_plan_sha256=query_digest,
                  physical_requests=1, physical_attempts=1, received_attempt_bodies=1)
    market['source_freeze_sha256'] = source['source_freeze_sha256']
    files['audit/independent_market_review.json'] = json.dumps(market).encode()
    source['independent_market_review_sha256'] = sha(files['audit/independent_market_review.json'])
    files['code_provenance.json'] = json.dumps({'source_sha256': sha(files['newest_lambda_function.py'])}).encode()
    files['checks/code_discovery.json'] = files['code_provenance.json']
    files['audit/independent_source_review.json'] = json.dumps(source).encode()
    files['audit/independent_market_review.json'] = json.dumps(market).encode()
    replay = {'status': 'frozen_inputs_hash_bound', 'report_month': '2024-07', 'dates': DATES,
              'source_acceptance_sha256': sha(files['audit/independent_source_review.json']),
              'market_acceptance_sha256': sha(files['audit/independent_market_review.json']),
              'file_count': 1, 'files': [{'path': 'cache/news/fixture.json.gz', 'sha256': sha(files['cache/news/fixture.json.gz']), 'bytes': len(files['cache/news/fixture.json.gz'])}]}
    files['audit/news_replay_inventory.json'] = json.dumps(replay).encode()
    class Archive:
        def __init__(self, values): self.values = values
        def namelist(self): return list(self.values)
        def read(self, name): return self.values[name]
    replay_archive(Archive(files))
    tampered = dict(files);bad = dict(replay);bad['source_acceptance_sha256'] = '0' * 64;tampered['audit/news_replay_inventory.json'] = json.dumps(bad).encode()
    rejected('replay_acceptance_digest_changed', lambda: replay_archive(Archive(tampered)))
    tampered_row = dict(files);tampered_row['cache/news/fixture.json.gz'] += b'changed'
    rejected('replay_raw_input_bytes_changed', lambda: replay_archive(Archive(tampered_row)))
    tampered_feed = dict(files);tampered_feed['feeds/2024-07-01.json.gz'] += b'changed'
    rejected('source_acceptance_feed_changed', lambda: replay_archive(Archive(tampered_feed)))
    tampered_card = dict(files);tampered_card['cards/2024-07-01.json'] += b'changed'
    rejected('source_acceptance_card_changed', lambda: replay_archive(Archive(tampered_card)))
    for name in ['AUTHORING.md', 'tools/fetch_news.py', 'audit_work/independent_guard_policy.py',
                 'audit/news_query_plan.json', 'audit/news_physical_requests.jsonl',
                 attempt_path, canonical_path, 'newest_lambda_function.py']:
        changed_dependency = dict(files); changed_dependency[name] += b'changed'
        rejected('current_source_dependency_changed_' + name,
                 lambda changed_dependency=changed_dependency: current_source_dependencies(Archive(changed_dependency), source, freeze))
    missing_binding = dict(source); missing_binding.pop('input_bindings')
    rejected('current_source_input_bindings_missing', lambda: current_source_dependencies(Archive(files), missing_binding, freeze))
    missing_attempt = dict(files); missing_attempt.pop(attempt_path)
    rejected('current_source_physical_attempt_body_missing', lambda: current_source_dependencies(Archive(missing_attempt), source, freeze))
    retail_module = modules['build_retail_page']
    retail_spec = {'date': '2024-07-01', 'retail_intro': 'Synthetic retail introduction. [[n0001]]',
                   'retail': [{'title': f'Synthetic {i} / SYN — fixture hook',
                               'parts': [['Why Retail Is Here', f'Synthetic trade {i} risk [100]. [[n0001]]'],
                                         ['Where It Breaks', 'Now here is a boundary.']]} for i in range(4)]}
    retail_feed = {'items': list(evidence.values())}
    day_html = '<section class="day" id="2024-07-01"><header class="dayhead"><p class="intro">' + retail_module.cite_html(retail_spec['retail_intro'], evidence) + '</p></header>'
    day_html += ''.join(retail_module.trade_card(item, evidence, lead=(i == 0)) for i, item in enumerate(retail_spec['retail']))
    day_html += retail_module.source_ledger(retail_spec, evidence) + '</section>'
    def retail_check(value):
        return monthly_retail_day(BeautifulSoup(value, 'html.parser').select_one('section.day'), retail_spec, retail_feed, '2024-07-01')
    retail_check(day_html)
    rejected('monthly_retail_introduction_changed', lambda: retail_check(day_html.replace('Synthetic retail introduction.', 'Changed introduction.')))
    rejected('monthly_retail_label_changed', lambda: retail_check(day_html.replace('Why Retail Is Here', 'Changed label', 1)))
    rejected('monthly_retail_chip_href_changed', lambda: retail_check(day_html.replace('https://example.org/source', 'https://example.org/changed', 1)))
    rejected('monthly_retail_dated_ledger_removed', lambda: retail_check(day_html[:day_html.index('<details class="sources">')] + '</section>'))
    rejected('monthly_retail_ledger_timestamp_changed', lambda: retail_check(day_html.replace('2024-06-30 12:00:00+00:00', '2024-06-29 12:00:00+00:00')))
    rejected('monthly_retail_bracketed_number_deleted', lambda: retail_check(day_html.replace('risk [100]', 'risk', 1)))
    return results

def static_review():
    hashes = {}
    modules = {}
    for name in ['render', 'build_artifacts', 'build_retail_page', 'build_source_inventory']:
        path = ROOT / 'tools' / (name + '.py')
        source = path.read_text()
        compile(source, str(path), 'exec')
        check(not re.search(r'2024-08|August2024|August_2024|August 2024|withdrawn_aug', source),
              'Inherited prior-month hardcode in ' + name)
        info = importlib.util.spec_from_file_location('july_artifact_static_' + name, path)
        module = importlib.util.module_from_spec(info)
        info.loader.exec_module(module)
        modules[name] = module
        hashes[name + '.py'] = sha(path.read_bytes())
        if hasattr(module, 'DATES'):
            check(module.DATES == DATES, 'Wrong July dates in ' + name)
    check(len(DATES) == 23 and DATES[0] == '2024-07-01' and DATES[-1] == '2024-07-31', 'Wrong 23-date scope')
    check('2024-07-04' in DATES and '2024-07-05' in DATES, 'Exchange holiday weekday omitted')
    builder = modules['build_artifacts']
    check(builder.ZIP_NAME == 'July_2024_Weekday_Reports.zip', 'Wrong report ZIP name')
    check(builder.SOURCE_NAME == 'July_2024_Frozen_Sources.zip', 'Wrong source ZIP name')
    check(23 * 3 + 5 == 74 and 23 * 3 + 3 == 72, 'Wrong delivery counts')
    check('max-width:1280px' in modules['render'].BODY, 'Wide layout lost')
    check('retail-lead' in modules['render'].CSS and '@media print' in modules['render'].CSS, 'Retail or print styling missing')
    method = builder.methodology(DATES)
    check('July 2024' in method and '23 weekday editions' in method, 'Wrong methodology month/count')
    for unsupported in ['five editions', 'August regional holidays', 'MSTR', 'Nebius', 'vendor gaps']:
        check(unsupported not in method, 'Inherited unsupported methodology: ' + unsupported)
    # Pure in-memory escaping/Unicode checks; no report input or artifact build.
    doc = modules['render'].Doc({'n0001': {'title': 'Łódź — 3.2% & <test>', 'url': 'https://example.org/'}})
    escaped = doc.text('Łódź −3.2% & <tag> [[n0001]]')
    check('Łódź −3.2% &amp; &lt;tag&gt;' in escaped and 'source-cite' in escaped, 'Unicode/escaping regression')
    check('"hook"' not in modules['render'].hook('Name / TICKER — hook', 14, '#123'), 'Retail hook altered by quotation marks')
    check(normal('Łódź −3.2% [100]') == normal('Łódź\n−3.2% [100]'), 'Layout whitespace normalization regression')
    token_sample = 'On 2024-06-28T07:00:00+00:00, total-return-tracker text remains.'
    token_html = BeautifulSoup(modules['render'].esc(token_sample), 'html.parser')
    check(token_html.get_text() == token_sample and len(token_html.select('.verbatim-token')) == 2,
          'Verbatim date/timestamp or compound rendering changed source text')
    check('font-variant-ligatures:none' in modules['render'].CSS and '.part-label' in modules['render'].CSS,
          'PDF label glyph/ligature rendering protection missing')
    fixtures = negative_fixtures(modules)
    hashes['audit_work/review_final_artifacts.py'] = sha(Path(__file__).read_bytes())
    return {'status': 'static_checks_passed', 'dates': DATES, 'tool_sha256': hashes,
            'artifact_targets_expected': 74, 'report_zip_members_expected': 72,
            'runtime_artifacts_reviewed': False, 'negative_fixtures': fixtures, 'negative_fixture_count': len(fixtures),
            'superseded_initial_receipt': 'audit/review_history/artifact_tool_review_initial_superseded.json',
            'scope': 'Generic July date/naming/shape/layout/escaping and code-compile checks only. No report data read, built, published or factually accepted.'}


def safe_member(name):
    if not isinstance(name, str) or not name:
        return False
    path = PurePosixPath(name)
    return (not path.is_absolute() and '..' not in path.parts and '\\' not in name
            and str(path) == name and not any(part.startswith('.') for part in path.parts)
            and not set(path.parts) & {'.git', '.aws', '.ssh', '__pycache__', 'node_modules',
                                       'repo', 'repository', 'secrets', 'credentials'})


def local_member(name, expected=None):
    check(safe_member(name) and (expected is None or name == expected), 'Unexpected/unsafe local path: ' + str(name))
    path = ROOT / name
    check(path.resolve().is_relative_to(ROOT) and path.is_file() and not path.is_symlink()
          and not any(parent.is_symlink() for parent in path.parents if parent.is_relative_to(ROOT)), 'Unsafe/missing local member: ' + name)
    return path


def replay_member_name(name):
    path = PurePosixPath(name)
    roots = ('cache/news/', 'cache/rss_raw/', 'audit/news_provenance/', 'audit/market_raw/',
             'work/source_candidates/', 'work/unreviewed_feeds/', 'work/acquisition_feeds/',
             'exclusions/', 'source_supplements/', 'audit/source_amendments/', 'audit/review_history/', 'audit_work/')
    return safe_member(name) and (name.startswith(roots)
        or (name.startswith('audit/') and len(path.parts) == 2 and path.suffix in {'.json', '.jsonl', '.csv'})
        or name in {'newest_lambda_function.py', 'code_provenance.json', 'checks/code_discovery.json'})


def source_member_name(name):
    return replay_member_name(name) or (safe_member(name) and
        (name.startswith(('tools/', 'data/', 'specs/', 'cards/', 'feeds/', 'notes/',
                          'nonretail_drafts/', 'retail_drafts/', 'checks/', 'reference/'))
         or name in {'AUTHORING.md', 'BRIEF.md', 'README.md'}))


def native_path(date, kind):
    check(date in DATES and kind in {'html', 'pdf', 'json'}, 'Unexpected native artifact')
    return {'html': f'html/{date}.html', 'pdf': f'pdf/{date}_Market_Intelligence.pdf',
            'json': f'json/{date}_Market_Intelligence.json'}[kind]


def current_source_dependencies(z, source, freeze):
    """Verify actual current producer bindings and every received request body."""
    names = set(z.namelist()); checks = 0
    def digest(name, expected):
        nonlocal checks
        check(source_member_name(name) and name in names, 'Missing/unsafe source dependency: ' + name)
        check(isinstance(expected, str) and len(expected) == 64 and sha(z.read(name)) == expected, 'Changed source dependency: ' + name)
        checks += 1
    bindings = source.get('input_bindings')
    check(isinstance(bindings, dict) and bool(bindings), 'Current source input_bindings required')
    for name, expected in bindings.items(): digest(name, expected)
    for field, prefix in [('tool_sha256', 'tools/'), ('contract_sha256', ''), ('reviewer_dependency_sha256', 'audit_work/')]:
        values = source.get(field)
        check(isinstance(values, dict) and bool(values), 'Missing current source dependency map: ' + field)
        for name, expected in values.items():
            check('/' not in name and safe_member(name), 'Unexpected source dependency name: ' + name)
            digest(prefix + name, expected)
    digest('audit_work/review_sources.py', source.get('reviewer_tool_sha256'))
    digest('audit/news_physical_requests.jsonl', source.get('ledger_sha256'))
    digest('audit_work/physical_source_inventory.json', source.get('physical_source_inventory_sha256'))
    digest('audit/news_query_plan.json', source.get('query_plan_sha256'))
    digest('audit/independent_market_review.json', source.get('independent_market_review_sha256'))
    if source.get('prior_physical_review_sha256'):
        digest('audit/independent_physical_source_review.json', source['prior_physical_review_sha256'])
    for field, name in [('query_plan_sha256', 'audit/news_query_plan.json'), ('coverage_sha256', 'audit/news_coverage.json'),
                        ('candidate_manifest_sha256', freeze.get('candidate_manifest', '')),
                        ('semantic_review_sha256', 'audit_work/news_semantic_review.json'),
                        ('physical_request_ledger_sha256', 'audit/news_physical_requests.jsonl')]:
        digest(name, freeze.get(field))
    policy = json.loads(z.read('audit_work/news_policy_lock.json'))
    check(isinstance(policy.get('files'), dict) and bool(policy['files']), 'Missing source policy dependency map')
    for name, expected in policy['files'].items(): digest(name, expected)
    ledger = [json.loads(line) for line in z.read('audit/news_physical_requests.jsonl').decode().splitlines() if line.strip()]
    check(len(ledger) == source.get('physical_attempts'), 'Physical request ledger count changed')
    attempts = set(); bodies = set(); per_signature = {}
    for row in ledger:
        identity = (row['signature'], row['attempt'])
        check(identity not in attempts, 'Duplicate physical request attempt')
        attempts.add(identity); per_signature[row['signature']] = per_signature.get(row['signature'], 0) + 1
        path = row.get('raw_response_path')
        if path:
            check(path.startswith('cache/rss_raw/attempts/') and path not in bodies, 'Reused/non-immutable attempt body')
            digest(path, row.get('raw_compressed_sha256'))
            raw = gzip.decompress(z.read(path)); check(sha(raw) == row.get('raw_sha256'), 'Physical attempt XML bytes changed: ' + path)
            bodies.add(path)
        if row.get('status') == 'fetched': check(bool(path), 'Fetched physical request lost body')
    check(len(bodies) == source.get('received_attempt_bodies'), 'Received body count changed')
    check({name for name in names if name.startswith('cache/rss_raw/attempts/')} == bodies, 'Attempt-body archive differs from physical ledger')
    physical = json.loads(z.read('audit_work/physical_source_inventory.json'))
    check(physical.get('query_plan_sha256') == source['query_plan_sha256'], 'Physical inventory plan changed')
    rows = physical.get('files', [])
    check(len(rows) == source.get('physical_requests') and len({row['signature'] for row in rows}) == len(rows), 'Physical canonical inventory count changed')
    for row in rows:
        check(per_signature.get(row['signature']) == row['physical_attempts'], 'Per-query attempt count changed')
        digest(row['parsed_cache_path'], row['parsed_cache_sha256'])
        digest(row['raw_xml_path'], row['raw_xml_compressed_sha256'])
        check(sha(gzip.decompress(z.read(row['raw_xml_path']))) == row['raw_xml_uncompressed_sha256'], 'Canonical XML bytes changed')
    # Discovery provenance describes the upstream toolkit hashes separately from
    # adapted current tools. Only the selected newest Lambda source is compared.
    provenance = json.loads(z.read('code_provenance.json'))
    discovery = json.loads(z.read('checks/code_discovery.json'))
    digest('newest_lambda_function.py', provenance.get('source_sha256'))
    check(discovery.get('source_sha256') == provenance['source_sha256'], 'Newest-code discovery/source provenance mismatch')
    return {'source_input_bindings': len(bindings), 'source_dependency_hash_checks': checks,
            'physical_attempts': len(ledger), 'received_attempt_bodies': len(bodies),
            'canonical_physical_requests': len(rows), 'current_source_schema_checked': True}

def replay_archive(z):
    names = set(z.namelist())
    def record(name):
        check(name in names, 'Missing source acceptance/replay member: ' + name)
        return json.loads(z.read(name))
    source = record('audit/independent_source_review.json')
    market = record('audit/independent_market_review.json')
    replay = record('audit/news_replay_inventory.json')
    check(source.get('passed') is True and market.get('passed') is True
          and not source.get('errors') and not market.get('errors')
          and [row.get('date') for row in source.get('dates', [])] == DATES
          and market.get('dates') == DATES, 'Source ZIP lacks accepted 23-date inputs')
    check(replay.get('report_month') == '2024-07' and replay.get('dates') == DATES
          and replay.get('status') == 'frozen_inputs_hash_bound', 'Wrong replay inventory scope')
    for field, name in [('source_acceptance_sha256', 'independent_source_review.json'),
                        ('market_acceptance_sha256', 'independent_market_review.json')]:
        check(replay.get(field) == sha(z.read('audit/' + name)), 'Replay acceptance hash changed: ' + name)
    freeze = 'audit/source_freeze.json'
    check(freeze in names and source.get('source_freeze_sha256') == sha(z.read(freeze))
          and market.get('source_freeze_sha256') == sha(z.read(freeze)), 'Source freeze binding changed')
    for row in source['dates']:
        date = row['date'];feed = f'feeds/{date}.json.gz';card = f'cards/{date}.json'
        check(feed in names and card in names and row.get('feed_sha256') == sha(z.read(feed)), 'Accepted feed changed: ' + date)
        check(all(review.get('card_sha256', {}).get(date) == sha(z.read(card)) for review in (source, market)), 'Accepted card changed: ' + date)
    source_dependency_result = current_source_dependencies(z, source, json.loads(z.read(freeze)))
    rows = replay.get('files', [])
    check(bool(rows) and replay.get('file_count') == len(rows) and len({row['path'] for row in rows}) == len(rows), 'Empty/duplicate/incomplete replay rows')
    for row in rows:
        name = row['path']
        check(replay_member_name(name) and name in names, 'Unsafe/missing replay member: ' + name)
        blob = z.read(name)
        check(len(blob) == row.get('bytes') and sha(blob) == row.get('sha256'), 'Replay input changed: ' + name)
    return {'replay_inputs_verified': len(rows), **source_dependency_result}

def final_review():
    result = static_review()
    manifest = load(ROOT / 'checks/artifact_manifest.json')
    check(manifest.get('dates') == DATES and manifest.get('complete_month') is True, 'Incomplete month')
    check([r['date'] for r in manifest['reports']] == DATES, 'Missing/duplicate report rows')
    check(set(manifest['collection']) == COLLECTION and manifest.get('artifact_targets') == 74, 'Wrong collection/target count')
    rows = []
    expected_zip = {'index.html', 'methodology.txt', 'What_Retail_Is_Playing_2024-07.html'}
    for row in manifest['reports']:
        date = row['date']
        check(set(row['files']) == {'html', 'pdf', 'json'}, date + ' missing native format')
        spec_path = ROOT / 'specs' / (date + '.json')
        check(sha(spec_path.read_bytes()) == row['spec_sha256'], date + ' stale artifact input')
        spec = load(spec_path)
        for kind, file in row['files'].items():
            path = local_member(file['path'], native_path(date, kind))
            blob = path.read_bytes()
            check(sha(blob) == file['sha256'] and len(blob) == file['bytes'], date + ' changed ' + kind)
            expected_zip.add(file['path'])
        payload = load(ROOT / row['files']['json']['path'])
        check(payload['spec'] == spec and payload['report_date'] == date, date + ' JSON changed prose/date')
        check(payload.get('news_cutoff_utc') == date + 'T00:00:00Z', date + ' JSON cutoff changed')
        cited = set(re.findall(r'\[\[(n\d{4,6})\]\]', json.dumps(spec, ensure_ascii=False)))
        check(set(payload['evidence']) == cited, date + ' wrong JSON evidence membership')
        feed = json.loads(gzip.decompress(local_member(f'feeds/{date}.json.gz').read_bytes()))
        exceptions_path = ROOT / 'audit/canonical_source_exceptions.json'
        exceptions = load(exceptions_path).get('exceptions', []) if exceptions_path.exists() else []
        evidence = validate_evidence(payload['evidence'], spec, feed, exceptions, date)
        page = BeautifulSoup((ROOT / row['files']['html']['path']).read_text(), 'html.parser')
        check([h['id'] for h in page.select('h2[id]')] == SECTIONS, date + ' wrong nine-section order')
        check(not page.select('.snapshot,.metric,.momentum,canvas,svg'), date + ' dashboard/chart remains')
        check(len(page.select('.retail-lead')) == 1, date + ' missing prominent retail lead')
        check(not re.search(r'\[\[|\]\]', page.get_text()), date + ' unresolved citation')
        count = html_preservation(page, spec, evidence, date)
        pdf = PdfReader(local_member(row['files']['pdf']['path'], native_path(date, 'pdf')))
        footer = re.compile(r'(?m)^' + re.escape(date) + r'\s*·\s*Market Intelligence Briefing\s*·\s*\d+\s*/\s*\d+\s*$')
        text = '\n'.join(footer.sub('', p.extract_text() or '') for p in pdf.pages)
        check(pdf_preservation(date, text, spec, evidence) == count, date + ' PDF paragraph count differs')
        rows.append({'date': date, 'paragraphs_preserved': count, 'ledger_headlines_preserved': len(payload['evidence']),
                     'pdf_pages': len(pdf.pages), 'spec_sha256': row['spec_sha256']})
    for name, file in manifest['collection'].items():
        blob = local_member(file['path'], 'collection/' + name).read_bytes()
        check(sha(blob) == file['sha256'] and len(blob) == file['bytes'], 'Changed collection ' + name)
    report_zip = ROOT / 'collection/July_2024_Weekday_Reports.zip'
    with zipfile.ZipFile(report_zip) as z:
        check(z.testzip() is None, 'Report ZIP CRC error')
        check(set(z.namelist()) == expected_zip and len(z.namelist()) == 72, 'Wrong report ZIP members')
        for name in z.namelist():
            check(safe_member(name), 'Unsafe report ZIP member')
            if name != 'index.html':
                local = ROOT / (name if name.startswith(('html/', 'pdf/', 'json/')) else 'collection/' + name)
                check(z.read(name) == local.read_bytes(), 'Report ZIP bytes differ: ' + name)
        offline = BeautifulSoup(z.read('index.html'), 'html.parser')
        check([a['href'] for a in offline.select('a.day')] == ['html/' + d + '.html' for d in DATES], 'Wrong offline links')
    source_zip = ROOT / 'collection/July_2024_Frozen_Sources.zip'
    with zipfile.ZipFile(source_zip) as z:
        check(z.testzip() is None, 'Source ZIP CRC error')
        inventory = json.loads(z.read('source_inventory.json'))
        check(len({r['path'] for r in inventory}) == len(inventory), 'Duplicate source inventory')
        check(set(z.namelist()) == {r['path'] for r in inventory} | {'source_inventory.json'}, 'Source ZIP inventory differs')
        check(len(z.namelist()) == len(inventory) + 1, 'Duplicate source ZIP member')
        for file in inventory:
            name = file['path']
            check(source_member_name(name), 'Unsafe source ZIP path: ' + name)
            check(not any(m != '2024-07' for m in re.findall(r'20\d{2}-\d{2}(?=-\d{2}(?:\D|$))', name)), 'Other report-month input: ' + name)
            check(not any(t in Path(name).name.lower() for t in ('secret', 'credential', '.pem', '.key')), 'Sensitive filename')
            blob = z.read(name)
            check(len(blob) == file['bytes'] and sha(blob) == file['sha256'], 'Source ZIP hash mismatch: ' + name)
            check(blob == local_member(name).read_bytes(), 'Source ZIP differs from retained input: ' + name)
        source_members = {r['path'] for r in inventory}
        for d in DATES:
            for prefix, suffix in [('feeds/', '.json.gz'), ('cards/', '.json'), ('specs/', '.json'), ('nonretail_drafts/', '.json'), ('retail_drafts/', '.json')]:
                check(prefix + d + suffix in source_members, 'Source ZIP missing current component ' + prefix + d)
        for prefix in ['cache/news/', 'cache/rss_raw/', 'audit/news_provenance/', 'audit/market_raw/', 'exclusions/']:
            check(any(name.startswith(prefix) for name in source_members), 'Source ZIP missing replay family ' + prefix)
        replay_input_count = replay_archive(z)
        market = load(ROOT / 'audit/independent_market_review.json')
        for name, digest in market.get('input_sha256', {}).items():
            check(name in source_members and sha(z.read(name)) == digest, 'Missing/changed independent market replay input: ' + name)
    collection = BeautifulSoup((ROOT / 'collection/2024-07.html').read_text(), 'html.parser')
    check([a['href'] for a in collection.select('a.day')] == ['archive/' + d + '.html' for d in DATES], 'Wrong online links')
    retail_path = ROOT / 'collection/What_Retail_Is_Playing_2024-07.html'
    retail = BeautifulSoup(retail_path.read_text(), 'html.parser')
    check([s['id'] for s in retail.select('section.day')] == DATES, 'Wrong retail chronology')
    monthly_retail_checks = []
    for date, section in zip(DATES, retail.select('section.day')):
        spec = load(ROOT / 'specs' / (date + '.json'))
        feed = json.loads(gzip.decompress(local_member(f'feeds/{date}.json.gz').read_bytes()))
        monthly_retail_checks.append(monthly_retail_day(section, spec, feed, date))
    layouts = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path='/usr/bin/chromium', args=['--no-sandbox'])
        page = browser.new_page()
        targets = [(date, ROOT / 'html' / (date + '.html')) for date in DATES]
        targets += [('collection', ROOT / 'collection/2024-07.html'), ('retail_collection', retail_path)]
        for name, path in targets:
            for width, height in [(1440, 1000), (390, 844)]:
                page.set_viewport_size({'width': width, 'height': height})
                page.set_content(path.read_text(), wait_until='load')
                measurement = page.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth})')
                check(measurement['scroll'] <= width, name + ' horizontal overflow at ' + str(width))
                layouts.append({'artifact': name, 'viewport_width': width, **measurement})
        browser.close()
    result.update(status='accepted', runtime_artifacts_reviewed=True, fatal_or_major_remaining=0,
                  reviewed_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                  artifact_manifest_sha256=sha((ROOT / 'checks/artifact_manifest.json').read_bytes()),
                  reports=rows, monthly_retail_checks=monthly_retail_checks, layouts=layouts, report_zip_members=72,
                  frozen_source_members=len(source_members), source_replay_verification=replay_input_count,
                  limits=['Technical preservation, Unicode, chronology, local bytes and layout review only; editorial/source-claim acceptance is separate.',
                          'No publication or public-domain routing/network verification performed; root verifies remote ZIP/native content separately.'])
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--static', action='store_true')
    args = parser.parse_args()
    try:
        result = static_review() if args.static else final_review()
    except Exception as error:
        result = {'status': 'failed', 'error': str(error), 'fatal_or_major_remaining': 1}
        save(ROOT / 'checks' / ('artifact_tool_review.json' if args.static else 'final_artifact_review.json'), result)
        raise
    save(ROOT / 'checks' / ('artifact_tool_review.json' if args.static else 'final_artifact_review.json'), result)
    print(json.dumps({key: result[key] for key in ['status', 'runtime_artifacts_reviewed']}, indent=2))


if __name__ == '__main__':
    main()
