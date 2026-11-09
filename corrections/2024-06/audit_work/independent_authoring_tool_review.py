"""Separate engineer review of generic authoring tools and synthetic inputs.

No factual report specifications, feeds, cards, price history or prose are read.
The owner regression fixture is rerun and independently mutated in its isolated
temporary directory. Actual 20-edition editorial integration remains pending.
"""
from pathlib import Path
import contextlib
import copy
import datetime as dt
import hashlib
import io
import json

ROOT = Path(__file__).resolve().parent.parent
FILES = ['tools/' + name + '.py' for name in (
    'verify', 'digest', 'showcard', 'cited_titles', 'check_block_ranges',
    'merge_retail', 'stage_reviewed', 'finalize_reviews', 'retail_quality_snapshot')]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    before = {name: sha(ROOT / name) for name in FILES}
    owner = ROOT / 'audit_work/authoring_tools_regression.py'
    source = owner.read_text().split('\nsummary=', 1)[0]
    scope = {'__file__': str(owner), '__name__': 'independent_authoring_fixture'}
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(source, str(owner), 'exec'), scope)
    temporary = scope['TEMP']; fixture = scope['FIX']; date = scope['d']
    finalizer = scope['finalize_reviews']; merge = scope['merge_retail']; verify = scope['verify']
    retail = scope['retail_quality_snapshot']; cases = []

    def rejects(name, action):
        try:
            action()
        except (ValueError, KeyError, TypeError, FileNotFoundError):
            cases.append({'case': name, 'result': 'rejected_as_required'})
        else:
            raise AssertionError('Independent negative accepted: ' + name)

    def mutate_file(relative, change, action, name):
        path = fixture / relative; original = path.read_bytes()
        value = json.loads(original); change(value)
        path.write_text(json.dumps(value, ensure_ascii=False))
        try:
            rejects(name, action)
        finally:
            path.write_bytes(original)

    try:
        current = copy.deepcopy(scope['current_source'])
        by_date = {row['date']: {'feed_sha256': row['feed_sha256'], 'exclusions': []}
                   for row in current['dates']}
        current.update(known_semantic_exclusions={'by_date': by_date}, known_timing_exclusions={'by_date': by_date})
        current.pop('input_bindings')
        rejects('legacy_maps_cannot_override_current_screening', lambda: finalizer.frozen_source_exclusions(current, {row['date']: row for row in current['dates']}))
        for kind in ['nonretail', 'retail']:
            relative = f'audit/independent_{kind}_{date}.json'
            mutate_file(relative, lambda value: value.pop('status'), lambda: merge.reviewed_candidate(date), kind + '_missing_status')
            mutate_file(relative, lambda value: value.__setitem__('status', 'pending'), lambda: merge.reviewed_candidate(date), kind + '_pending_status')
            mutate_file(relative, lambda value: value.__setitem__('exclusions_sha256', '0' * 64), lambda: merge.reviewed_candidate(date), kind + '_stale_exclusions')
        for label, action in [('verifier', lambda: verify.load_exclusions(date, verify.load_feed(date))),
                              ('retail_gate', lambda: retail.load_feed(fixture, date))]:
            mutate_file(f'exclusions/{date}.json', lambda value: value.pop('feed_sha256'), action, label + '_missing_exclusion_feed_binding')
            mutate_file(f'exclusions/{date}.json', lambda value: value.__setitem__('feed_sha256', '0' * 64), action, label + '_stale_exclusion_feed_binding')
        exact_warning = 'Synthetic calendar warning requiring a dated preview'
        bad = {'warning': 'WARN ' + date + ' ' + exact_warning, 'evidence_ids': ['n0001'],
               'rationale': 'The synthetic headline establishes the exact pending event under review.'}
        assert finalizer.reviewed_warnings([exact_warning], [{'reviewed_validation_warnings': [bad]}], {'n0001'})[0]
        cases.append({'case': 'CLI_warning_prefix_cannot_replace_raw_diagnostic', 'result': 'rejected_as_required'})
        ready_name = f'audit/news_ready_{date}.json'; ready_path = fixture / ready_name
        original = ready_path.read_bytes()
        for name, mutate in [('screened_alias_with_rebound_hashes', lambda value: value['excluded'][0].__setitem__('id', 'ALIAS')),
                             ('screened_boolean_count_with_rebound_hashes', lambda value: value.__setitem__('ready_items', True))]:
            value = json.loads(original); mutate(value); ready_path.write_text(json.dumps(value))
            changed = copy.deepcopy(scope['current_source']); rows = {row['date']: row for row in changed['dates']}
            changed['input_bindings'][ready_name] = rows[date]['ready_receipt_sha256'] = sha(ready_path)
            rejects(name, lambda: finalizer.frozen_source_exclusions(changed, rows))
            ready_path.write_bytes(original)
        assert len(scope['results']) >= 106 and all(row['pass'] for row in scope['results'])
        assert merge.digest({'Łódź': 'é'}) == hashlib.sha256(json.dumps({'Łódź': 'é'}, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        cases.append({'case': 'canonical_UTF8_compact_sorted_JSON_digest', 'result': 'passed'})
        assert before == {name: sha(ROOT / name) for name in FILES}
        assert sha(ROOT / 'audit_work/shared_retail_quality_original.py') == sha(ROOT.parent / 'retail-quality/retail_quality.py')
    finally:
        temporary.cleanup()
    result = {'status': 'accepted', 'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'review_type': 'independent_authoring_tool_engineering_review', 'fatal_or_major_remaining': 0,
              'tool_sha256': before, 'reviewer_sha256': sha(Path(__file__)), 'owner_regression_helper_sha256': sha(owner),
              'owner_synthetic_cases_rerun': len(scope['results']), 'independent_cases': cases,
              'report_facts_read': False, 'runtime_full20_accepted': False, 'publication_performed': False,
              'findings_resolved': ['June legacy source maps could bypass current screening; they now reject.',
                                    'Missing component status could pass; explicit accepted/passed is now required.',
                                    'Missing exclusion-feed hashes could pass; both loaders now require exact frozen feed bytes.'],
              'limits': ['Generic code, receipt schema and isolated synthetic checks only.',
                         'Actual20date source/feed/card/component/editorial integration remains pending.',
                         'Numeric membership checks do not establish instrument identity or headline claim meaning.']}
    (ROOT / 'audit/independent_authoring_tool_review.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'owner_cases_rerun': result['owner_synthetic_cases_rerun'],
                      'independent_cases': len(cases), 'runtime_full20_accepted': False}))


if __name__ == '__main__':
    main()
