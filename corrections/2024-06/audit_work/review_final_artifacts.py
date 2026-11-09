"""Independent report-content preservation and artifact checks; never publish.

--static inspects only generic pipeline code/constants, without reading report
facts or building artifacts. The default reviews existing final June artifacts,
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
DATES = [dt.date(2024, 6, day).isoformat() for day in range(3, 29)
         if dt.date(2024, 6, day).weekday() < 5]
COLLECTION = {'2024-06.html', 'methodology.txt', 'June_2024_Weekday_Reports.zip',
              'June_2024_Frozen_Sources.zip', 'What_Retail_Is_Playing_2024-06.html'}
SECTIONS = ['geo', 'sectors', 'earnings', 'underowned', 'crypto', 'flows',
            'anticipatory', 'catalysts', 'retail']
SOURCE_PHASE_AMENDMENT = 'audit/source_phase_binding_amendment.json'
SOURCE_PHASE_AMENDMENT_SHA256 = 'bc3e4f27dda483666be7f1e9e622a5d552dd613645d893e45415cff77ec68c37'


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
    spec = {'date': '2024-06-03', 'geo': [], 'sectors': [],
            'earnings_pattern': {'parts': [['First', 'Risk [100] remains. [[n0001]]'],
                                           ['Second', 'Now here is the limit.'],
                                           ['Again', 'Repeat this occurrence.'], ['Again', 'Repeat this occurrence.']]},
            'underowned': [], 'crypto': {'parts': []}, 'flows': {'parts': []},
            'anticipatory': [], 'catalysts': [], 'retail_intro': 'Synthetic crowd introduction.', 'retail': []}
    evidence = {'n0001': {'id': 'n0001', 'title': 'Synthetic source title', 'src': 'Synthetic Outlet',
                         'published_at': '2024-06-02T12:00:00+00:00', 'url': 'https://example.org/source'}}
    order = expected_order(spec)
    entries = [(label + ': ' if label else '') + displayed(value, order) for _, label, value in paragraphs(spec)]
    ledger = 'Dated evidence · 1 sources Synthetic source title — Synthetic Outlet · 2024-06-02T12:00:00+00:00'
    good = ' '.join(entries) + ' ' + ledger
    class Page:
        def __init__(self, value): self.value = value
        def extract_text(self): return self.value
    class PDF:
        def __init__(self, value): self.pages = [Page(value)]
    for name, checker in [('builder', lambda value: builder.check_pdf_prose('2024-06-03', PDF(value), spec, evidence)),
                          ('reviewer', lambda value: pdf_preservation('2024-06-03', value, spec, evidence))]:
        checker(good)
        rejected(name + '_literal_bracket_deleted', lambda: checker(good.replace('[100]', '')))
        rejected(name + '_word_boundary_corrupted', lambda: checker(good.replace('Now here', 'Nowhere')))
        reversed_body = ' '.join([entries[1], entries[0], *entries[2:]]) + ' ' + ledger
        rejected(name + '_paragraphs_reordered', lambda: checker(reversed_body))
        rejected(name + '_repeated_occurrence_deleted', lambda: checker(good.replace(entries[2] + ' ', '', 1)))
        rejected(name + '_ledger_outlet_deleted', lambda: checker(good.replace(' — Synthetic Outlet', '')))
        rejected(name + '_ledger_timestamp_deleted', lambda: checker(good.replace(' · 2024-06-02T12:00:00+00:00', '')))
        rejected(name + '_ledger_missing_body_title_present', lambda: checker(good.replace(ledger, 'Synthetic source title')))
    doc = modules['render'].Doc(evidence)
    nodes = []
    for _, label, value in paragraphs(spec):
        nodes.append(doc.parts([(label, value)])[0] if label is not None else '<p class="retail-intro">' + doc.text(value) + '</p>')
    html_text = ''.join(nodes) + '<details class="ledger"><ol><li data-source-id="n0001"><a href="https://example.org/source">Synthetic source title</a> — Synthetic Outlet · 2024-06-02T12:00:00+00:00</li></ol></details>'
    html_preservation(BeautifulSoup(html_text, 'html.parser'), spec, evidence, '2024-06-03')
    rejected('html_reordered_paragraphs', lambda: html_preservation(BeautifulSoup(html_text.replace(nodes[0] + nodes[1], nodes[1] + nodes[0]), 'html.parser'), spec, evidence, '2024-06-03'))
    rejected('html_wrong_source_href', lambda: html_preservation(BeautifulSoup(html_text.replace('https://example.org/source', 'https://example.org/changed', 1), 'html.parser'), spec, evidence, '2024-06-03'))
    rejected('html_ledger_metadata_deleted', lambda: html_preservation(BeautifulSoup(html_text.replace(' — Synthetic Outlet', ''), 'html.parser'), spec, evidence, '2024-06-03'))
    check(own_evidence(spec, {'items': list(evidence.values())}, [], '2024-06-03') == evidence, 'Own-feed positive fixture')
    changed = json.loads(json.dumps(evidence)); changed['n0001']['url'] += '/changed'
    rejected('exact_own_feed_record_metadata', lambda: validate_evidence(changed, spec, {'items': list(evidence.values())}, [], '2024-06-03'))
    with tempfile.TemporaryDirectory(prefix='artifact_negative_', dir=ROOT / 'work') as temporary:
        root = Path(temporary)
        for relative in ['audit_work/proof.json', 'audit_work/.private/proof.json', 'html/2024-06-03.html', 'audit/news_physical_requests.jsonl']:
            path = root / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('{}')
        with patch.object(inventory, 'ROOT', root), patch.dict(globals(), ROOT=root):
            inventory.safe_path('audit_work/proof.json')
            inventory.safe_path('audit/news_physical_requests.jsonl')
            rejected('replay_hidden_parent_existing_file', lambda: inventory.safe_path('audit_work/.private/proof.json'))
            rejected('local_hidden_parent_existing_file', lambda: local_member('audit_work/.private/proof.json'))
            rejected('native_wrong_exact_kind_path', lambda: local_member('html/2024-06-03.html', native_path('2024-06-03', 'pdf')))
            rejected('collection_wrong_exact_path', lambda: local_member('html/2024-06-03.html', 'collection/2024-06.html'))
    for relative in ['audit_work/.private/proof.json', '../outside.json', '/outside.json', 'audit_work//proof.json']:
        check(not safe_member(relative), 'Unsafe ZIP path accepted: ' + relative)
        results.append({'case': 'zip_path_' + relative, 'result': 'rejected_as_required'})
    for date in ['../2024-06-03', '2024-08-01', '2024-06-08', '20240603']:
        with patch('builtins.open', side_effect=AssertionError('Invalid date tried to read a file')):
            rejected('renderer_invalid_date_before_read_' + date, lambda: modules['render'].render(date))
    rejected('partial_collection_scope', lambda: builder.collection(DATES[:1]))
    files = {'audit/source_freeze.json': b'{"synthetic_freeze":true}', 'cache/news/fixture.json.gz': b'synthetic response'}
    source = {'passed': True, 'errors': [], 'dates': [], 'card_sha256': {}, 'source_freeze_sha256': sha(files['audit/source_freeze.json'])}
    market = {'passed': True, 'errors': [], 'dates': DATES, 'card_sha256': {}, 'source_freeze_sha256': source['source_freeze_sha256']}
    for date in DATES:
        feed = f'feeds/{date}.json.gz'; card = f'cards/{date}.json';files[feed] = b'synthetic feed';files[card] = b'synthetic card'
        raw = f'work/unreviewed_feeds/{date}.json.gz'; files[raw] = b'synthetic unreviewed feed'
        ready = f'audit/news_ready_{date}.json'
        files[ready] = json.dumps({'date': date, 'status': 'ready', 'ready_sha256': sha(files[feed]),
                                  'unreviewed_sha256': sha(files[raw]), 'input_items': 3, 'ready_items': 2,
                                  'excluded_items': 1, 'excluded': [{'id': 'n0002', 'guard': 'synthetic_only'}]}).encode()
        source['dates'].append({'date': date, 'feed_sha256': sha(files[feed]), 'raw_sha256': sha(files[raw]),
                                'ready_receipt_sha256': sha(files[ready]), 'raw_items': 3, 'ready_items': 2, 'excluded': 1})
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
    ledger_row = {'signature': 'synthetic', 'attempt': 1, 'request_url': 'https://example.org/synthetic-query',
                  'started_at_utc': '2000-01-01T00:00:00+00:00', 'finished_at_utc': '2000-01-01T00:00:01+00:00',
                  'status': 'fetched', 'raw_response_path': attempt_path,
                  'raw_compressed_sha256': sha(compressed), 'raw_sha256': sha(raw)}
    files['audit/news_physical_requests.jsonl'] = (json.dumps(ledger_row) + '\n').encode()
    files['cache/news/fixture.json.gz'] = gzip.compress(json.dumps({
        'signature': 'synthetic', 'request_url': ledger_row['request_url'], 'status': 'fetched',
        'response_format_verified': True, 'raw_response_path': canonical_path,
        'raw_sha256': sha(raw), 'raw_response_compressed_sha256': sha(compressed),
        'physical_attempts': [ledger_row]}).encode(), mtime=0)
    physical_row = {'signature': 'synthetic', 'physical_attempts': 1, 'parsed_cache_path': 'cache/news/fixture.json.gz',
                    'parsed_cache_sha256': sha(files['cache/news/fixture.json.gz']), 'raw_xml_path': canonical_path,
                    'raw_xml_compressed_sha256': sha(compressed), 'raw_xml_uncompressed_sha256': sha(raw)}
    query_digest = sha(files['audit/news_query_plan.json'])
    files['audit_work/physical_source_inventory.json'] = json.dumps({'query_plan_sha256': query_digest, 'files': [physical_row]}).encode()
    freeze = {'status': 'all_20_ready', 'dates': [{'date': date} for date in DATES],
              'query_plan_sha256': query_digest, 'coverage_sha256': sha(files['audit/news_coverage.json']),
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
    source['input_bindings'].update({f'audit/news_ready_{date}.json': sha(files[f'audit/news_ready_{date}.json']) for date in DATES})
    limitation_name = 'audit_work/acquisition_capture_limitation.json'
    files[limitation_name] = json.dumps({'status': 'disclosed_capture_limitation',
                                        'recorded_failed_attempts_missing_bodies': 0, 'affected_attempts': []}).encode()
    proof = {'status': 'physical_infrastructure_replay_passed', 'passed': True, 'errors': [],
             'authoring_acceptance': False, 'dates': DATES, 'physical_requests': 1, 'physical_attempts': 1,
             'received_attempt_bodies': 1, 'failed_attempts': 0, 'recorded_missing_response_bodies': 0,
             'discarded_error_body_limitations_sha256': sha(files[limitation_name]),
             'legacy_signature_attempt_number_collisions': [], 'unlogged_interrupted_attempts_maximum': 16,
             'unlogged_interrupted_attempts_actual_count': None, 'all_physical_network_attempts_complete': False,
             'attempt_starts_ledger_sha256': None, 'attempt_starts_instrumentation_used': False,
             'recorded_transport_bodies_complete_except_declared_58': True,
             'ledger_sha256': source['ledger_sha256'], 'query_plan_sha256': query_digest,
             'physical_source_inventory_sha256': source['physical_source_inventory_sha256'],
             'input_bindings': {name: sha(files[name]) for name in
                                ['audit/news_query_plan.json', 'audit/news_physical_requests.jsonl', limitation_name]}}
    files['audit/independent_physical_source_review.json'] = json.dumps(proof).encode()
    source.update({name: proof[name] for name in modules['build_source_inventory'].TRANSPORT_FIELDS})
    source['prior_physical_review_sha256'] = sha(files['audit/independent_physical_source_review.json'])
    market['source_freeze_sha256'] = source['source_freeze_sha256']
    files['audit/independent_market_review.json'] = json.dumps(market).encode()
    source['independent_market_review_sha256'] = sha(files['audit/independent_market_review.json'])
    files['code_provenance.json'] = json.dumps({'source_sha256': sha(files['newest_lambda_function.py'])}).encode()
    files['checks/code_discovery.json'] = files['code_provenance.json']
    files['audit/independent_source_review.json'] = json.dumps(source).encode()
    files['audit/independent_market_review.json'] = json.dumps(market).encode()
    replay = {'status': 'frozen_inputs_hash_bound', 'report_month': '2024-06', 'dates': DATES,
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
    tampered_feed = dict(files);tampered_feed['feeds/2024-06-03.json.gz'] += b'changed'
    rejected('source_acceptance_feed_changed', lambda: replay_archive(Archive(tampered_feed)))
    tampered_card = dict(files);tampered_card['cards/2024-06-03.json'] += b'changed'
    rejected('source_acceptance_card_changed', lambda: replay_archive(Archive(tampered_card)))
    for name in ['AUTHORING.md', 'tools/fetch_news.py', 'audit_work/independent_guard_policy.py',
                 'audit/news_ready_2024-06-03.json', 'audit/news_physical_requests.jsonl',
                 attempt_path, canonical_path, 'newest_lambda_function.py']:
        changed_dependency = dict(files); changed_dependency[name] += b'changed'
        rejected('current_source_dependency_changed_' + name,
                 lambda changed_dependency=changed_dependency: current_source_dependencies(Archive(changed_dependency), source, freeze))
    missing_binding = dict(source); missing_binding.pop('input_bindings')
    rejected('current_source_input_bindings_missing', lambda: current_source_dependencies(Archive(files), missing_binding, freeze))
    missing_attempt = dict(files); missing_attempt.pop(attempt_path)
    rejected('current_source_physical_attempt_body_missing', lambda: current_source_dependencies(Archive(missing_attempt), source, freeze))
    retail_module = modules['build_retail_page']
    retail_spec = {'date': '2024-06-03', 'retail_intro': 'Synthetic retail introduction. [[n0001]]',
                   'retail': [{'title': f'Synthetic {i} / SYN — fixture hook',
                               'parts': [['Why Retail Is Here', f'Synthetic trade {i} risk [100]. [[n0001]]'],
                                         ['Where It Breaks', 'Now here is a boundary.']]} for i in range(4)]}
    retail_feed = {'items': list(evidence.values())}
    day_html = '<section class="day" id="2024-06-03"><header class="dayhead"><p class="intro">' + retail_module.cite_html(retail_spec['retail_intro'], evidence) + '</p></header>'
    day_html += ''.join(retail_module.trade_card(item, evidence, lead=(i == 0)) for i, item in enumerate(retail_spec['retail']))
    day_html += retail_module.source_ledger(retail_spec, evidence) + '</section>'
    def retail_check(value):
        return monthly_retail_day(BeautifulSoup(value, 'html.parser').select_one('section.day'), retail_spec, retail_feed, '2024-06-03')
    retail_check(day_html)
    rejected('monthly_retail_introduction_changed', lambda: retail_check(day_html.replace('Synthetic retail introduction.', 'Changed introduction.')))
    rejected('monthly_retail_label_changed', lambda: retail_check(day_html.replace('Why Retail Is Here', 'Changed label', 1)))
    rejected('monthly_retail_chip_href_changed', lambda: retail_check(day_html.replace('https://example.org/source', 'https://example.org/changed', 1)))
    rejected('monthly_retail_dated_ledger_removed', lambda: retail_check(day_html[:day_html.index('<details class="sources">')] + '</section>'))
    rejected('monthly_retail_ledger_timestamp_changed', lambda: retail_check(day_html.replace('2024-06-02 12:00:00+00:00', '2024-06-01 12:00:00+00:00')))
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
        info = importlib.util.spec_from_file_location('june_artifact_static_' + name, path)
        module = importlib.util.module_from_spec(info)
        info.loader.exec_module(module)
        modules[name] = module
        hashes[name + '.py'] = sha(path.read_bytes())
        if hasattr(module, 'DATES'):
            check(module.DATES == DATES, 'Wrong June dates in ' + name)
    check(len(DATES) == 20 and DATES[0] == '2024-06-03' and DATES[-1] == '2024-06-28', 'Wrong 20-date scope')
    check('2024-06-19' in DATES, 'Exchange holiday weekday omitted')
    builder = modules['build_artifacts']
    check(builder.ZIP_NAME == 'June_2024_Weekday_Reports.zip', 'Wrong report ZIP name')
    check(builder.SOURCE_NAME == 'June_2024_Frozen_Sources.zip', 'Wrong source ZIP name')
    check(20 * 3 + 5 == 65 and 20 * 3 + 3 == 63, 'Wrong delivery counts')
    check('max-width:1280px' in modules['render'].BODY, 'Wide layout lost')
    check('retail-lead' in modules['render'].CSS and '@media print' in modules['render'].CSS, 'Retail or print styling missing')
    method = builder.methodology(DATES)
    check('June 2024' in method and '20 weekday editions' in method, 'Wrong methodology month/count')
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
    for literal in ['non\u2011breaking', 'non\u2010breaking', 'non-breaking', 'ordinary']:
        literal_html = BeautifulSoup(modules['render'].esc(literal), 'html.parser')
        check(literal_html.get_text() == literal and bool(literal_html.select('.literal-nbhyphen')) == ('\u2011' in literal),
              'Scoped U+2011 literal renderer protection changed')
    fixtures = negative_fixtures(modules)
    hashes['audit_work/review_final_artifacts.py'] = sha(Path(__file__).read_bytes())
    return {'status': 'static_checks_passed', 'dates': DATES, 'tool_sha256': hashes,
            'artifact_targets_expected': 65, 'report_zip_members_expected': 63,
            'runtime_artifacts_reviewed': False, 'negative_fixtures': fixtures, 'negative_fixture_count': len(fixtures),
            'scope': 'Generic June date/naming/shape/layout/escaping and code-compile checks only. No report data read, built, published or factually accepted.'}


def safe_member(name):
    if not isinstance(name, str) or not name:
        return False
    path = PurePosixPath(name)
    return (not path.is_absolute() and '..' not in path.parts and '\\' not in name
            and str(path) == name and not any(part.startswith('.') for part in path.parts)
            and path.name not in {'artifact_manifest.json', 'final_artifact_review.json', 'source_archive_build.json',
                                  'delivery_verification.json', 'publication.json', 'archive_index_reconciliation.json'}
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


class PublicResearchArchive:
    """An explicit public projection, with no stand-in original research bytes."""
    def __init__(self, archive, *, require_review=True):
        info = importlib.util.spec_from_file_location('public_research_archive_policy', ROOT / 'tools/build_source_inventory.py')
        policy = importlib.util.module_from_spec(info); info.loader.exec_module(policy)
        self.archive = archive
        self.context = policy.validate_public_research_bundle(archive.read, archive.namelist(),
            json.loads(archive.read('audit/independent_source_review.json')), require_review=require_review)
        self.checked_commitments = set()

    def namelist(self): return self.archive.namelist()
    def read(self, name): return self.archive.read(name)

    def commitment(self, name, expected, expected_bytes=None):
        row = self.context['commitments'].get(name)
        check(row is not None and row['sha256'] == expected
              and (expected_bytes is None or row['bytes'] == expected_bytes),
              'Private original research hash/size commitment changed: ' + name)
        self.checked_commitments.add(name)
        return True


def physical_source_dependencies(z, source, *, physical_review_only=False):
    """Replay accepted physical bytes and the precise disclosed transport losses.

    The explicit physical-only mode accepts no authoring/report inputs. It lets
    the real source producer/consumer boundary be checked before prose exists.
    """
    info = importlib.util.spec_from_file_location('artifact_transport_policy', ROOT / 'tools/build_source_inventory.py')
    policy = importlib.util.module_from_spec(info); info.loader.exec_module(policy)
    names = set(z.namelist()); checks = 0
    def digest(name, expected):
        nonlocal checks
        check(source_member_name(name) and name in names, 'Missing/unsafe physical dependency: ' + name)
        check(isinstance(expected, str) and len(expected) == 64 and sha(z.read(name)) == expected,
              'Changed physical dependency: ' + name)
        checks += 1
    proof_name = policy.PHYSICAL_REVIEW
    check(proof_name in names, 'Independent physical review missing')
    proof = json.loads(z.read(proof_name))
    if physical_review_only:
        check(source == proof, 'Physical-only consumer requires the actual retained physical receipt')
    else:
        digest(proof_name, source.get('prior_physical_review_sha256'))
        for key in policy.TRANSPORT_FIELDS:
            check(key in source and type(source[key]) is type(proof.get(key)) and source[key] == proof.get(key),
                  'Current source/physical transport proof differs: ' + key)
    bindings = proof.get('input_bindings')
    check(isinstance(bindings, dict) and bool(bindings), 'Independent physical input bindings missing')
    historical_context = {}
    for name, expected in bindings.items():
        # Original coverage is phase context; current semantic coverage is
        # independently bound by the full source input_bindings and freeze.
        if name == 'audit/news_coverage.json':
            check(name in names and source_member_name(name), 'Current semantic coverage missing')
            current = sha(z.read(name))
            if not physical_review_only:
                check(source.get('input_bindings', {}).get(name) == current, 'Final source must bind current semantic coverage bytes')
            historical_context[name] = {'earlier_physical_review_sha256': expected, 'current_sha256': current,
                                        'original_bytes_retained': False,
                                        'status': 'original_coverage_bytes_unreplayable_auxiliary_phase_metadata',
                                        'reason': 'Coverage changes during semantic projection by design; only this named historical phase context differs. Current coverage requires fresh final source/freeze replay.'}
        else:
            digest(name, expected)
    for name, field in [('audit/news_physical_requests.jsonl', 'ledger_sha256'),
                        ('audit/news_query_plan.json', 'query_plan_sha256'),
                        ('audit_work/physical_source_inventory.json', 'physical_source_inventory_sha256'),
                        (policy.CAPTURE_LIMITATION, 'discarded_error_body_limitations_sha256')]:
        digest(name, proof.get(field))
    check(bindings.get(policy.CAPTURE_LIMITATION) == proof['discarded_error_body_limitations_sha256'],
          'Physical missing-body whitelist absent from original input bindings')
    starts = None
    if policy.ATTEMPT_STARTS in names:
        digest(policy.ATTEMPT_STARTS, proof.get('attempt_starts_ledger_sha256'))
        starts = [json.loads(line) for line in z.read(policy.ATTEMPT_STARTS).decode().splitlines() if line.strip()]
    ledger = [json.loads(line) for line in z.read('audit/news_physical_requests.jsonl').decode().splitlines() if line.strip()]
    records = policy.transport_records(ledger, proof, json.loads(z.read(policy.CAPTURE_LIMITATION)), starts)
    for row in ledger:
        path = row.get('raw_response_path')
        if path:
            digest(path, row.get('raw_compressed_sha256'))
            check(sha(gzip.decompress(z.read(path))) == row.get('raw_sha256'), 'Physical attempt bytes changed: ' + path)
    check({name for name in names if name.startswith('cache/rss_raw/attempts/')} == records['bodies'],
          'Attempt-body archive differs from exact recorded ledger')
    physical = json.loads(z.read('audit_work/physical_source_inventory.json')); rows = physical.get('files', [])
    check(physical.get('query_plan_sha256') == proof['query_plan_sha256'], 'Physical inventory plan changed')
    check(type(proof.get('physical_requests')) is int and len(rows) == proof['physical_requests']
          and len({row['signature'] for row in rows}) == len(rows)
          and {row['signature'] for row in rows} == set(records['per_signature']) == set(records['successful']),
          'Physical canonical inventory count/signature/successful scope changed')
    current_cache_attempts = set(); query_urls = {}
    for row in rows:
        digest(row['parsed_cache_path'], row['parsed_cache_sha256'])
        digest(row['raw_xml_path'], row['raw_xml_compressed_sha256'])
        cache = json.loads(gzip.decompress(z.read(row['parsed_cache_path'])))
        attempts = cache.get('physical_attempts')
        check(isinstance(attempts, list) and bool(attempts) and type(row.get('physical_attempts')) is int
              and row['physical_attempts'] == len(attempts) and cache.get('signature') == row['signature']
              and cache.get('status') == 'fetched' and cache.get('response_format_verified') is True
              and isinstance(cache.get('request_url'), str) and bool(cache['request_url']),
              'Current canonical cache attempt schema/count changed')
        query_urls[row['signature']] = cache['request_url']; successful = []
        for attempt in attempts:
            identity = policy.attempt_identity(attempt)
            check(identity not in current_cache_attempts and records['ledger_rows'].get(identity) == attempt
                  and attempt['signature'] == row['signature'] and attempt.get('request_url') == cache['request_url'],
                  'Current cache attempt differs from immutable physical ledger')
            current_cache_attempts.add(identity)
            if attempt['status'] == 'fetched': successful.append(attempt)
        check(sha(gzip.decompress(z.read(row['raw_xml_path']))) == row['raw_xml_uncompressed_sha256']
              and bool(successful) and successful[-1]['raw_sha256'] == row['raw_xml_uncompressed_sha256']
              and cache.get('raw_response_path') == row['raw_xml_path']
              and cache.get('raw_sha256') == row['raw_xml_uncompressed_sha256']
              and cache.get('raw_response_compressed_sha256') == row['raw_xml_compressed_sha256'],
              'Canonical pair/last successful physical response bytes changed')
    check(all(row.get('request_url') == query_urls[row['signature']] for row in ledger),
          'Historical/current physical attempt URL differs from planned canonical query')
    return {'physical_dependency_hash_checks': checks, 'physical_attempts': len(ledger),
            'received_attempt_bodies': len(records['bodies']), 'canonical_physical_requests': len(rows),
            'recorded_missing_response_bodies': records['recorded_missing_response_bodies'],
            'modern_attempt_ids': records['modern_attempt_ids'], 'physical_review_only': physical_review_only,
            'historical_superseded_cache_attempts': len(ledger) - len(current_cache_attempts),
            'all_physical_network_attempts_complete': False,
            'unlogged_interrupted_attempts_maximum': proof['unlogged_interrupted_attempts_maximum'],
            'unlogged_interrupted_attempts_actual_count': None,
            'physical_proof_historical_context_only': historical_context}


def coverage_phase_binding(z, source, freeze, policy, *, expected_amendment_sha256=SOURCE_PHASE_AMENDMENT_SHA256):
    """Accept only the independently amended coverage entry and its three phases."""
    names = set(z.namelist()); coverage = 'audit/news_coverage.json'
    def blob(name):
        check(source_member_name(name) and name in names, 'Missing/unsafe phase dependency: ' + name)
        return z.read(name)
    def bound(name, expected):
        if name not in names and isinstance(z, PublicResearchArchive):
            z.commitment(name, expected)
            return None
        value = blob(name)
        check(isinstance(expected, str) and len(expected) == 64 and sha(value) == expected,
              'Changed coverage-phase dependency: ' + name)
        return value
    amendment_bytes = bound(SOURCE_PHASE_AMENDMENT, expected_amendment_sha256)
    amendment = json.loads(amendment_bytes)
    check(amendment.get('schema') == 'june-source-auxiliary-phase-binding-amendment-v1'
          and amendment.get('status') == 'independently_verified_metadata_only_phase_amendment'
          and amendment.get('passed') is True and amendment.get('errors') == []
          and amendment.get('affected_auxiliary_path') == coverage,
          'Unaccepted or wrongly scoped coverage-phase amendment')
    contract = amendment.get('consumer_patch_contract', {})
    check(contract.get('allowed_phase_difference_path') == coverage
          and contract.get('allowed_historical_maps') == ['audit/independent_physical_source_review.json.input_bindings',
                                                         'audit_work/news_policy_lock.json.files'],
          'Coverage-phase contract extends beyond the named historical maps')
    originals = amendment.get('original_proofs_preserved', {})
    expected = {'physical': ('audit/independent_physical_source_review.json', 'input_bindings'),
                'policy_lock': ('audit_work/news_policy_lock.json', 'files'),
                'staged': ('audit_work/independent_staged_source_review.json', 'input_bindings'),
                'source': ('audit/independent_source_review.json', 'input_bindings'),
                'freeze': ('audit/source_freeze.json', 'input_bindings')}
    check(set(originals) == set(expected), 'Incomplete original phase proof set')
    records = {}; hashes = {}
    for role, (path, field) in expected.items():
        saved = originals[role]
        check(saved.get('path') == path, 'Wrong original phase proof path: ' + role)
        value = bound(path, saved.get('sha256')); backup = bound(saved['backup_path'], saved.get('backup_sha256'))
        check(backup == value and saved.get('backup_sha256') == saved.get('sha256'), 'Original phase backup differs: ' + role)
        record = json.loads(value)
        check(isinstance(record.get(field), dict) and record[field] == saved.get('original_map'), 'Original proof map rewritten: ' + role)
        records[role] = record; hashes[role] = sha(value)
    check(records['source'] == source and records['freeze'] == freeze and records['policy_lock'] == policy,
          'Phase amendment is not bound to the actual current source/freeze/policy')
    check(source.get('status') == 'accepted_for_authoring_with_semantic_exclusions' and source.get('passed') is True
          and source.get('authoring_acceptance') is True and not source.get('errors')
          and [row.get('date') for row in source.get('dates', [])] == DATES
          and freeze.get('status') == 'all_20_ready' and source.get('source_freeze_sha256') == hashes['freeze']
          and source.get('prior_physical_review_sha256') == hashes['physical'], 'Current final source/physical/freeze acceptance changed')
    staged = records['staged']
    check(staged.get('status') == 'staged_infrastructure_verified' and staged.get('passed') is True
          and not staged.get('errors') and source['input_bindings'].get(expected['staged'][0]) == hashes['staged'],
          'Historical policy coverage lacks its actual passed staged proof')
    phases = amendment.get('phases', [])
    check([row.get('name') for row in phases] == ['physical_infrastructure_replay',
          'independently_verified_staged_semantic_projection', 'actual_final_frozen_source_acceptance'], 'Wrong coverage phase ordering/scope')
    physical, stage, final = phases
    for phase, role, field in [(physical, 'physical', 'input_bindings'), (stage, 'policy_lock', 'files'), (final, 'source', 'input_bindings')]:
        check(phase.get('path') == coverage and phase.get('proof_path') == expected[role][0]
              and phase.get('proof_sha256') == hashes[role] and phase.get('map') == field
              and phase.get('expected_sha256') == records[role][field].get(coverage), 'Coverage phase/proof/map binding changed: ' + role)
    check(all(row.get('status') == 'historical_auxiliary_bytes_unreplayable'
              and row.get('original_auxiliary_bytes_retained') is False and row.get('retained_matching_paths') == []
              for row in [physical, stage]), 'Unavailable historical coverage bytes must remain explicit')
    check(stage.get('independent_stage_proof_path') == expected['staged'][0]
          and stage.get('independent_stage_proof_sha256') == hashes['staged']
          and stage.get('independent_stage_expected_sha256') == staged['input_bindings'].get(coverage)
          == policy['files'].get(coverage), 'Wrong staged coverage phase hash')
    current = sha(blob(coverage))
    check(current == source['input_bindings'].get(coverage) == freeze.get('coverage_sha256') == final.get('expected_sha256')
          == final.get('source_freeze_expected_sha256') == final.get('current_auxiliary_backup_sha256')
          and final.get('source_freeze_path') == expected['freeze'][0] and final.get('source_freeze_sha256') == hashes['freeze']
          and final.get('status') == 'current_bytes_replayed_and_accepted', 'Current coverage does not match final source and freeze')
    check(bound(final['current_auxiliary_backup_path'], current) == blob(coverage), 'Current coverage backup differs')
    # The only historical mismatch is coverage. Every other map entry remains
    # exact, and all current final-source dependencies are still rehashed.
    for field, record in [('input_bindings', records['physical']), ('files', policy)]:
        for name, digest in record[field].items():
            if name != coverage: bound(name, digest)
    for name, digest in source['input_bindings'].items(): bound(name, digest)
    guard_name = 'audit/independent_release_guard_review.json'; semantic_name = 'audit_work/news_semantic_review.json'
    guard = json.loads(bound(guard_name, source['input_bindings'].get(guard_name)))
    semantic = json.loads(bound(semantic_name, source['input_bindings'].get(semantic_name)))
    check(guard.get('passed') is True and type(guard.get('fatal_or_major_remaining')) is int and guard['fatal_or_major_remaining'] == 0
          and not guard.get('errors') and guard.get('owner_policy_lock_sha256') == hashes['policy_lock']
          and guard.get('independent_staged_review_sha256') == hashes['staged']
          and semantic.get('status') == 'completed' and type(semantic.get('fatal_or_major_remaining')) is int
          and semantic['fatal_or_major_remaining'] == 0 and semantic.get('policy_lock_sha256') == hashes['policy_lock']
          and semantic.get('independent_staged_source_review_sha256') == hashes['staged']
          and semantic.get('independent_release_guard_review_sha256') == sha(blob(guard_name)), 'Passed staged guard/semantic evidence changed')
    return {'amendment_path': SOURCE_PHASE_AMENDMENT, 'amendment_sha256': sha(amendment_bytes),
            'affected_auxiliary_path': coverage, 'phases': phases,
            'all_original_proofs_and_backups_preserved': True, 'all_current_source_bindings_verified': len(source['input_bindings']),
            'report_editorial_or_publication_acceptance': False}


def current_source_dependencies(z, source, freeze):
    """Verify actual current producer bindings and every received request body."""
    names = set(z.namelist()); checks = 0
    def digest(name, expected):
        nonlocal checks
        if name not in names and isinstance(z, PublicResearchArchive):
            check(source_member_name(name), 'Unsafe private research dependency: ' + name)
            z.commitment(name, expected); checks += 1
            return
        check(source_member_name(name) and name in names, 'Missing/unsafe source dependency: ' + name)
        check(isinstance(expected, str) and len(expected) == 64 and sha(z.read(name)) == expected, 'Changed source dependency: ' + name)
        checks += 1
    bindings = source.get('input_bindings')
    check(isinstance(bindings, dict) and bool(bindings), 'Current source input_bindings required')
    for name, expected in bindings.items(): digest(name, expected)
    for row in source.get('dates', []):
        date = row['date']; ready_name = f'audit/news_ready_{date}.json'
        digest(ready_name, row.get('ready_receipt_sha256'))
        check(bindings.get(ready_name) == row['ready_receipt_sha256'], 'Screening receipt absent from current input_bindings: ' + date)
        ready = json.loads(z.read(ready_name))
        check(ready.get('date') == date and ready.get('status') == 'ready'
              and ready.get('ready_sha256') == row.get('feed_sha256')
              and ready.get('unreviewed_sha256') == row.get('raw_sha256'), 'Screening receipt identity changed: ' + date)
        counts = [ready.get(key) for key in ('input_items', 'ready_items', 'excluded_items')]
        accepted = [row.get(key) for key in ('raw_items', 'ready_items', 'excluded')]
        exclusions = ready.get('excluded')
        check(all(type(value) is int and value >= 0 for value in counts + accepted)
              and counts == accepted and isinstance(exclusions, list) and counts[2] == len(exclusions)
              and counts[0] == counts[1] + counts[2], 'Screening exclusion counts changed: ' + date)
        identities = [item.get('id') if isinstance(item, dict) else None for item in exclusions]
        check(all(isinstance(identity, str) and re.fullmatch(r'n\d{4,6}', identity) for identity in identities)
              and len(identities) == len(set(identities)), 'Screening exclusion IDs changed: ' + date)
        digest(f'work/unreviewed_feeds/{date}.json.gz', row['raw_sha256'])
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
    for field, name in [('query_plan_sha256', 'audit/news_query_plan.json'), ('coverage_sha256', 'audit/news_coverage.json'),
                        ('candidate_manifest_sha256', freeze.get('candidate_manifest', '')),
                        ('semantic_review_sha256', 'audit_work/news_semantic_review.json'),
                        ('physical_request_ledger_sha256', 'audit/news_physical_requests.jsonl')]:
        digest(name, freeze.get(field))
    policy = json.loads(z.read('audit_work/news_policy_lock.json'))
    check(isinstance(policy.get('files'), dict) and bool(policy['files']), 'Missing source policy dependency map')
    phase_context = None
    for name, expected in policy['files'].items():
        if name == 'audit/news_coverage.json' and name in names and sha(z.read(name)) != expected:
            phase_context = coverage_phase_binding(z, source, freeze, policy)
        else:
            digest(name, expected)
    physical_result = physical_source_dependencies(z, source)
    # Discovery provenance describes the upstream toolkit hashes separately from
    # adapted current tools. Only the selected newest Lambda source is compared.
    provenance = json.loads(z.read('code_provenance.json'))
    discovery = json.loads(z.read('checks/code_discovery.json'))
    digest('newest_lambda_function.py', provenance.get('source_sha256'))
    check(discovery.get('source_sha256') == provenance['source_sha256'], 'Newest-code discovery/source provenance mismatch')
    return {'source_input_bindings': len(bindings), 'source_dependency_hash_checks': checks,
            **physical_result, 'current_source_schema_checked': True, 'source_phase_binding_amendment': phase_context,
            'original_research_bytes_checked': not isinstance(z, PublicResearchArchive)}

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
          and market.get('dates') == DATES, 'Source ZIP lacks accepted 20-date inputs')
    check(replay.get('report_month') == '2024-06' and replay.get('dates') == DATES
          and replay.get('status') == 'frozen_inputs_hash_bound', 'Wrong replay inventory scope')
    for field, name in [('source_acceptance_sha256', 'independent_source_review.json'),
                        ('market_acceptance_sha256', 'independent_market_review.json')]:
        check(replay.get(field) == sha(z.read('audit/' + name)), 'Replay acceptance hash changed: ' + name)
    freeze = 'audit/source_freeze.json'
    check(freeze in names and source.get('source_freeze_sha256') == sha(z.read(freeze))
          and market.get('source_freeze_sha256') == sha(z.read(freeze)), 'Source freeze binding changed')
    freeze_record = json.loads(z.read(freeze))
    check(freeze_record.get('status') == 'all_20_ready'
          and [row.get('date') for row in freeze_record.get('dates', [])] == DATES, 'Wrong source-freeze scope')
    for row in source['dates']:
        date = row['date'];feed = f'feeds/{date}.json.gz';card = f'cards/{date}.json'
        check(feed in names and card in names and row.get('feed_sha256') == sha(z.read(feed)), 'Accepted feed changed: ' + date)
        check(all(review.get('card_sha256', {}).get(date) == sha(z.read(card)) for review in (source, market)), 'Accepted card changed: ' + date)
    source_dependency_result = current_source_dependencies(z, source, freeze_record)
    rows = replay.get('files', [])
    check(bool(rows) and replay.get('file_count') == len(rows) and len({row['path'] for row in rows}) == len(rows), 'Empty/duplicate/incomplete replay rows')
    for row in rows:
        name = row['path']
        check(replay_member_name(name), 'Unsafe replay member: ' + name)
        if name not in names and isinstance(z, PublicResearchArchive):
            z.commitment(name, row.get('sha256'), row.get('bytes'))
            continue
        check(name in names, 'Missing original replay member: ' + name)
        blob = z.read(name)
        check(len(blob) == row.get('bytes') and sha(blob) == row.get('sha256'), 'Replay input changed: ' + name)
    result = {'replay_inputs_verified': len(rows), **source_dependency_result}
    if isinstance(z, PublicResearchArchive):
        result['public_research_projection'] = {key: value for key, value in z.context.items() if key != 'commitments'}
        result['private_research_hash_commitments_verified'] = len(z.checked_commitments)
        result['original_research_bytes_checked'] = False
    return result

def final_review():
    result = static_review()
    manifest = load(ROOT / 'checks/artifact_manifest.json')
    check(manifest.get('dates') == DATES and manifest.get('complete_month') is True, 'Incomplete month')
    check([r['date'] for r in manifest['reports']] == DATES, 'Missing/duplicate report rows')
    check(set(manifest['collection']) == COLLECTION and manifest.get('artifact_targets') == 65, 'Wrong collection/target count')
    rows = []
    expected_zip = {'index.html', 'methodology.txt', 'What_Retail_Is_Playing_2024-06.html'}
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
    report_zip = ROOT / 'collection/June_2024_Weekday_Reports.zip'
    with zipfile.ZipFile(report_zip) as z:
        check(z.testzip() is None, 'Report ZIP CRC error')
        check(set(z.namelist()) == expected_zip and len(z.namelist()) == 63, 'Wrong report ZIP members')
        for name in z.namelist():
            check(safe_member(name), 'Unsafe report ZIP member')
            if name != 'index.html':
                local = ROOT / (name if name.startswith(('html/', 'pdf/', 'json/')) else 'collection/' + name)
                check(z.read(name) == local.read_bytes(), 'Report ZIP bytes differ: ' + name)
        offline = BeautifulSoup(z.read('index.html'), 'html.parser')
        check([a['href'] for a in offline.select('a.day')] == ['html/' + d + '.html' for d in DATES], 'Wrong offline links')
    source_zip = ROOT / 'collection/June_2024_Frozen_Sources.zip'
    with zipfile.ZipFile(source_zip) as z:
        check(z.testzip() is None, 'Source ZIP CRC error')
        inventory = json.loads(z.read('source_inventory.json'))
        check(len({r['path'] for r in inventory}) == len(inventory), 'Duplicate source inventory')
        check(set(z.namelist()) == {r['path'] for r in inventory} | {'source_inventory.json'}, 'Source ZIP inventory differs')
        check(len(z.namelist()) == len(inventory) + 1, 'Duplicate source ZIP member')
        for file in inventory:
            name = file['path']
            check(source_member_name(name), 'Unsafe source ZIP path: ' + name)
            check(not any(m != '2024-06' for m in re.findall(r'20\d{2}-\d{2}(?=-\d{2}(?:\D|$))', name)), 'Other report-month input: ' + name)
            check(not any(t in Path(name).name.lower() for t in ('secret', 'credential', '.pem', '.key')), 'Sensitive filename')
            blob = z.read(name)
            check(len(blob) == file['bytes'] and sha(blob) == file['sha256'], 'Source ZIP hash mismatch: ' + name)
            check(blob == local_member(name).read_bytes(), 'Source ZIP differs from retained input: ' + name)
        source_members = {r['path'] for r in inventory}
        check({'audit/news_physical_requests.jsonl', 'reference/nonretail_schema.json', 'reference/retail_schema.json'} <= source_members,
              'Source ZIP missing explicit physical ledger or blank reference schema')
        for d in DATES:
            for prefix, suffix in [('feeds/', '.json.gz'), ('cards/', '.json'), ('specs/', '.json'), ('nonretail_drafts/', '.json'), ('retail_drafts/', '.json')]:
                check(prefix + d + suffix in source_members, 'Source ZIP missing current component ' + prefix + d)
        for prefix in ['cache/news/', 'cache/rss_raw/', 'audit/news_provenance/', 'audit/market_raw/', 'exclusions/']:
            check(any(name.startswith(prefix) for name in source_members), 'Source ZIP missing replay family ' + prefix)
        # Local original bytes remain strict; the public ZIP intentionally
        # contains a reviewed compact projection for raw web research only.
        info = importlib.util.spec_from_file_location('local_public_research_policy', ROOT / 'tools/build_source_inventory.py')
        projection_policy = importlib.util.module_from_spec(info); info.loader.exec_module(projection_policy)
        projection_policy.public_research_export()
        replay_input_count = replay_archive(PublicResearchArchive(z))
        market = load(ROOT / 'audit/independent_market_review.json')
        for name, digest in market.get('input_sha256', {}).items():
            check(name in source_members and sha(z.read(name)) == digest, 'Missing/changed independent market replay input: ' + name)
    collection = BeautifulSoup((ROOT / 'collection/2024-06.html').read_text(), 'html.parser')
    check([a['href'] for a in collection.select('a.day')] == ['archive/' + d + '.html' for d in DATES], 'Wrong online links')
    retail_path = ROOT / 'collection/What_Retail_Is_Playing_2024-06.html'
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
        targets += [('collection', ROOT / 'collection/2024-06.html'), ('retail_collection', retail_path)]
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
                  reports=rows, monthly_retail_checks=monthly_retail_checks, layouts=layouts, report_zip_members=63,
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
