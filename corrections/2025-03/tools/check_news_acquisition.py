"""Independently check the April query inventory, frozen feeds and boundary behavior.

This checker never fetches network data or rewrites acquisition inputs. It
reconstructs required intervals from the catalogue rather than trusting the
acquisition planner, and independently merges cached records before comparing
the raw snapshots. Publisher-body vintages and original server responses remain
outside this audit's claims. Run before freezing report artifacts.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import urllib.parse
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parent.parent
UTC = dt.timezone.utc
DATES = [dt.date(2025, 4, n) for n in range(1, 31)
         if dt.date(2025, 4, n).weekday() < 5]
AGES = {'news': 7, 'result': 14, 'monthly': 35}
PREVIEW = re.compile(r'\b(?:preview|previews|ahead of|week ahead|to report|will report|set to report|what to expect|earnings calendar)\b', re.I)
ROLLING = re.compile(r'\b(?:live updates|live blog|as it happened|stock market today|markets today)\b', re.I)
ACQUISITION_TOOLS = ['tools/fetch_news.py', 'tools/expand_capped_news.py',
                     'tools/topics.py', 'tools/ready_feeds.py']
HELPER_TOOLS = ['tools/digest.py', 'posthoc/resolve_news_url.py']
RSS_CI_FILES = {'.github/workflows/apr2025-rss-recovery.yml',
                'corrections/2025-04/rss_recovery/fetch_news.py',
                'corrections/2025-04/rss_recovery/input.json',
                'corrections/2025-04/rss_recovery/run.py'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


def safe_path(name):
    path = (ROOT/name).resolve()
    require(path.is_relative_to(ROOT) and path.is_file(), 'Invalid input path: '+name)
    return path


def interval_key(job):
    topic, query, category, locale, lower, upper = job
    return topic, query, category, tuple(locale), str(lower), str(upper)


def request_url(job):
    _, query, _, locale, lower, upper = interval_key(job)
    lower = dt.date.fromisoformat(lower)
    q = f'{query} after:{lower-dt.timedelta(days=1)} before:{upper}'
    return 'https://news.google.com/rss/search?'+urllib.parse.urlencode(
        {'q': q, 'hl': locale[0], 'gl': locale[1], 'ceid': locale[2]})


def expected_initial_contexts():
    # Reconstruct by category age and calendar partition; do not call make_jobs
    # or cutoff_prefix_jobs from the acquisition implementation.
    from topics import TOPICS, EN
    weekly, prefix = [], []
    for topic, entries in TOPICS.items():
        for entry in entries:
            query, category = entry[:2]
            locale = tuple(entry[2]) if len(entry) > 2 else tuple(EN)
            lower = min(DATES)-dt.timedelta(days=AGES[category])
            while lower < max(DATES):
                upper = min(lower+dt.timedelta(days=7), max(DATES))
                base = (topic, query, category, locale, lower.isoformat(), upper.isoformat())
                weekly.append(base)
                for cutoff in DATES:
                    if lower < cutoff < upper:
                        prefix.append((base, (*base[:5], cutoff.isoformat())))
                lower = upper
    return weekly, prefix


def context_token(job, kind, parent=None):
    return interval_key(job), kind, parent


def record_key(item):
    return item['title'].casefold(), item['src'].casefold(), item['published_at']


def eligible_context(job, date):
    _, _, category, _, lower, upper = interval_key(job)
    stamp = date.isoformat()
    return (lower < stamp and upper <= stamp
            and upper > (date-dt.timedelta(days=AGES[category])).isoformat())


def independent_merge(date, requests, batches):
    """Replay parsed search observations directly, independently of collect_feed."""
    cutoff = dt.datetime.combine(date, dt.time(), UTC)
    grouped = {}
    signatures = {}
    for row in requests:
        batch = batches[row['signature']]
        seen_contexts = set()
        for context in row['contexts']:
            job = interval_key(context['job'])
            if job in seen_contexts:
                continue
            seen_contexts.add(job)
            if not eligible_context(job, date):
                continue
            topic, query, category, locale, _, _ = job
            for item in batch['items']:
                pub = dt.datetime.fromisoformat(item['published_at'])
                effective = 'news' if PREVIEW.search(item['title']) else category
                if not cutoff-dt.timedelta(days=AGES[effective]) <= pub < cutoff:
                    continue
                key = record_key(item)
                signatures.setdefault(key, set()).add(row['signature'])
                if key not in grouped:
                    grouped[key] = {**item, 'cat': effective, 'topics': [topic],
                                    'q': query, 'queries': [query], 'lang': locale[0]}
                else:
                    result = grouped[key]
                    if topic not in result['topics']:
                        result['topics'].append(topic)
                    if query not in result['queries']:
                        result['queries'].append(query)
                    if AGES[effective] < AGES[result['cat']]:
                        result['cat'] = effective
    result = [item for item in grouped.values()
              if cutoff-dt.timedelta(days=AGES[item['cat']])
              <= dt.datetime.fromisoformat(item['published_at']) < cutoff]
    result.sort(key=lambda x: (x['topics'][0], x['published_at'], x['title'], x['src'], x['url']))
    ledger = {}
    for index, item in enumerate(result, 1):
        item['id'] = f'n{index:04d}'
        ledger[item['id']] = sorted(signatures[record_key(item)])
    return result, ledger


def fixture_checks():
    # Production code is exercised with deliberately conflicting query and
    # publication boundaries; fixtures never touch real acquisition inputs.
    import fetch_news as acquire
    checks = []
    date = dt.date(2025, 4, 10)
    base = {'status': 'fetched', 'signature': 'fixture', 'topic': 'us_macro',
            'query': 'fixture', 'category': 'news', 'locale': ['en-US', 'US', 'US:en'],
            'lower_date': '2025-04-01', 'upper_date_exclusive': '2025-04-10'}

    def item(title, stamp):
        return {'published_at': stamp, 'src': 'Fixture', 'title': title,
                'url': 'https://example.com/'+urllib.parse.quote(title),
                'source_url': 'https://example.com'}

    def collect(rows):
        return acquire.collect_feed(date, rows, asof_queries=True)

    probe = [item('lower included', '2025-04-03T00:00:00+00:00'),
             item('old excluded', '2025-04-02T23:59:59+00:00'),
             item('last included', '2025-04-09T23:59:59+00:00'),
             item('midnight excluded', '2025-04-10T00:00:00+00:00')]
    rows, _, failures = collect([{**base, 'items': probe}])
    require({r['title'] for r in rows} == {'lower included', 'last included'} and not failures,
            'Inclusive age boundary/exclusive midnight fixture failed')
    checks.append({'name': 'age_lower_inclusive_and_midnight_exclusive', 'passed': True})
    require(not collect([{**base, 'upper_date_exclusive': '2025-04-11', 'items': probe}])[0],
            'Later query interval leaked an earlier published record')
    require(len(collect([{**base, 'items': [probe[0]]}])[0]) == 1,
            'Query interval ending at own midnight was rejected')
    checks.append({'name': 'future_query_days_rejected_even_with_old_publication', 'passed': True})
    old_result = item('Result published', '2025-03-30T12:00:00+00:00')
    old_preview = item('Result preview ahead of earnings', '2025-03-30T12:00:00+00:00')
    rows, _, _ = collect([{**base, 'category': 'result', 'lower_date': '2025-03-25',
                          'items': [old_result, old_preview]}])
    require([r['title'] for r in rows] == ['Result published'], 'Preview retained result age')
    checks.append({'name': 'previews_cannot_inherit_longer_result_window', 'passed': True})
    duplicate = item('Distinct story', '2025-04-09T12:00:00+00:00')
    rows, _, _ = collect([{**base, 'category': 'result', 'items': [duplicate]},
                          {**base, 'topic': 'retail', 'query': 'other', 'items': [duplicate]},
                          {**base, 'items': [{**duplicate, 'published_at': '2025-04-09T13:00:00+00:00'}]}])
    first = next(x for x in rows if x['published_at'].endswith('12:00:00+00:00'))
    require(len(rows) == 2 and first['cat'] == 'news' and first['topics'] == ['us_macro', 'retail']
            and first['queries'] == ['fixture', 'other'], 'Dedup context or timestamp identity failed')
    checks.append({'name': 'duplicate_contexts_preserved_and_distinct_times_retained', 'passed': True})
    require(collect([{**base, 'status': 'failed', 'items': []}])[2] == ['fixture'],
            'Relevant failed request disappeared')
    require(not collect([{**base, 'status': 'failed', 'upper_date_exclusive': '2025-04-11', 'items': []}])[2],
            'Ineligible future request counted as own-date failure')
    checks.append({'name': 'relevant_failed_request_is_not_successful_empty_evidence', 'passed': True})
    try:
        collect([{**base, 'items': [item('naive timestamp', '2025-04-09T12:00:00')]}])
    except (TypeError, ValueError):
        pass
    else:
        raise ValueError('Naive publication timestamp was accepted')
    checks.append({'name': 'naive_publication_timestamp_rejected', 'passed': True})
    # Exercise the actual XML parser and transport-error path with an isolated
    # cache. No requests are sent, and inherited network configuration is intact.
    class Response:
        def __init__(self, raw):
            self.raw = raw
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def read(self):
            return self.raw

    def xml_node(title, pub, link='https://example.com/story'):
        return (f'<item><title>{title}</title><pubDate>{pub}</pubDate>'
                f'<link>{link}</link><source url="https://example.com">Fixture</source></item>')

    valid = xml_node('Eligible story', 'Wed, 09 Apr 2025 19:59:59 -0400')
    raw = ('<rss><channel>'+valid
           +xml_node('Future story', 'Thu, 10 Apr 2025 00:00:00 +0000')
           +xml_node('Malformed clock', 'not-a-date')
           +xml_node('Missing timezone', 'Wed, 09 Apr 2025 12:00:00')
           +xml_node('Market live updates', 'Wed, 09 Apr 2025 12:00:00 +0000')
           +xml_node('Insecure link', 'Wed, 09 Apr 2025 12:00:00 +0000', 'http://example.com')
           +'</channel></rss>').encode()
    example_job = ('us_macro', 'parser-fixture', 'news', ('en-US', 'US', 'US:en'),
                   dt.date(2025, 4, 9), date)
    with tempfile.TemporaryDirectory(prefix='april-source-qa-') as directory:
        temp = Path(directory)
        with mock.patch.object(acquire, 'CACHE', temp), mock.patch.object(
                acquire.urllib.request, 'urlopen', return_value=Response(raw)):
            parsed = acquire.fetch(example_job, attempts=1)
        require(parsed['status'] == 'fetched' and parsed['raw_count'] == 6
                and len(parsed['items']) == 1
                and parsed['items'][0]['published_at'] == '2025-04-09T23:59:59+00:00'
                and parsed['discarded'] == {'outside_query_window': 1, 'malformed_timestamp': 2,
                                           'rolling_headline': 1, 'missing_title_or_https_url': 1},
                'XML parsing/drop-accounting fixture failed')
        capped_raw = ('<rss><channel>'+valid*100+'</channel></rss>').encode()
        capped_job = (*example_job[:1], 'cap-fixture', *example_job[2:])
        with mock.patch.object(acquire, 'CACHE', temp), mock.patch.object(
                acquire.urllib.request, 'urlopen', return_value=Response(capped_raw)):
            capped = acquire.fetch(capped_job, attempts=1)
        require(capped['possibly_capped'] is True and capped['raw_count'] == 100,
                'Exact 100-row RSS ceiling was not flagged')
        failed_job = (*example_job[:1], 'failure-fixture', *example_job[2:])
        with mock.patch.object(acquire, 'CACHE', temp), mock.patch.object(
                acquire.urllib.request, 'urlopen', side_effect=OSError('isolated fixture')):
            failed = acquire.fetch(failed_job, attempts=1)
        require(failed['status'] == 'failed' and failed['items'] == [] and failed['error_type'] == 'OSError',
                'Transport failure was accepted as fetched empty RSS')
        checks.append({'name': 'xml_timestamp_filter_cap_and_transport_failure', 'passed': True})
        invalid_job = (*example_job[:1], 'non-rss-fixture', *example_job[2:])
        with mock.patch.object(acquire, 'CACHE', temp), mock.patch.object(
                acquire.urllib.request, 'urlopen', return_value=Response(b'<html><body>Service challenge</body></html>')):
            invalid = acquire.fetch(invalid_job, attempts=1)
        require(invalid['status'] == 'failed', 'Wellformed service HTML masqueraded as empty RSS')
        empty_job = (*example_job[:1], 'empty-rss-fixture', *example_job[2:])
        with mock.patch.object(acquire, 'CACHE', temp), mock.patch.object(
                acquire.urllib.request, 'urlopen', return_value=Response(b'<rss><channel></channel></rss>')):
            empty = acquire.fetch(empty_job, attempts=1)
        require(empty['status'] == 'fetched' and empty['raw_count'] == 0 and empty['items'] == []
                and empty['possibly_capped'] is False, 'Valid empty RSS was not recognized')
        checks.append({'name': 'service_html_rejected_and_valid_empty_rss_accepted', 'passed': True})
        stale = dict(parsed)
        stale.pop('parser_schema')
        cached_path = temp/(parsed['signature']+'.json.gz')
        cached_path.write_bytes(gzip.compress(json.dumps(stale).encode(), mtime=0))
        with mock.patch.object(acquire, 'CACHE', temp), mock.patch.object(
                acquire.urllib.request, 'urlopen', return_value=Response(raw)) as request:
            refreshed = acquire.fetch(example_job, attempts=1)
        require(request.call_count == 1 and refreshed.get('parser_schema') == acquire.PARSER_SCHEMA,
                'Old parser-schema cache was reused without refetching')
        with mock.patch.object(acquire, 'CACHE', temp), mock.patch.object(
                acquire.urllib.request, 'urlopen', side_effect=AssertionError('Should use current compatible cache')):
            reused = acquire.fetch(example_job, attempts=1)
        require(json.dumps(reused, sort_keys=True) == json.dumps(refreshed, sort_keys=True),
                'Current parser-schema cache could not be reused')
        checks.append({'name': 'old_parser_cache_refetched_and_current_contract_cache_reused', 'passed': True})
        # A URL can be shared by different topic and category contexts. The
        # stored first-request metadata must not erase a second consumer.
        import expand_capped_news as expansion
        cache_path = temp/'context.json.gz'
        cache_path.write_bytes(gzip.compress(json.dumps(parsed).encode(), mtime=0))
        context_job = expansion.serial(example_job)
        second_job = list(context_job)
        second_job[0], second_job[2] = 'retail', 'result'
        plan = {'requests': [{'signature': parsed['signature'], 'cache_path': 'context.json.gz',
                              'cache_sha256': sha(cache_path),
                              'contexts': [{'job': context_job, 'kind': 'weekly'},
                                           {'job': second_job, 'kind': 'weekly'}]}]}
        with mock.patch.object(expansion, 'ROOT', temp), mock.patch.object(expansion, 'CACHE', temp):
            contexts = expansion.load_harvest(plan)
        require([(r['topic'], r['category']) for r in contexts] == [('us_macro', 'news'), ('retail', 'result')],
                'Physical URL reuse erased a topic/category context')
        merged, _, _ = collect(contexts)
        require(len(merged) == 1 and merged[0]['topics'] == ['us_macro', 'retail'],
                'Shared URL contexts disappeared from merged metadata')
        checks.append({'name': 'shared_url_cache_replays_distinct_topic_category_contexts', 'passed': True})
    from ready_feeds import release_guard_reason
    release_cases = [
        ('RBA keeps rates unchanged', '2025-03-31', '2025-04-01', True),
        ('RBA keeps rates unchanged', '2025-04-01', '2025-04-02', False),
        ('Trump announces reciprocal tariffs with 10% baseline', '2025-04-01', '2025-04-02', True),
        ('Trump announces reciprocal tariffs with 10% baseline', '2025-04-02', '2025-04-03', False),
        ('Trump pauses tariffs for 90 days', '2025-04-08', '2025-04-09', True),
        ('Trump pauses tariffs for 90 days', '2025-04-09', '2025-04-10', False),
        ('US March CPI inflation falls', '2025-04-09', '2025-04-10', True),
        ('China Q1 GDP growth rises', '2025-04-15', '2025-04-16', True),
        ('US Q1 GDP contracts 0.3%', '2025-04-29', '2025-04-30', True),
        ('US March CPI inflation expected to fall', '2025-04-09', '2025-04-10', False),
        ('Japan Tokyo CPI inflation rises', '2025-04-24', '2025-04-25', False),
        ('RBA holds rates but could cut later', '2025-03-31', '2025-04-01', True),
        ('RBA expected to hold rates but could cut later', '2025-03-31', '2025-04-01', False),
        ('RBA keeps rates unchanged as expected', '2025-03-31', '2025-04-01', True),
        ('Nvidia expects up to $5.5 billion charge after US imposes H20 export license rule',
         '2025-04-14', '2025-04-15', True),
        ('Nvidia expects up to $5.5 billion charge after US imposes H20 export license rule',
         '2025-04-15', '2025-04-16', False),
        ('Nvidia could need an H20 export license', '2025-04-14', '2025-04-15', False),
        ('US March CPI falls but Fed could keep rates unchanged', '2025-04-09', '2025-04-10', True),
        ('US March CPI expected to fall while Fed could keep rates unchanged', '2025-04-09', '2025-04-10', False),
        ('China Q1 GDP rises as government expects stronger growth', '2025-04-15', '2025-04-16', True),
        ('China Q1 GDP expected to rise as government expects stronger growth', '2025-04-15', '2025-04-16', False),
        ('ECB cuts interest rates but could pause later', '2025-04-16', '2025-04-17', True),
        ('ECB expected to cut interest rates but could pause later', '2025-04-16', '2025-04-17', False),
        ('RBA held rates unchanged but could cut later', '2025-03-31', '2025-04-01', True),
        ('China Q1 GDP grew as government expects stronger growth', '2025-04-15', '2025-04-16', True),
        ('Wynagrodzenia w marcu wzrosły mocniej od oczekiwań - GUS', '2025-04-21', '2025-04-22', True),
        ('Prognoza: wynagrodzenia w marcu mogą wzrosnąć - GUS', '2025-04-21', '2025-04-22', False),
        ('US stocks fall while March CPI expected to rise', '2025-04-09', '2025-04-10', False),
        ('China stocks rise while Q1 GDP expected to improve', '2025-04-15', '2025-04-16', False),
        ('RBA held rates while April minutes could signal cuts', '2025-04-14', '2025-04-15', False),
        ('RBA April minutes show concern but could suggest cuts', '2025-04-14', '2025-04-15', True),
        ('Poland stocks rise while March industrial output expected to fall', '2025-04-21', '2025-04-22', False),
        ('Australia stocks rise while March employment expected to fall', '2025-04-16', '2025-04-17', False),
    ]
    for title, published, report, blocked in release_cases:
        require(bool(release_guard_reason({'title': title, 'published_at': published+'T23:30:00+00:00'}, report)) == blocked,
                'Configured release guard boundary fixture failed: '+title+' '+report)
    checks.append({'name': 'high_risk_release_actuals_and_preview_early_japan_boundaries',
                   'passed': True, 'cases': len(release_cases)})
    from digest import rank
    from ready_feeds import selected
    older = {'src': 'Reuters', 'published_at': '2025-04-09T09:00:00+00:00'}
    newer = {'src': 'Reuters', 'published_at': '2025-04-09T18:00:00+00:00'}
    require(sorted([older, newer], key=rank) == [newer, older],
            'Same-day timestamp precision lost in ranking')
    require(rank(newer) == rank({**newer, 'published_at': '2025-04-09T20:00:00+02:00'}),
            'Ranking does not compare equivalent UTC instants')
    try:
        rank({**newer, 'published_at': '2025-04-09T18:00:00'})
    except ValueError:
        pass
    else:
        raise ValueError('Ranking accepted a naive clock')
    candidates = [{'id': f'n{n+1:04d}', 'src': 'Reuters', 'title': 'Synthetic priority example',
                   'published_at': f'2025-04-09T18:{n:02d}:00+00:00', 'topics': ['us_macro']}
                  for n in range(36)]
    chosen = {entry['id'] for entry in selected(candidates)}
    require(chosen == {f'n{n:04d}' for n in range(2, 37)},
            'Priority cap selected an old same-day story instead of the newest')
    checks.append({'name': 'full_timestamp_utc_ranking_and_priority_cap_boundary', 'passed': True,
                   'candidate_count': 36, 'selected_count': 35})
    pilot = ROOT/'work/rss_recovery_batch1'
    if pilot.is_dir() and (ROOT/'tools/import_public_rss.py').is_file():
        import import_public_rss as importer
        with tempfile.TemporaryDirectory(prefix='april-rss-import-qa-') as directory:
            temp = Path(directory)
            (temp/'tools').mkdir()
            shutil.copy2(ROOT/'tools/fetch_news.py', temp/'tools/fetch_news.py')
            batch = temp/'work/rss_recovery_batch1'
            shutil.copytree(pilot, batch)
            with mock.patch.object(importer, 'ROOT', temp):
                records, proof = importer.verify(batch)
            require(len(records) == 100 and proof['status'] == 'verified',
                    'Captured pilot import could not be replayed in isolation')
            binding_path = batch/'run_binding.json'
            original_binding = binding_path.read_bytes()
            binding = json.loads(original_binding)
            binding['jobs'][0]['artifact_sha256'] = '0'*64
            binding_path.write_text(json.dumps(binding))
            try:
                with mock.patch.object(importer, 'ROOT', temp):
                    importer.verify(batch)
            except AssertionError:
                pass
            else:
                raise ValueError('Changed public artifact digest was accepted')
            binding_path.write_bytes(original_binding)
            parser_path = batch/'source/corrections/2025-04/rss_recovery/fetch_news.py'
            parser_path.write_bytes(parser_path.read_bytes()+b'\n# Changed parser fixture\n')
            try:
                with mock.patch.object(importer, 'ROOT', temp):
                    importer.verify(batch)
            except AssertionError:
                pass
            else:
                raise ValueError('Changed reviewed CI parser was accepted')
        checks.append({'name': 'actual_pilot_import_replay_and_tampered_artifact_parser_rejection',
                       'passed': True, 'records': 100, 'negative_cases': 2})
    return checks


def verify_acquisition():
    import fetch_news as acquire
    from topics import TOPICS
    coverage_path = ROOT/'audit/news_coverage.json'
    plan_path = ROOT/'audit/news_query_plan.json'
    coverage, plan = map(read, [coverage_path, plan_path])
    require(coverage.get('status') == 'acquired_verified' and coverage.get('report_dates') == len(DATES),
            'Complete acquired coverage receipt required')
    require(coverage.get('parser_schema') == acquire.PARSER_SCHEMA,
            'Coverage parser contract differs from strict current parser')
    require(coverage['query_plan_sha256'] == sha(plan_path), 'Query plan differs from coverage proof')
    tool_hashes = {name: sha(safe_path(name)) for name in ACQUISITION_TOOLS}
    helper_hashes = {name: sha(safe_path(name)) for name in HELPER_TOOLS}
    require(set(coverage['acquisition_tool_sha256']) == set(ACQUISITION_TOOLS),
            'Complete acquisition code inventory required')
    for name, value in coverage['acquisition_tool_sha256'].items():
        require(tool_hashes[name] == value, 'Acquisition tool changed: '+name)
    require(coverage.get('helper_tool_sha256') == helper_hashes, 'Acquisition helper changed')
    requests = plan['requests']
    by_signature = {r['signature']: r for r in requests}
    require(len(by_signature) == len(requests) == len({r['request_url'] for r in requests}),
            'Duplicate physical requests')
    require(plan['dates'] == [d.isoformat() for d in DATES], 'Query plan dates differ')
    batches, actual_contexts, before = {}, {}, {}
    cached_items = 0
    for row in requests:
        sig = row['signature']
        require(sig == hashlib.sha256((acquire.VERSION+'\n'+row['request_url']).encode()).hexdigest(),
                'Request signature mismatch: '+sig)
        path = safe_path(row['cache_path'])
        require(sha(path) == row['cache_sha256'], 'Cache hash mismatch: '+sig)
        before[str(path.relative_to(ROOT))] = row['cache_sha256']
        batch = read(path)
        require(batch['status'] == row['status'] == 'fetched', 'Required request failed: '+sig)
        require(batch['signature'] == sig and batch['request_url'] == row['request_url']
                and batch['version'] == acquire.VERSION
                and batch.get('parser_schema') == row.get('parser_schema') == acquire.PARSER_SCHEMA
                and batch.get('response_format_verified') is True,
                'Cached request identity/parser contract mismatch: '+sig)
        require(batch['raw_sha256'] == row['raw_sha256']
                and bool(re.fullmatch('[a-f0-9]{64}', batch['raw_sha256'])), 'Raw response hash malformed')
        require(batch['raw_count'] == row['raw_count'] and len(batch['items']) == row['eligible_items'],
                'Request counts mismatch: '+sig)
        require(bool(batch['possibly_capped']) == bool(row['possibly_capped']) == (batch['raw_count'] >= 100),
                'RSS ceiling flag mismatch: '+sig)
        require(batch['raw_count'] == len(batch['items'])+sum(batch['discarded'].values()),
                'Parsed and discarded RSS counts do not reconcile: '+sig)
        tokens = set()
        for context in row['contexts']:
            token = context_token(context['job'], context['kind'], context.get('parent_signature'))
            require(token not in tokens, 'Duplicate context: '+sig)
            tokens.add(token)
            require(request_url(context['job']) == row['request_url'], 'Context request URL mismatch: '+sig)
            require(context['job'][4] == batch['lower_date'] == row['lower_date']
                    and context['job'][5] == batch['upper_date_exclusive'] == row['upper_date_exclusive'],
                    'Cache interval mismatch: '+sig)
        require(tokens, 'Request has no contexts: '+sig)
        actual_contexts[sig] = tokens
        for item in batch['items']:
            pub = dt.datetime.fromisoformat(item['published_at'])
            require(pub.tzinfo is not None and pub.utcoffset() == dt.timedelta(0)
                    and batch['lower_date'] <= pub.date().isoformat() < batch['upper_date_exclusive'],
                    'Cached item publication outside request interval: '+sig)
            require(item['title'].strip() and item['url'].startswith('https://')
                    and not ROLLING.search(item['title']), 'Invalid cached headline: '+sig)
        batches[sig] = batch
        cached_items += len(batch['items'])
    weekly, prefixes = expected_initial_contexts()
    expected = {}

    def add(job, kind, parent=None):
        url = request_url(job)
        sig = hashlib.sha256((acquire.VERSION+'\n'+url).encode()).hexdigest()
        expected.setdefault(sig, set()).add(context_token(job, kind, parent))
        return sig

    for job in weekly:
        add(job, 'weekly')
    for parent, child in prefixes:
        parent_sig = hashlib.sha256((acquire.VERSION+'\n'+request_url(parent)).encode()).hexdigest()
        add(child, 'cutoff_prefix', parent_sig)
    initial_signatures = set(expected)
    missing_initial = initial_signatures-set(by_signature)
    require(not missing_initial, 'Missing catalogue weekly/cutoff requests: '+str(len(missing_initial)))
    for sig in sorted(initial_signatures):
        if not batches[sig]['possibly_capped']:
            continue
        for job, _, _ in list(expected[sig]):
            lower, upper = map(dt.date.fromisoformat, job[4:])
            if upper-lower <= dt.timedelta(days=1):
                continue
            for offset in range((upper-lower).days):
                day = lower+dt.timedelta(days=offset)
                add((*job[:4], day.isoformat(), (day+dt.timedelta(days=1)).isoformat()),
                    'daily_refinement', sig)
    require(expected == actual_contexts, 'Actual context inventory differs from independent required catalogue/refinement set')
    daily_caps = sorted(sig for sig, batch in batches.items() if batch['possibly_capped']
                        and dt.date.fromisoformat(batch['upper_date_exclusive'])
                        -dt.date.fromisoformat(batch['lower_date']) == dt.timedelta(days=1))
    require(coverage['unique_query_urls'] == len(requests)
            and coverage['remaining_daily_caps'] == len(daily_caps)
            and sorted(coverage['remaining_daily_cap_signatures']) == daily_caps
            and coverage['failed_requests'] == 0
            and coverage['weekly_contexts'] == len(weekly)
            and coverage['cutoff_prefix_contexts'] == len(prefixes), 'Coverage summary does not match actual requests')
    # Raw/ready replay is implemented below after the acquisition inventory so
    # each retained source has an independently established response lineage.
    return {'coverage': coverage, 'plan': plan,
            'tool_hashes': tool_hashes, 'helper_hashes': helper_hashes,
            'requests': requests, 'batches': batches,
            'before': before, 'weekly_contexts': len(weekly), 'prefix_contexts': len(prefixes),
            'catalog_contexts': sum(map(len, TOPICS.values())), 'daily_caps': daily_caps,
            'cached_items': cached_items}


def configured_priority(items):
    """Independently replay the declared ranking policy, using its bound lists."""
    from digest import TIER1, SPAM
    from ready_feeds import CAPS

    def score(item):
        source = item['src'].lower()
        tier = (0 if any(value in source for value in TIER1)
                else 2 if any(value in source for value in SPAM) else 1)
        published = dt.datetime.fromisoformat(item['published_at'].replace('Z', '+00:00'))
        require(published.tzinfo is not None, 'Naive priority ranking clock')
        return tier, -published.astimezone(UTC).timestamp()

    chosen = set()
    for topic, cap in CAPS.items():
        candidates = sorted((item for item in items if item['topics'][0] == topic), key=score)
        chosen.update(item['id'] for item in candidates[:cap])
    return [item for item in items if item['id'] in chosen and is_reuters(item)]


def is_reuters(item):
    return (item['src'].casefold().strip() in {'reuters', 'reuters.com'}
            or item['title'].casefold().endswith(' - reuters'))


def configured_guard(item, stamp):
    # Replay the configured conservative exclusion policy. The factual calendar
    # and unguarded claims still require the separate chronology/editorial review.
    from ready_feeds import RELEASE_GUARDS, PREVIEW as GUARD_PREVIEW
    title, published = item['title'], item['published_at'][:10]
    if ('2025-04-09' <= published < '2025-04-16' and stamp < '2025-04-16'
            and re.search(r'(?=.*Nvidia)(?=.*5[.,]5)(?=.*charge)', title, re.I)):
        disclosure = re.search(r'\bNvidia\b(?P<before>[^,;:.]{0,60}?)\b(?:expects?|discloses?|reports?|flags?|warns?)\b', title, re.I)
        if disclosure:
            disclosure_prefix = re.split(r'[;,:]|\b(?:but|while|whereas|although|yet)\b',
                                         title[:disclosure.end('before')], flags=re.I)[-1]
            if not GUARD_PREVIEW.search(disclosure_prefix) and not re.search(r'\bto\s*$', disclosure_prefix, re.I):
                return 'Nvidia expected $5.5 billion charge disclosure unavailable until 2025-04-16 report'
    clean = re.sub(r'\b(?:better|worse|more|less|higher|lower|stronger|weaker|faster|slower)\s+than\s+expected\b|\bas\s+expected\b',
                   '', title, flags=re.I)
    clean = re.sub(r'\b(?:mocniej|słabiej|lepiej|gorzej|więcej|mniej|wyżej|niżej)\s+(?:od|niż)\s+(?:oczekiwań|oczekiwano|prognoz(?:owano)?)',
                   '', clean, flags=re.I)
    polish_preview = r'\b(?:prognoz|oczekuj|oczekiw|może|moze|mogą|moga|mają|maja|powinn|będ|beda|wzrosn|spadn|spodziew|prawdopodob|zapowied|szacuj)'
    preview = bool(GUARD_PREVIEW.search(clean) or re.search(polish_preview, clean, re.I))
    actions = (r'holds?|held|keeps?|kept|leaves?|left|cuts?|raises?|raised|maintains?|maintained|falls?|fell|falling|'
               r'rises?|rose|rising|cools?|cooled|grows?|grew|contracts?|contracted|shrinks?|shrank|surges?|surged|'
               r'slows?|slowed|drops?|dropped|jumps?|jumped|pauses?|paused|announces?|announced|unveils?|unveiled|'
               r'exempts?|exempted|down|up|wzrosł\w*|spadł\w*|utrzyma\w*|pozostawi\w*')

    def completed(label):
        action = actions
        if label == 'RBA April minutes':
            subject = r'minutes'
            action = r'shows?|showed|reveals?|revealed|says?|said|signals?|indicates?|indicated|suggests?|suggested|released|published'
        elif label.startswith('RBA'): subject = r'RBA|Reserve Bank of Australia'
        elif label.startswith('ECB'): subject = r'ECB|European Central Bank'
        elif label.startswith('NBP'): subject = r'NBP|RPP|Glapiński|central bank'
        elif 'ISM' in label: subject = r'ISM|Institute for Supply Management'
        elif 'JOLTS' in label: subject = r'JOLTS|job openings'
        elif 'ADP' in label: subject = r'ADP|private payrolls|private employment'
        elif 'payrolls' in label: subject = r'payrolls?|nonfarm|employment|jobs report|hiring'
        elif 'CPI' in label or 'inflation' in label: subject = r'CPI|inflation|consumer prices|PPI|producer prices'
        elif 'PPI' in label: subject = r'PPI|producer prices|wholesale prices'
        elif 'GDP' in label: subject = r'GDP|gross domestic product|economy'
        elif 'PCE' in label: subject = r'PCE|personal consumption expenditure|personal spending|personal income'
        elif 'retail sales' in label: subject = r'retail sales|sprzeda[żz] detal\w*'
        elif label == 'China March trade': subject = r'exports?|imports?|trade surplus|trade data'
        elif label == 'China March activity': subject = r'retail sales|industrial output|industrial production|fixed.asset investment|home prices'
        elif 'LPR' in label: subject = r'LPR|loan prime rates?|benchmark lending rates?'
        elif 'PMI' in label: subject = r'PMI|purchasing managers|factory activity|business activity'
        elif 'wages' in label: subject = r'wages|salary|employment|wynagrodz\w*|zatrudn\w*'
        elif 'industry' in label: subject = r'industrial output|industrial production|industry|produkcj\w*|przemysł\w*'
        elif 'employment' in label: subject = r'jobs|employment|unemployment|hiring'
        elif 'tariff' in label.lower() or 'electronics' in label.lower(): subject = r'Trump|U\.?S\.?'
        else:
            return False
        pairs = re.finditer(r'\b(?:'+subject+r')\b(?P<before>(?:(?!\b(?:but|while|whereas|although|yet|and)\b)[^.;:]){0,100}?)\b(?:'+action+r')\b', clean, re.I)
        for pair in pairs:
            own_clause = re.split(r'[;,:]|\b(?:but|while|whereas|although|yet)\b',
                                  clean[:pair.end('before')], flags=re.I)[-1]
            countries = {'US': r'\b(?:U\.?S\.?|American)\b', 'China': r'\b(?:China|Chinese)\b',
                         'Australia': r'\b(?:Australia|Australian|ABS)\b',
                         'Poland': r'\b(?:Poland|Polish|Polsk\w*|GUS)\b'}
            country = next((name for name in countries if label.startswith(name)), None)
            implicit_us = any(word in label for word in ['ISM', 'JOLTS', 'ADP', 'payrolls'])
            if country and not (country == 'US' and implicit_us) and not re.search(countries[country], own_clause, re.I):
                continue
            if (not GUARD_PREVIEW.search(own_clause)
                    and not re.search(r'\b(?:to|will|would|could|should|may|might)\s*$', own_clause, re.I)
                    and not re.search(polish_preview, own_clause, re.I)):
                return True
        return False

    for label, start, eligible, pattern in RELEASE_GUARDS:
        if (start <= published < eligible and stamp < eligible and re.search(pattern, title, re.I)
                and (not preview or completed(label))):
            return label+' actual may precede scheduled release; excluded until '+eligible+' report'
    return None


def git_blob_sha(raw):
    return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()


def verify_public_rss_transports(state, inventoried_names):
    """Independently bind each imported cache to reviewed code and GitHub output."""
    import fetch_news as acquire
    coverage = state['coverage']
    rows = coverage.get('public_rss_ingestions', [])
    if not rows:
        require(not list((ROOT/'audit').glob('news_public_rss_ingestion_*.json')),
                'Public RSS ingestion receipt omitted from coverage')
        return {'batches': 0, 'records': 0, 'proof_files': [], 'required_files': set()}
    importer_path = 'tools/import_public_rss.py'
    require(coverage.get('transport_tool_sha256') == {importer_path: sha(safe_path(importer_path))},
            'Current public RSS importer code binding required')
    remote_name = 'audit/news_public_rss_independent_remote_binding.json'
    remote_path = safe_path(remote_name)
    remote = read(remote_path)
    require(remote.get('status') == 'passed' and remote.get('repository') == 'marcinzieba4-bot/DailyDigest_Markets',
            'Independent GitHub run/job/artifact/tree binding required')
    runs = {row['id']: row for row in remote['runs']}
    require(len(runs) == len(remote['runs']), 'Duplicate independently observed CI runs')
    required = {importer_path, remote_name}
    actual_receipts = {str(p.relative_to(ROOT)) for p in (ROOT/'audit').glob('news_public_rss_ingestion_*.json')}
    names = [row['path'] for row in rows]
    require(len(names) == len(set(names)) and set(names) == actual_receipts,
            'Public RSS coverage omits or duplicates an ingestion receipt')
    proof_files = []
    imported_signatures, used_runs = set(), set()
    expected_by_signature = {row['signature']: row for row in state['requests']}
    baseline_runner = baseline_workflow = None
    for descriptor in rows:
        path = safe_path(descriptor['path'])
        require(sha(path) == descriptor['sha256'], 'Public RSS ingestion receipt changed')
        receipt = read(path)
        require(receipt['status'] == 'imported' and receipt['failures'] == 0
                and receipt['parser_schema'] == acquire.PARSER_SCHEMA
                and receipt['exact_four_files_verified'] is True
                and receipt['importer_sha256'] == sha(ROOT/importer_path)
                and receipt['records'] == descriptor['records'] and receipt['head'] == descriptor['head'],
                'Public RSS ingestion summary/current importer mismatch')
        batch = (ROOT/receipt['batch']).resolve()
        require(batch.is_relative_to(ROOT/'work') and batch.is_dir(), 'Invalid public RSS batch path')
        required.add(descriptor['path'])
        required.update(str(p.relative_to(ROOT)) for p in batch.rglob('*') if p.is_file())
        manifest = read(batch/'code_manifest.json')
        binding = read(batch/'run_binding.json')
        require(set(manifest) == RSS_CI_FILES and binding['head'] == receipt['head'],
                'Exact reviewed RSS batch source inventory/head mismatch')
        source_bytes = {}
        for name, entry in manifest.items():
            source = (batch/'source'/name).resolve()
            require(source.is_relative_to(batch) and source.is_file(), 'Invalid reviewed RSS source path')
            raw = source.read_bytes()
            require(hashlib.sha256(raw).hexdigest() == entry['sha256'] and len(raw) == entry['bytes'],
                    'Reviewed RSS source byte/hash mismatch')
            source_bytes[name] = raw
        fetcher_name = 'corrections/2025-04/rss_recovery/fetch_news.py'
        runner_name = 'corrections/2025-04/rss_recovery/run.py'
        input_name = 'corrections/2025-04/rss_recovery/input.json'
        workflow_name = '.github/workflows/apr2025-rss-recovery.yml'
        require(source_bytes[fetcher_name] == (ROOT/'tools/fetch_news.py').read_bytes(),
                'Executed RSS parser differs from accepted current source')
        runner = source_bytes[runner_name]
        workflow = re.sub(rb'(?m)^(\s*part:) \[[0-9, ]+\]$', rb'\1 [MATRIX]', source_bytes[workflow_name])
        if baseline_runner is None:
            baseline_runner, baseline_workflow = runner, workflow
        require(runner == baseline_runner and workflow == baseline_workflow,
                'RSS runner or workflow behavior changed between reviewed batches')
        # Safety properties of the reviewed runner/workflow remain explicit;
        # only public fixed-host query jobs can be executed.
        require(b"u.hostname=='news.google.com'" in runner and b"u.path=='/rss/search'" in runner
                and b'persist-credentials: false' in workflow and b'contents: read' in workflow,
                'Reviewed public RSS workflow/runner constraints missing')
        inputs = json.loads(source_bytes[input_name])
        part_size = inputs.get('part_size', 750)
        jobs = inputs['jobs']
        require(0 < len(jobs) <= 15000 and 0 < part_size <= 1000, 'Invalid public RSS input partition size')
        wanted_all = {}
        for item in jobs:
            sig = item['signature']
            require(sig in expected_by_signature and sig not in wanted_all
                    and item['request_url'] == expected_by_signature[sig]['request_url']
                    and request_url(item['job']) == item['request_url']
                    and interval_key(item['job']) in {interval_key(c['job']) for c in expected_by_signature[sig]['contexts']},
                    'Public RSS recovery input is outside required acquisition query inventory')
            wanted_all[sig] = item
        transported = {}
        for artifact in receipt['artifacts']:
            run_id = artifact['run_id']
            require(run_id in runs, 'RSS run missing independent remote binding')
            run = runs[run_id]
            used_runs.add(run_id)
            require(run['head_sha'] == receipt['head'] == artifact['commit_sha']
                    and run['status'] == 'completed' and run['conclusion'] == 'success'
                    and run['event'] == 'pull_request'
                    and run['path'] == workflow_name
                    and run['repository_full_name'] == 'marcinzieba4-bot/DailyDigest_Markets',
                    'Public RSS actual run/head/status mismatch')
            tree = run['tree']
            require(tree.get('truncated') is False, 'Truncated independent recovery Git tree')
            blobs = {row['path']: row for row in tree['files']}
            require(set(blobs) == RSS_CI_FILES | {'README.md'}, 'Unexpected files in isolated recovery commit')
            for name, raw in source_bytes.items():
                require(blobs[name]['sha'] == git_blob_sha(raw) and blobs[name]['size'] == len(raw),
                        'Actual Git tree does not contain reviewed RSS bytes: '+name)
            actual_job = next((row for row in run['jobs'] if row['id'] == artifact['job_id']), None)
            require(actual_job and actual_job['run_id'] == artifact['job_run_id'] == run_id
                    and actual_job['head_sha'] == receipt['head'] and actual_job['status'] == 'completed'
                    and actual_job['conclusion'] == 'success', 'Actual recovery job binding mismatch')
            actual_artifact = next((row for row in run['artifacts'] if row['id'] == artifact['artifact_id']), None)
            archive_path = (batch/artifact['file']).resolve()
            require(archive_path.is_relative_to(batch) and archive_path.is_file(), 'Invalid RSS artifact path')
            digest = sha(archive_path)
            require(actual_artifact and actual_artifact['name'] == artifact['artifact_name']
                    and actual_artifact['size_in_bytes'] == artifact['artifact_size_bytes'] == archive_path.stat().st_size
                    and actual_artifact['digest'] == 'sha256:'+digest
                    and actual_artifact['workflow_run']['id'] == run_id
                    and actual_artifact['workflow_run']['head_sha'] == receipt['head']
                    and digest == artifact['artifact_sha256'], 'Actual GitHub artifact digest/head binding mismatch')
            with zipfile.ZipFile(archive_path) as archive:
                require(archive.testzip() is None and set(archive.namelist()) == {'records.json', 'receipt.json'},
                        'RSS artifact ZIP members/CRC mismatch')
                record_raw, part_receipt_raw = archive.read('records.json'), archive.read('receipt.json')
            part_receipt, part_records = json.loads(part_receipt_raw), json.loads(record_raw)
            part = artifact['part']
            wanted = {item['signature'] for item in jobs[part*part_size:(part+1)*part_size]}
            require(part >= 0 and wanted and set(part_records) == wanted
                    and part_receipt['part'] == part and part_receipt['part_size'] == part_size
                    and part_receipt['records'] == len(wanted) == artifact['records']
                    and part_receipt['failures'] == 0 and part_receipt['parser_schema'] == acquire.PARSER_SCHEMA
                    and part_receipt['input_sha256'] == manifest[input_name]['sha256'] == receipt['input_sha256']
                    and part_receipt['fetcher_sha256'] == manifest[fetcher_name]['sha256'] == receipt['fetcher_sha256']
                    and part_receipt['runner_sha256'] == manifest[runner_name]['sha256'] == receipt['runner_sha256']
                    and part_receipt['records_sha256'] == hashlib.sha256(record_raw).hexdigest() == artifact['records_sha256']
                    and hashlib.sha256(part_receipt_raw).hexdigest() == artifact['receipt_sha256'],
                    'Executed public RSS partition/input/parser/output hash proof mismatch')
            for sig, record in part_records.items():
                require(sig not in transported and record == state['batches'][sig],
                        'Actual public RSS output differs from accepted cache')
                transported[sig] = hashlib.sha256(json.dumps(
                    record, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
        require(set(transported) == set(wanted_all) and len(transported) == receipt['records'],
                'Public RSS artifacts do not cover exact whole reviewed input')
        cache_rows = {row['signature']: row for row in receipt['cache_files']}
        require(len(cache_rows) == len(receipt['cache_files']) and set(cache_rows) == set(transported),
                'Imported cache receipt does not cover actual transported records')
        for sig, record_json_sha256 in transported.items():
            cache_row = cache_rows[sig]
            cache_path = safe_path(cache_row['path'])
            require(cache_row['path'] == expected_by_signature[sig]['cache_path']
                    and sha(cache_path) == cache_row['sha256'] and cache_path.stat().st_size == cache_row['bytes']
                    and record_json_sha256 == cache_row['record_json_sha256'],
                    'Imported RSS cache bytes/hash changed')
        require(not imported_signatures.intersection(transported), 'Duplicate independently imported RSS query')
        imported_signatures.update(transported)
        proof_files.append({'path': descriptor['path'], 'sha256': sha(path),
                            'records': len(transported), 'head': receipt['head']})
    require(used_runs == set(runs), 'Independent RSS remote binding contains missing/unused runs')
    require(required <= inventoried_names, 'Replay inventory omits reviewed RSS transport inputs/proofs: '
            +str(sorted(required-inventoried_names)))
    return {'batches': len(rows), 'records': len(imported_signatures), 'proof_files': proof_files,
            'required_files': required, 'remote_binding_sha256': sha(remote_path),
            'importer_sha256': sha(ROOT/importer_path)}


def verify_priority_metadata_payloads(canonical, inventoried_names):
    """Verify captured initial metadata payloads without touching the growing cache."""
    import import_public_metadata as importer
    names = sorted(name for name in inventoried_names
                   if name.startswith('audit/metadata_ci_ingestion_') and name.endswith('.json'))
    require(names, 'Captured priority metadata recovery proof missing from replay inventory')
    required = {'tools/import_public_metadata.py'}
    mappings, proofs = {}, []
    for name in names:
        path = safe_path(name)
        saved = read(path)
        batch = (ROOT/saved['files']).resolve()
        require(batch.is_relative_to(ROOT/'work') and batch.is_dir(), 'Invalid priority metadata capture directory')
        required.add(name)
        required.update(str(p.relative_to(ROOT)) for p in batch.rglob('*') if p.is_file())
        records, proof, _, _ = importer.verify(batch)  # Default verification is read-only.
        for key in ['workflow_run_id', 'workflow_job_id', 'commit_sha', 'input_sha256',
                    'resolver_sha256', 'runner_sha256', 'workflow_sha256', 'output_sha256',
                    'payload_sha256', 'job_log_sha256', 'records', 'failures',
                    'all_hash_checks_passed', 'requested_url_set_exact', 'exact_head_four_files_verified']:
            require(saved.get(key) == proof.get(key), 'Captured priority metadata receipt differs: '+key)
        resolver = batch/'source/corrections/2025-04/recovery/resolve_news_url.py'
        require(resolver.read_bytes() == (ROOT/'posthoc/resolve_news_url.py').read_bytes(),
                'Priority metadata used another resolver than the reviewed current source')
        for url, row in records.items():
            if url in mappings:
                require(mappings[url]['canonical_url'] == row['canonical_url'], 'Conflicting captured priority mappings')
            mappings[url] = row
        proofs.append({'path': name, 'sha256': sha(path), 'records': len(records),
                       'run_id': proof['workflow_run_id'], 'head': proof['commit_sha']})
    require(required <= inventoried_names, 'Replay inventory omits priority metadata source/code/proofs')
    for url, row in canonical.items():
        require(url in mappings and row == mappings[url],
                'Immutable priority canonical record does not replay from captured verified payload')
    return {'batches': len(names), 'captured_mappings': len(mappings),
            'priority_mappings_verified': len(canonical), 'receipts': proofs,
            'importer_sha256': sha(ROOT/'tools/import_public_metadata.py')}


def verify_ready_and_replay(state, checks):
    from topics import TOPICS
    coverage = state['coverage']
    ready = read(ROOT/'audit/news_ready_audit.json')
    inventory = read(ROOT/'audit/news_replay_inventory.json')
    require(inventory.get('complete') is True and inventory.get('status') == 'complete',
            'Complete replay inventory required')
    files = inventory['files']
    names = [row['path'] for row in files]
    require(len(set(names)) == len(files) == inventory['file_count'], 'Replay inventory duplicates/count mismatch')
    require(inventory['total_bytes'] == sum(row['bytes'] for row in files), 'Replay inventory byte summary mismatch')
    for row in files:
        path = safe_path(row['path'])
        require(path.stat().st_size == row['bytes'] and sha(path) == row['sha256'],
                'Replay input drifted: '+row['path'])
        state['before'][row['path']] = row['sha256']
    required = {row['cache_path'] for row in state['requests']}
    required.update(ACQUISITION_TOOLS+HELPER_TOOLS)
    required.update(['audit/news_coverage.json', 'audit/news_query_plan.json',
                     'audit/news_ready_audit.json', 'audit/news_metadata_request_plan.json',
                     'audit/canonical_priority_urls.json'])
    for date in DATES:
        stamp = date.isoformat()
        required.update([f'work/unreviewed_feeds/{stamp}.json.gz', f'feeds/{stamp}.json.gz',
                         f'audit/news_provenance/{stamp}.json.gz', f'audit/news_ready_{stamp}.json'])
    require(required <= set(names), 'Replay inventory omits required files: '+str(sorted(required-set(names))))
    transport = verify_public_rss_transports(state, set(names))
    require(ready.get('status') == 'passed' and ready.get('report_dates') == len(DATES)
            and ready.get('missing_dates') == [] and ready.get('failed_query_windows') == 0
            and ready.get('unresolved_priority_records') == 0 and ready.get('failed_requests') == 0
            and ready.get('unresolved_priority_urls') == 0, 'Complete passing readiness receipt required')
    require(ready['coverage_sha256'] == sha(ROOT/'audit/news_coverage.json')
            and ready['screening_tool_sha256'] == state['tool_hashes']['tools/ready_feeds.py'],
            'Readiness coverage/code binding mismatch')
    canonical_path = safe_path(ready['canonical_cache_path'])
    require(ready['canonical_cache_sha256'] == sha(canonical_path), 'Priority canonical snapshot drifted')
    canonical = read(canonical_path)
    metadata_plan_path = ROOT/'audit/news_metadata_request_plan.json'
    require(ready['metadata_plan_sha256'] == sha(metadata_plan_path), 'Priority request plan drifted')
    metadata_plan = read(metadata_plan_path)
    require(metadata_plan.get('ranking_helper_sha256') == state['helper_hashes']['tools/digest.py'],
            'Priority plan does not bind the current full-timestamp ranking helper')
    require(len(set(metadata_plan['urls'])) == len(metadata_plan['urls']) == metadata_plan['url_count']
            and set(metadata_plan['urls']) == set(canonical), 'Priority metadata snapshot URL set mismatch')
    for url, entry in canonical.items():
        parsed = urllib.parse.urlsplit(entry.get('canonical_url', ''))
        require(not entry.get('error') and parsed.scheme in {'http', 'https'} and parsed.hostname
                and parsed.hostname.lower() not in {'google.com', 'www.google.com', 'news.google.com',
                                                    'accounts.google.com', 'consent.google.com'}
                and '/sorry/' not in parsed.path.lower() and entry.get('publisher_body_fetched') is False,
                'Unresolved/invalid priority canonical metadata')
        match = re.search(r'(\d{4}-\d{2}-\d{2})/?$', parsed.path)
        require(entry.get('canonical_date') == (match.group(1) if match else None),
                'Canonical date inconsistent with resolved Reuters path')
    metadata_transport = verify_priority_metadata_payloads(canonical, set(names))
    date_coverage = {row['date']: row for row in coverage['dates']}
    date_ready = {row['date']: row for row in ready['rows']}
    date_metadata = {row['date']: row for row in metadata_plan['dates']}
    expected_dates = {date.isoformat() for date in DATES}
    require(set(date_coverage) == set(date_ready) == set(date_metadata) == expected_dates
            and len(coverage['dates']) == len(ready['rows']) == len(metadata_plan['dates']) == len(DATES),
            'Missing/duplicate dated coverage/readiness rows')
    raw_hashes, final_hashes, provenance_hashes, report_rows = {}, {}, {}, {}
    all_priority_urls = set()
    raw_total = final_total = excluded_total = provenance_edges = 0
    for date in DATES:
        stamp = date.isoformat()
        cutoff = dt.datetime.combine(date, dt.time(), UTC)
        raw_path = ROOT/f'work/unreviewed_feeds/{stamp}.json.gz'
        final_path = ROOT/f'feeds/{stamp}.json.gz'
        ledger_path = ROOT/f'audit/news_provenance/{stamp}.json.gz'
        receipt_path = ROOT/f'audit/news_ready_{stamp}.json'
        raw, final, ledger, receipt = map(read, [raw_path, final_path, ledger_path, receipt_path])
        raw_hashes[stamp], final_hashes[stamp], provenance_hashes[stamp] = map(sha, [raw_path, final_path, ledger_path])
        row = date_coverage[stamp]
        require(row['raw_feed_sha256'] == row['feed_sha256'] == raw_hashes[stamp]
                and row['raw_feed_path'] == str(raw_path.relative_to(ROOT))
                and row['provenance_path'] == str(ledger_path.relative_to(ROOT))
                and row['provenance_sha256'] == provenance_hashes[stamp], 'Raw/provenance receipt drift: '+stamp)
        for feed in [raw, final]:
            require(feed['date'] == stamp and dt.datetime.fromisoformat(feed['cutoff_utc']) == cutoff
                    and feed.get('query_upper_bound_enforced') is True and feed['fails'] == [],
                    'Own-date feed identity/cutoff/failure mismatch: '+stamp)
            ids = [item['id'] for item in feed['items']]
            require(len(ids) == len(set(ids)), 'Duplicate source ID: '+stamp)
            for item in feed['items']:
                pub = dt.datetime.fromisoformat(item['published_at'])
                require(pub.tzinfo is not None and cutoff-dt.timedelta(days=AGES[item['cat']]) <= pub < cutoff,
                        'Own-date source age/cutoff violation: '+stamp+' '+item['id'])
        require([item['id'] for item in raw['items']] == [f'n{n:04d}' for n in range(1, len(raw['items'])+1)],
                'Raw deterministic IDs not sequential: '+stamp)
        used = sorted(row['signature'] for row in state['requests']
                      if any(eligible_context(context['job'], date) for context in row['contexts']))
        require(row['eligible_query_signatures'] == used and row['eligible_queries'] == len(used),
                'Date eligible-query inventory mismatch: '+stamp)
        expected_raw, expected_ledger = independent_merge(date, state['requests'], state['batches'])
        require(raw['items'] == expected_raw, 'Independent raw merge differs: '+stamp)
        require(ledger['date'] == stamp and dt.datetime.fromisoformat(ledger['cutoff_utc']) == cutoff
                and ledger['records'] == expected_ledger, 'Per-record response lineage replay differs: '+stamp)
        priority = configured_priority(raw['items'])
        priority_ids = {item['id'] for item in priority}
        all_priority_urls.update(item['url'] for item in priority)
        meta_row = date_metadata[stamp]
        require(meta_row['raw_feed_sha256'] == raw_hashes[stamp] and meta_row['raw_items'] == len(raw['items'])
                and meta_row['priority_reuters_records'] == len(priority)
                and meta_row['priority_ids'] == [item['id'] for item in priority],
                'Independent configured priority selection differs: '+stamp)
        expected_final, expected_excluded = [], []
        for item in raw['items']:
            metadata = canonical.get(item['url'], {}) if is_reuters(item) else {}
            day = metadata.get('canonical_date')
            reason = configured_guard(item, stamp)
            if day and day >= stamp:
                reason = 'canonical_date_at_or_after_report; original pre-cutoff availability unverified; conservatively excluded'
            elif item['id'] in priority_ids and not day:
                reason = 'resolved priority canonical URL has no publication date; conservatively excluded'
            if reason:
                expected_excluded.append({**item, 'reason': reason, 'metadata': metadata})
            else:
                expected_final.append({**item, 'canonical_url': metadata['canonical_url'], 'canonical_date': day}
                                      if day else item)
        require(final['items'] == expected_final and receipt['excluded_items'] == expected_excluded,
                'Independent readiness partition/metadata replay differs: '+stamp)
        require({key: value for key, value in final.items() if key not in {'items', 'canonical_screening'}}
                == {key: value for key, value in raw.items() if key != 'items'},
                'Non-screening feed headers changed: '+stamp)
        require(receipt['status'] == 'ready' and receipt['date'] == stamp
                and receipt['unreviewed_sha256'] == raw_hashes[stamp]
                and receipt['ready_sha256'] == receipt['feed_sha256'] == final_hashes[stamp]
                and receipt['metadata_lookup_failures'] == 0 and receipt['unresolved_priority_ids'] == []
                and receipt['surviving_ids_preserved'] is True and receipt['query_upper_bound_enforced'] is True
                and receipt['priority_reuters_records'] == len(priority)
                and receipt['unreviewed_items'] == len(raw['items'])
                and receipt['items'] == receipt['ready_items'] == len(final['items'])
                and receipt['excluded_count'] == len(expected_excluded)
                and {key: value for key, value in receipt.items() if key != 'excluded_items'} == date_ready[stamp],
                'Per-date readiness receipt differs from actual frozen files: '+stamp)
        require(set(topic for item in final['items'] for topic in item['topics']) == set(TOPICS),
                'Expected topic absent from final feed: '+stamp)
        require(row['items'] == len(raw['items']) and row['failed_query_windows'] == 0,
                'Coverage date record count/failure mismatch: '+stamp)
        raw_total += len(raw['items'])
        final_total += len(final['items'])
        excluded_total += len(expected_excluded)
        edges = sum(map(len, expected_ledger.values()))
        provenance_edges += edges
        report_rows[stamp] = {'raw_records': len(raw['items']), 'final_records': len(final['items']),
                              'excluded_records': len(expected_excluded), 'provenance_edges': edges,
                              'raw_sha256': raw_hashes[stamp], 'final_sha256': final_hashes[stamp],
                              'provenance_sha256': provenance_hashes[stamp],
                              'independent_raw_replay_passed': True, 'screening_partition_replay_passed': True}
        print(stamp, len(raw['items']), 'raw;', len(final['items']), 'ready; independent replay passed', flush=True)
    require(all_priority_urls == set(canonical), 'Metadata snapshot omits expected/contains unused priority URLs')
    require(raw_total == coverage['own_date_records'] == ready['raw_own_date_records']
            and final_total == ready['ready_own_date_records'] and excluded_total == ready['excluded_records']
            and raw_total == final_total+excluded_total, 'Monthly source counts do not reconcile')
    for name, value in state['before'].items():
        require(sha(safe_path(name)) == value, 'Input changed during independent QA: '+name)
    checks.extend([
        {'name': 'independently_reconstructed_catalog_weekly_and_all_cutoff_prefix_contexts', 'passed': True,
         'catalog_contexts': state['catalog_contexts'], 'weekly_contexts': state['weekly_contexts'],
         'cutoff_prefix_contexts': state['prefix_contexts']},
        {'name': 'all_capped_multiday_contexts_have_daily_children_and_residual_caps_disclosed',
         'passed': True, 'remaining_daily_caps': len(state['daily_caps'])},
        {'name': 'all_physical_response_cache_identity_counts_and_hashes_checked', 'passed': True,
         'unique_query_urls': len(state['requests']), 'parsed_records': state['cached_items']},
        {'name': 'independent_raw_merge_and_every_record_query_lineage_replayed', 'passed': True,
         'reports': len(DATES), 'raw_records': raw_total, 'provenance_edges': provenance_edges},
        {'name': 'configured_priority_canonical_and_guard_partition_replayed_without_id_changes',
         'passed': True, 'final_records': final_total, 'excluded_records': excluded_total},
        {'name': 'complete_replay_inventory_hashes_verified_and_all_inputs_stable', 'passed': True,
         'inventory_files': len(files), 'unchanged_inputs': len(state['before'])},
        {'name': 'public_rss_transport_reviewed_git_bytes_run_job_server_artifact_digest_and_cache_proofs',
         'passed': True, 'batches': transport['batches'], 'recovered_query_urls': transport['records']},
        {'name': 'captured_canonical_metadata_payload_replays_every_priority_snapshot_record',
         'passed': True, 'batches': metadata_transport['batches'],
         'priority_mappings_verified': metadata_transport['priority_mappings_verified']}])
    return {'status': 'passed', 'passed': True, 'report_count': len(DATES),
            'reviewer': '/root/apr_source_qa', 'checked_at_utc': dt.datetime.now(UTC).isoformat(),
            'coverage_sha256': sha(ROOT/'audit/news_coverage.json'),
            'query_plan_sha256': sha(ROOT/'audit/news_query_plan.json'),
            'replay_inventory_sha256': sha(ROOT/'audit/news_replay_inventory.json'),
            'news_ready_audit_sha256': sha(ROOT/'audit/news_ready_audit.json'),
            'acquisition_tool_sha256': state['tool_hashes'], 'helper_tool_sha256': state['helper_hashes'],
            'qa_script_sha256': sha(Path(__file__).resolve()),
            'raw_feed_sha256': raw_hashes, 'final_feed_sha256': final_hashes,
            'provenance_sha256': provenance_hashes,
            'request_catalog_complete': True, 'all_capped_multiday_refined': True,
            'request_upper_cutoff_enforced': True, 'own_date_replay_passed': True,
            'readiness_replay_passed': True, 'category_age_cutoffs_passed': True,
            'failed_requests': 0, 'unresolved_priority_records': 0,
            'inventory_files_verified': len(files), 'stable_input_files_verified': len(state['before']),
            'query_urls_verified': len(state['requests']), 'query_contexts_verified': sum(len(r['contexts']) for r in state['requests']),
            'parser_schema': state['coverage']['parser_schema'],
            'public_rss_transport': {key: value for key, value in transport.items() if key != 'required_files'},
            'priority_metadata_transport': metadata_transport,
            'raw_records': raw_total, 'final_records': final_total, 'excluded_records': excluded_total,
            'provenance_edges': provenance_edges, 'remaining_daily_caps': len(state['daily_caps']),
            'checks': checks, 'reports': report_rows,
            'limits': ['Retrieval-time historical search results are replayed; original historical RSS server responses and original publisher article bodies are not available.',
                       'Raw XML response hashes are bound as recorded by acquisition; original XML bytes are not retained, so this audit verifies the parsed-cache replay rather than reparsing those original bytes.',
                       'Remaining daily result caps and Google ranking/indexing prevent an exhaustive archive claim.',
                       'Canonical dates and configured release filters are conservatively replayed; independent narrative chronology and selected-claim review remain separate requirements.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures-only', action='store_true')
    parser.add_argument('--acquisition-only', action='store_true',
                        help='Check physical query acquisition only; do not write final source QA')
    parser.add_argument('--check-only', action='store_true', help='Validate all inputs without writing a review receipt')
    args = parser.parse_args()
    checks = fixture_checks()
    if args.fixtures_only:
        print(json.dumps({'passed': True, 'checks': checks}, indent=2))
        return
    state = verify_acquisition()
    if args.acquisition_only:
        print(json.dumps({'scope': 'Acquisition requests only; final source/readiness QA remains pending.',
                          'query_urls_verified': len(state['requests']),
                          'weekly_contexts': state['weekly_contexts'], 'prefix_contexts': state['prefix_contexts'],
                          'cached_parsed_items': state['cached_items'], 'remaining_daily_caps': len(state['daily_caps'])}))
        return
    result = verify_ready_and_replay(state, checks)
    path = ROOT/'checks/source_acquisition_independent_review.json'
    if not args.check_only:
        if path.exists():
            old = read(path)
            semantic = lambda value: {key: child for key, child in value.items() if key != 'checked_at_utc'}
            if semantic(old) == semantic(result):
                result = old
            else:
                path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
        else:
            path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({key: result[key] for key in ['passed', 'report_count', 'query_urls_verified',
                                                 'inventory_files_verified', 'raw_records', 'final_records',
                                                 'excluded_records', 'remaining_daily_caps']}))


if __name__ == '__main__':
    main()
