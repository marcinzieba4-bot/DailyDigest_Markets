"""Synthetic transport-schema self-QA only; no actual acquisition inputs read."""
from pathlib import Path
from collections import Counter
from unittest.mock import patch
import copy
import datetime as dt
import gzip
import hashlib
import importlib.util
import json
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


def digest(blob): return hashlib.sha256(blob).hexdigest()


def main():
    modules = {name: module('transport_test_' + name, ROOT / 'tools' / (name + '.py'))
               for name in ['render', 'build_artifacts', 'build_retail_page', 'build_source_inventory']}
    reviewer = module('transport_test_reviewer', ROOT / 'audit_work/review_final_artifacts.py')
    inventory = modules['build_source_inventory']; captured = {}; original = reviewer.replay_archive
    def capture(archive):
        if not captured: captured.update(copy.deepcopy(archive.values))
        return original(archive)
    with patch.object(reviewer, 'replay_archive', side_effect=capture):
        assert len(reviewer.negative_fixtures(modules)) == 55
    ledger_name = 'audit/news_physical_requests.jsonl'; cache_name = 'cache/news/fixture.json.gz'
    physical_name = 'audit_work/physical_source_inventory.json'; proof_name = inventory.PHYSICAL_REVIEW
    limitation_name = inventory.CAPTURE_LIMITATION; source_name = 'audit/independent_source_review.json'
    base_ledger = [json.loads(line) for line in captured[ledger_name].decode().splitlines()]
    base_cache = json.loads(gzip.decompress(captured[cache_name])); cases = []
    def rebind(files, ledger=None, cache=None, limitation=None):
        ledger = copy.deepcopy(base_ledger if ledger is None else ledger)
        cache = copy.deepcopy(base_cache if cache is None else cache)
        limitation = copy.deepcopy(json.loads(files[limitation_name]) if limitation is None else limitation)
        files[ledger_name] = ''.join(json.dumps(row) + '\n' for row in ledger).encode()
        files[cache_name] = gzip.compress(json.dumps(cache).encode(), mtime=0)
        files[limitation_name] = json.dumps(limitation).encode()
        physical = json.loads(files[physical_name]); physical['files'][0]['parsed_cache_sha256'] = digest(files[cache_name])
        files[physical_name] = json.dumps(physical).encode()
        proof = json.loads(files[proof_name]); proof.update(
            physical_attempts=len(ledger), received_attempt_bodies=sum(bool(row.get('raw_response_path')) for row in ledger),
            failed_attempts=sum(row.get('status') == 'failed' for row in ledger),
            ledger_sha256=digest(files[ledger_name]), physical_source_inventory_sha256=digest(files[physical_name]),
            recorded_missing_response_bodies=limitation['recorded_failed_attempts_missing_bodies'],
            discarded_error_body_limitations_sha256=digest(files[limitation_name]),
            legacy_signature_attempt_number_collisions=[{'signature': key[0], 'attempt': key[1], 'records': count}
                for key, count in Counter((row['signature'], row['attempt']) for row in ledger).items() if count > 1],
            attempt_starts_instrumentation_used=any('attempt_id' in row for row in ledger),
            attempt_starts_ledger_sha256=digest(files[inventory.ATTEMPT_STARTS]) if inventory.ATTEMPT_STARTS in files else None)
        proof['input_bindings'].update({ledger_name: digest(files[ledger_name]), limitation_name: digest(files[limitation_name])})
        if inventory.ATTEMPT_STARTS in files: proof['input_bindings'][inventory.ATTEMPT_STARTS] = digest(files[inventory.ATTEMPT_STARTS])
        files[proof_name] = json.dumps(proof).encode()
        source = json.loads(files[source_name]); source.update({key: proof[key] for key in inventory.TRANSPORT_FIELDS})
        source['prior_physical_review_sha256'] = digest(files[proof_name])
        source['input_bindings']['audit/news_coverage.json'] = digest(files['audit/news_coverage.json'])
        files[source_name] = json.dumps(source).encode()
        return files
    class Archive:
        def __init__(self, files): self.files = files
        def namelist(self): return list(self.files)
        def read(self, name): return self.files[name]
    def exercise(name, files, accepted=False):
        source = json.loads(files[source_name])
        try: reviewer.physical_source_dependencies(Archive(files), source); allowed = True
        except (ValueError, KeyError, TypeError): allowed = False
        assert allowed == accepted, 'Archive consumer: ' + name
        cases.append({'case': 'archive_' + name, 'accepted': allowed, 'passed': True})
        with tempfile.TemporaryDirectory(prefix='artifact_transport_synthetic_', dir=ROOT / 'work') as temporary:
            root = Path(temporary)
            for relative, blob in files.items():
                path = root / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(blob)
            with patch.object(inventory, 'ROOT', root):
                try: inventory.require_physical_ledger(source); allowed = True
                except (ValueError, KeyError, TypeError): allowed = False
                assert allowed == accepted, 'Filesystem consumer: ' + name
                if accepted and any(key.endswith('.http-error.gz') for key in files):
                    assert {key for key in files if key.endswith('.http-error.gz')} <= {path.relative_to(root).as_posix() for path in inventory.collect_paths()}
        cases.append({'case': 'filesystem_' + name, 'accepted': allowed, 'passed': True})
    exercise('current_schema_positive', rebind(copy.deepcopy(captured)), True)
    # A real legacy ordinal collision has two distinct starts and immutable
    # bodies; canonical cache count describes only its current successful run.
    historical = copy.deepcopy(base_ledger[0]); historical.update(status='failed', error_type='HTTPError', error='HTTP Error 503: synthetic',
        started_at_utc='1999-12-31T23:59:58+00:00', finished_at_utc='1999-12-31T23:59:59+00:00',
        raw_response_path='cache/rss_raw/attempts/synthetic.legacy.http-error.gz')
    error_body = b'Synthetic HTTP503 response only'; error_compressed = gzip.compress(error_body, mtime=0)
    historical.update(raw_sha256=digest(error_body), raw_compressed_sha256=digest(error_compressed))
    legacy_files = copy.deepcopy(captured); legacy_files[historical['raw_response_path']] = error_compressed
    exercise('legacy_reused_ordinal_distinct_actual_starts_and_error_body', rebind(legacy_files, [historical, base_ledger[0]]), True)
    missing = copy.deepcopy(historical)
    for key in ['raw_response_path', 'raw_sha256', 'raw_compressed_sha256']: missing.pop(key)
    limitation = {'status': 'disclosed_capture_limitation', 'recorded_failed_attempts_missing_bodies': 1, 'affected_attempts': [missing]}
    disclosed = rebind(copy.deepcopy(captured), [missing, base_ledger[0]], limitation=limitation)
    exercise('exact_original_disclosed_missing_HTTP503_row', disclosed, True)
    changed = copy.deepcopy(disclosed); bad = json.loads(changed[limitation_name]); bad['affected_attempts'][0]['error'] += ' changed'
    exercise('rebound_whitelist_cannot_change_original_row', rebind(changed, [missing, base_ledger[0]], limitation=bad))
    exercise('unlisted_failed_missing_body', rebind(copy.deepcopy(captured), [missing, base_ledger[0]]))
    for label, key, value in [('missing_start', 'started_at_utc', None), ('naive_start', 'started_at_utc', '2000-01-01T00:00:00'),
        ('nonUTC_start', 'started_at_utc', '2000-01-01T01:00:00+01:00'), ('finish_before_start', 'finished_at_utc', '1999-12-31T23:59:59+00:00'),
        ('boolean_ordinal', 'attempt', True), ('unknown_status', 'status', 'pending')]:
        ledger = copy.deepcopy(base_ledger)
        if value is None: ledger[0].pop(key)
        else: ledger[0][key] = value
        exercise(label, rebind(copy.deepcopy(captured), ledger))
    duplicate = copy.deepcopy(base_ledger[0]); duplicate['raw_response_path'] = 'cache/rss_raw/attempts/synthetic.duplicate.xml.gz'
    files = copy.deepcopy(captured); files[duplicate['raw_response_path']] = files[base_ledger[0]['raw_response_path']]
    exercise('same_full_start_identity_even_with_new_body_path', rebind(files, [*base_ledger, duplicate]))
    fetched_missing = copy.deepcopy(base_ledger); fetched_missing[0].pop('raw_response_path')
    exercise('fetched_missing_body_never_waived', rebind(copy.deepcopy(captured), fetched_missing))
    orphan = copy.deepcopy(historical); orphan['signature'] = 'unplanned'; files = copy.deepcopy(captured)
    files[orphan['raw_response_path']] = error_compressed
    exercise('historical_ledger_signature_outside_canonical_inventory', rebind(files, [orphan, *base_ledger]))
    for label, change in [('empty_current_cache_attempts', lambda value: value.update(physical_attempts=[])),
                          ('cache_attempt_URL_changed', lambda value: value['physical_attempts'][0].update(request_url='https://example.org/changed'))]:
        cache = copy.deepcopy(base_cache); change(cache); exercise(label, rebind(copy.deepcopy(captured), cache=cache))
    # Modern instrumentation is optional only when it was not actually used.
    modern = copy.deepcopy(base_ledger); modern[0]['attempt_id'] = 'synthetic-modern-1'
    cache = copy.deepcopy(base_cache); cache['physical_attempts'] = modern
    start = {key: modern[0][key] for key in ['signature', 'request_url', 'attempt', 'attempt_id', 'started_at_utc']}
    files = copy.deepcopy(captured); files[inventory.ATTEMPT_STARTS] = (json.dumps(start) + '\n').encode()
    modern_files = rebind(files, modern, cache)
    exercise('modern_start_completion_exact_positive', modern_files, True)
    for label, starts in [('duplicate_modern_start_id', [start, start]),
                          ('orphan_modern_started_id', [start, {**start, 'attempt_id': 'synthetic-unsettled'}]),
                          ('modern_start_clock_mismatch', [{**start, 'started_at_utc': '2000-01-01T00:00:02+00:00'}])]:
        files = copy.deepcopy(modern_files); files[inventory.ATTEMPT_STARTS] = ''.join(json.dumps(row) + '\n' for row in starts).encode()
        exercise(label, rebind(files, modern, cache))
    files = copy.deepcopy(modern_files); files.pop(inventory.ATTEMPT_STARTS)
    exercise('modern_start_ledger_missing', rebind(files, modern, cache))
    files = copy.deepcopy(captured); files[inventory.ATTEMPT_STARTS] = b''
    exercise('fabricated_unused_empty_start_ledger', rebind(files))
    # Only the named mutable coverage phase context can differ from the old
    # physical review. Every other immutable dependency remains exact.
    files = rebind(copy.deepcopy(captured)); proof = json.loads(files[proof_name])
    proof['input_bindings']['audit/news_coverage.json'] = digest(b'earlier synthetic coverage')
    files[proof_name] = json.dumps(proof).encode(); source = json.loads(files[source_name]); source['prior_physical_review_sha256'] = digest(files[proof_name])
    files[source_name] = json.dumps(source).encode(); exercise('named_historical_coverage_with_current_final_binding', files, True)
    source['input_bindings']['audit/news_coverage.json'] = '0' * 64; files[source_name] = json.dumps(source).encode()
    exercise('historical_coverage_does_not_waive_current_final_binding', files)
    files = rebind(copy.deepcopy(captured)); files['audit/news_query_plan.json'] += b'changed'
    exercise('immutable_query_plan_still_exact', files)
    result = {'status': 'synthetic_transport_checks_passed', 'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'cases': cases, 'case_count': len(cases), 'runtime_full20_report_artifacts_accepted': False,
              'scope': 'Generic synthetic current-schema transport controls only; no actual source inputs or report facts read.',
              'tool_sha256': {name: digest((ROOT / name).read_bytes()) for name in
                             ['tools/build_source_inventory.py', 'tools/build_artifacts.py', 'audit_work/review_final_artifacts.py',
                              'audit_work/test_artifact_transport_regressions.py']}}
    (ROOT / 'checks/artifact_transport_regressions.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'case_count': len(cases)}))


if __name__ == '__main__': main()
