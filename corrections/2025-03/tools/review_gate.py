"""Require current chronology and independent selected-claim review receipts."""
import datetime as dt
import hashlib
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATES = [dt.date(2025, 4, n).isoformat() for n in range(1, 31)
         if dt.date(2025, 4, n).weekday() < 5]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text())


def checked_input(row, label):
    """Resolve an explicitly recorded supporting file inside this month."""
    path = (ROOT/row['path']).resolve()
    if (not path.is_relative_to(ROOT) or not path.is_file()
            or sha(path) != row.get('sha256')
            or ('bytes' in row and path.stat().st_size != row['bytes'])):
        raise ValueError(label+' changed: '+row['path'])
    return path


def require_date_hashes(hashes, directory, suffix, label):
    if sorted(hashes) != DATES:
        raise ValueError('Complete current '+label+' hashes required')
    for date in DATES:
        if hashes[date] != sha(ROOT/directory/(date+suffix)):
            raise ValueError(date+' changed after '+label)


def tagged_market_paragraphs(report):
    """Use the exact source-tag scope recorded by the market prose reviewer."""
    tag = re.compile(r'\((?:Yahoo Finance|US Treasury), prior [^)]+\)')
    found = {}
    def walk(value, path=()):
        if isinstance(value, dict):
            for key, child in value.items(): walk(child, path+(key,))
        elif isinstance(value, list):
            for index, child in enumerate(value): walk(child, path+(index,))
        elif isinstance(value, str) and tag.search(value):
            found[path] = hashlib.sha256(value.encode()).hexdigest()
    walk(report)
    return found


def require_market_prose_review():
    path = ROOT/'checks/market_prose_review.json'
    if not path.is_file():
        raise ValueError('Complete current market prose review required')
    review = read_json(path)
    rows = review.get('reports', [])
    if (review.get('status') != 'complete_market_quote_scope'
            or review.get('reports_reviewed') != len(DATES)
            or sorted(row.get('date') for row in rows) != DATES
            or review.get('pending_dates') != []
            or review.get('unreviewed_changed_paragraphs') != []
            or not review.get('reviewer')
            or any(row.get('status') != 'corrected_and_reread'
                   or row.get('current_text_matches_reviewed_correction') is not True
                   for row in review.get('findings', []))):
        raise ValueError('Complete current market prose review required')
    if review.get('showcard_formatter_sha256') != sha(ROOT/'tools/showcard.py'):
        raise ValueError('Market card formatter changed after prose review')
    total = 0
    for row in rows:
        date = row['date']
        for field, directory, suffix in [('current_spec_sha256', 'specs', '.json'),
                                          ('feed_sha256', 'feeds', '.json.gz'),
                                          ('card_sha256', 'cards', '.json')]:
            if row.get(field) != sha(ROOT/directory/(date+suffix)):
                raise ValueError(date+' changed after market prose review: '+field)
        checked_input({'path': row['snapshot_path'], 'sha256': row['snapshot_spec_sha256']},
                      'Market prose review snapshot')
        if not row.get('author_seals'):
            raise ValueError(date+' market prose author seals missing')
        for name, digest in row['author_seals'].items():
            checked_input({'path': name, 'sha256': digest}, 'Market prose author seal')
        report = read_json(ROOT/'specs'/f'{date}.json')
        expected = tagged_market_paragraphs(report)
        reviewed = row.get('reviewed_market_quote_paragraphs', [])
        actual = {tuple(part['path']): part['reviewed_text_sha256'] for part in reviewed}
        if len(actual) != len(reviewed) or not set(expected).issubset(actual):
            raise ValueError(date+' missing reviewed market quote paragraphs')
        for parts, digest in actual.items():
            value = report
            try:
                for part in parts: value = value[part]
            except (KeyError, IndexError, TypeError):
                raise ValueError(date+' changed market quote paragraph path') from None
            if not isinstance(value, str) or hashlib.sha256(value.encode()).hexdigest() != digest:
                raise ValueError(date+' changed reviewed market quote paragraph')
        total += len(actual)
    if review.get('market_quote_paragraphs_reviewed') != total:
        raise ValueError('Market prose reviewed paragraph count changed')
    diagnostic = review['numeric_diagnostic']
    diagnostic_path = checked_input({'path': diagnostic['path'], 'sha256': diagnostic['sha256']},
                                    'Market prose diagnostic')
    checked_input({'path': diagnostic['auditor_path'], 'sha256': diagnostic['auditor_sha256']},
                  'Market prose diagnostic code')
    numeric = read_json(diagnostic_path)
    numeric_rows = numeric.get('reports', [])
    if (numeric.get('auditor_sha256') != diagnostic['auditor_sha256']
            or sorted(row.get('date') for row in numeric_rows) != DATES):
        raise ValueError('Complete current market prose numeric diagnostic required')
    for row in numeric_rows:
        date = row['date']
        if (row.get('input_kind') != 'current_sealed_spec'
                or row.get('spec_snapshot_sha256') != sha(ROOT/'specs'/f'{date}.json')
                or row.get('card_sha256') != sha(ROOT/'cards'/f'{date}.json')):
            raise ValueError(date+' market prose diagnostic inputs changed')
    portable_path = checked_input(review['portable_inputs'], 'Market prose portable inventory')
    for row in read_json(portable_path)['files']:
        checked_input(row, 'Market prose portable input')
    return sha(path)


def require_cited_metadata_review():
    path = ROOT/'checks/cited_metadata_independent_review.json'
    if not path.is_file():
        raise ValueError('Complete current cited metadata review required')
    review = read_json(path)
    current = review.get('current_citation_snapshot', {})
    cache_path = ROOT/'audit/canonical_all_cited_urls.json'
    inventory_path = ROOT/'audit/news_replay_inventory.json'
    qa_path = ROOT/'checks/source_acquisition_independent_review.json'
    if (review.get('status') != 'passed' or review.get('passed') is not True
            or review.get('pending_report_dates') != [] or not review.get('reviewer')
            or current.get('dates') != DATES or current.get('missing_count') != 0
            or current.get('missing_urls') != [] or current.get('cache_sha256') != sha(cache_path)
            or review.get('initial_inventory_sha256') != sha(inventory_path)
            or review.get('initial_source_qa_sha256') != sha(qa_path)):
        raise ValueError('Complete current cited metadata review required')
    require_date_hashes(current.get('spec_sha256', {}), 'specs', '.json', 'cited metadata review')
    checker_path = ROOT/'tools/check_cited_metadata_recovery.py'
    if review.get('review_tool_sha256') != sha(checker_path):
        raise ValueError('Cited metadata review code changed')
    frozen = review.get('frozen_acquisition_verification', {})
    inventory = read_json(inventory_path)
    if (frozen.get('passed') is not True
            or frozen.get('files_verified') != len(inventory['files'])
            or frozen.get('bytes_verified') != sum(row['bytes'] for row in inventory['files'])
            or frozen.get('inventory_sha256') != sha(inventory_path)
            or frozen.get('initial_source_qa_sha256') != sha(qa_path)):
        raise ValueError('Cited metadata frozen acquisition proof changed')
    sp = importlib.util.spec_from_file_location('april_cited_metadata_gate', checker_path)
    checker = importlib.util.module_from_spec(sp); sp.loader.exec_module(checker)
    try:
        if review.get('current_cache_verification') != checker.verify_cache():
            raise ValueError('Cited metadata cache or captured output proof changed')
        if current != checker.snapshot(DATES):
            raise ValueError('Current cited metadata snapshot changed')
        numbers = sorted(int(re.search(r'batch(\d+)', p.name).group(1))
                         for p in (ROOT/'audit').glob('metadata_ci_ingestion_batch*.json')
                         if int(re.search(r'batch(\d+)', p.name).group(1)) >= 2)
        expected = [checker.batch_proof(number) for number in numbers]
        if (review.get('batches') != expected
                or review.get('verified_later_records') != sum(row['records'] for row in expected)):
            raise ValueError('Cited metadata independent batch proof changed')
    except AssertionError as error:
        raise ValueError('Cited metadata captured inputs changed: '+str(error)) from error
    return sha(path)


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def require_retail_editorial_review():
    path = ROOT/'checks/retail_editorial_review.json'
    if not path.is_file():
        raise ValueError('Complete current retail editorial review required')
    review = read_json(path)
    reports = review.get('reports', {})
    if (review.get('status') != 'passed' or review.get('report_count') != len(DATES)
            or review.get('chronological_review') is not True
            or review.get('unresolved_issues') != [] or not review.get('reviewer')
            or sorted(reports) != DATES):
        raise ValueError('Complete current retail editorial review required')
    for field, directory, suffix in [('spec_sha256', 'specs', '.json'),
                                     ('feed_sha256', 'feeds', '.json.gz'),
                                     ('card_sha256', 'cards', '.json')]:
        require_date_hashes(review.get(field, {}), directory, suffix, 'retail editorial review '+field)
    for date, row in reports.items():
        for field in ['spec_sha256', 'feed_sha256', 'card_sha256']:
            if row.get(field) != review[field][date]:
                raise ValueError(date+' retail editorial input hashes disagree')
        retail = read_json(ROOT/'specs'/f'{date}.json')['retail']
        if (row.get('reviewed') is not True or row.get('reviewed_entries') != 4
                or row.get('retail_sha256') != canonical_sha(retail)
                or row.get('entry_sha256') != [canonical_sha(entry) for entry in retail]
                or not row.get('notes')):
            raise ValueError(date+' changed or incomplete reviewed retail entries')
    decision_path = ROOT/'checks/retail_editorial_decisions.json'
    guard_path = ROOT/'checks/retail_quality.json'
    guard_code = ROOT.parent/'retail-quality/retail_quality.py'
    if (review.get('decision_file_sha256') != sha(decision_path)
            or review.get('guard_receipt_sha256') != sha(guard_path)
            or review.get('guard_code_sha256') != sha(guard_code)
            or review.get('proposals_sha256') != sha(ROOT/'work/retail_edit_proposals.json')):
        raise ValueError('Retail editorial decisions, guard or proposal proof changed')
    sp = importlib.util.spec_from_file_location('april_retail_editorial_gate', guard_code)
    guard = importlib.util.module_from_spec(sp); sp.loader.exec_module(guard)
    receipt = read_json(guard_path)
    current = guard.audit_month(ROOT, decision_path)
    semantic = lambda record: {key: value for key, value in record.items() if key != 'checked_at_utc'}
    if receipt.get('review_gate_passed') is not True or semantic(receipt) != semantic(current):
        raise ValueError('Retail guard no longer binds the current reviewed inputs')
    return sha(path)


def require_author_acceptance():
    path = ROOT/'checks/source_input_acceptance.json'
    acceptance = read_json(path)
    if (acceptance.get('status') != 'accepted_for_historical_authoring'
            or acceptance.get('report_dates') != len(DATES)
            or acceptance.get('source_qa_sha256') != sha(ROOT/'checks/source_acquisition_independent_review.json')):
        raise ValueError('Historical author input acceptance changed')
    for field, original_field in [
            ('acceptance_gate_snapshot', 'source_review_gate_sha256'),
            ('acceptance_check_receipt_snapshot', 'source_gate_rejection_checks_sha256')]:
        row = acceptance[field]
        checked_input(row, 'Initial author acceptance snapshot')
        if row['sha256'] != acceptance.get(original_field):
            raise ValueError('Initial author acceptance snapshot hash disagrees')
    return sha(path)


def require_sources():
    """Bind pre-author acquisition, replay inventory and independently checked feeds."""
    coverage_path = ROOT/'audit/news_coverage.json'
    plan_path = ROOT/'audit/news_query_plan.json'
    inventory_path = ROOT/'audit/news_replay_inventory.json'
    ready_path = ROOT/'audit/news_ready_audit.json'
    qa_path = ROOT/'checks/source_acquisition_independent_review.json'
    coverage, plan, inventory, ready, qa = [read_json(p) for p in
        (coverage_path, plan_path, inventory_path, ready_path, qa_path)]
    if (coverage.get('status') != 'acquired_verified'
            or coverage.get('report_dates') != len(DATES)
            or coverage.get('failed_requests') != 0
            or coverage.get('query_plan_sha256') != sha(plan_path)
            or sorted(plan.get('dates', [])) != DATES):
        raise ValueError('Complete passing cutoff-bounded news acquisition required')
    required = ['request_catalog_complete', 'all_capped_multiday_refined',
                'request_upper_cutoff_enforced', 'own_date_replay_passed',
                'readiness_replay_passed', 'category_age_cutoffs_passed']
    if (qa.get('passed') is not True or qa.get('report_count') != len(DATES)
            or any(qa.get(key) is not True for key in required)
            or qa.get('failed_requests') != 0
            or qa.get('unresolved_priority_records') != 0):
        raise ValueError('Complete independent news acquisition and readiness review required')
    for field, path in [('coverage_sha256', coverage_path),
                        ('query_plan_sha256', plan_path),
                        ('replay_inventory_sha256', inventory_path),
                        ('news_ready_audit_sha256', ready_path)]:
        if qa.get(field) != sha(path):
            raise ValueError('Source acquisition proof changed: '+path.name)
    tools = qa.get('acquisition_tool_sha256', {})
    expected = {'tools/fetch_news.py', 'tools/expand_capped_news.py',
                'tools/topics.py', 'tools/ready_feeds.py'}
    if (set(tools) != expected
            or any(tools[name] != sha(ROOT/name) for name in tools)
            or qa.get('qa_script_sha256') != sha(ROOT/'tools/check_news_acquisition.py')):
        raise ValueError('Source acquisition or independent check code changed')
    helpers = qa.get('helper_tool_sha256', {})
    if (set(helpers) != {'tools/digest.py', 'posthoc/resolve_news_url.py'}
            or any(helpers[name] != sha(ROOT/name) for name in helpers)):
        raise ValueError('Source screening helper changed after independent review')
    coverage_tools = coverage.get('acquisition_tool_sha256', {})
    if (set(coverage_tools) != expected
            or any(coverage_tools[name] != tools[name] for name in coverage_tools)):
        raise ValueError('Coverage tool inventory does not match independent review')
    files = inventory.get('files', [])
    names = [row.get('path') for row in files]
    if (inventory.get('complete') is not True or not files
            or len(names) != len(set(names))
            or inventory.get('file_count', len(files)) != len(files)
            or qa.get('inventory_files_verified') != len(files)):
        raise ValueError('Complete unique news replay inventory required')
    for row in files:
        path = (ROOT/row['path']).resolve()
        if (not path.is_relative_to(ROOT) or not path.is_file()
                or path.stat().st_size != row.get('bytes') or sha(path) != row.get('sha256')):
            raise ValueError('Archived news replay input changed: '+row['path'])
    for field, directory in [('raw_feed_sha256', 'work/unreviewed_feeds'),
                             ('final_feed_sha256', 'feeds')]:
        hashes = qa.get(field, {})
        if sorted(hashes) != DATES:
            raise ValueError('Complete source-feed hashes required: '+field)
        for date in DATES:
            if hashes[date] != sha(ROOT/directory/f'{date}.json.gz'):
                raise ValueError(date+' '+directory+' changed after source review')
    if (ready.get('status') != 'passed' or ready.get('report_dates') != len(DATES)
            or ready.get('missing_dates') != []
            or ready.get('failed_query_windows') != 0
            or ready.get('unresolved_priority_records') != 0):
        raise ValueError('Complete source readiness required')
    return {'news_coverage_sha256': sha(coverage_path),
            'news_replay_inventory_sha256': sha(inventory_path),
            'source_acquisition_review_sha256': sha(qa_path)}



def paragraph_hashes(report):
    """Bind reviewed prose itself as well as the enclosing specification file."""
    sp = importlib.util.spec_from_file_location('april_reviewed_paragraphs', ROOT/'tools/verify.py')
    verifier = importlib.util.module_from_spec(sp); sp.loader.exec_module(verifier)
    return {where+':'+label: hashlib.sha256(text.encode()).hexdigest()
            for where, label, text in verifier.paragraphs(report)}


def selected_parts():
    parts = {
        'geo:US': ['Macro Stance', 'Rates & Curve', 'New / Most Important'],
        'geo:EU': ['Macro Stance', 'New / Most Important'],
        'geo:CN': ['Macro Stance', 'PMIs & Activity', 'New / Most Important'],
        'geo:JP': ['Macro Stance'], 'geo:AU': ['Macro Stance'],
        'geo:PL': ['Macro Stance', 'Corporate & Sectors', 'New / Most Important'],
        'earnings_pattern': ['Rewarded', 'Punished'],
        'crypto': ['New / Most Important'], 'retail[0]': ['The Social Signal']}
    keys = {where+':'+label for where, labels in parts.items() for label in labels}
    keys.update('catalysts['+str(n)+']:Catalyst & Thesis' for n in range(6))
    return keys


def require_manifest_review(proof):
    """Finalization/publication must use the review proof stored by the build."""
    manifest_path = ROOT/'checks/artifact_manifest.json'
    if (manifest_path.exists()
            and read_json(manifest_path).get('review_receipts') != proof):
        raise ValueError('Artifact manifest does not bind the current review receipts')


def require_review(*, check_manifest=True):
    source_proof = require_sources()
    chronology = json.loads((ROOT/'audit/cited_source_dates.json').read_text())
    if (chronology.get('date_screen_passed') is not True
            or sorted(chronology.get('spec_sha256', {})) != DATES):
        raise ValueError('Complete passing cited-source date screen required')
    if (chronology.get('timing_exceptions_sha256') != sha(ROOT/'audit/canonical_source_exceptions.json')
            or chronology.get('auditor_sha256') != sha(ROOT/'tools/audit_source_dates.py')):
        raise ValueError('Timing exceptions or source auditor changed after screening')
    exceptions = json.loads((ROOT/'audit/canonical_source_exceptions.json').read_text())['exceptions']
    approved = {(x['date'], x['id']): x for x in exceptions}
    for used in chronology.get('timing_exceptions_used', []):
        row = approved.get((used['date'], used['id']))
        proof = (ROOT/row.get('timing_proof_file', '')).resolve() if row else None
        if (not proof or not proof.is_relative_to(ROOT) or not proof.is_file()
                or sha(proof) != row.get('timing_proof_sha256')):
            raise ValueError('Timing proof changed after source screening: '+str(used))
    independent = json.loads((ROOT/'checks/independent_selected_review.json').read_text())
    attributions = json.loads((ROOT/'checks/source_attribution_diagnostic.json').read_text())
    if (attributions.get('reports') != len(DATES) or attributions.get('flags') != []
            or sorted(attributions.get('spec_sha256', {})) != DATES
            or attributions.get('auditor_sha256') != sha(ROOT/'tools/audit_attributions.py')):
        raise ValueError('Complete current named-outlet attribution diagnostic required')
    if sorted(independent.get('reports', {})) != DATES:
        raise ValueError(f'Independent selected-claim review required for all {len(DATES)} dates')
    for date in DATES:
        spec_hash = sha(ROOT/'specs'/f'{date}.json')
        feed_hash = sha(ROOT/'feeds'/f'{date}.json.gz')
        card_hash = sha(ROOT/'cards'/f'{date}.json')
        row = independent['reports'][date]
        if (chronology['spec_sha256'].get(date) != spec_hash
                or attributions['spec_sha256'].get(date) != spec_hash
                or attributions.get('feed_sha256', {}).get(date) != feed_hash
                or chronology.get('feed_sha256', {}).get(date) != feed_hash
                or row.get('spec_sha256') != spec_hash
                or row.get('feed_sha256') != feed_hash
                or row.get('card_sha256') != card_hash):
            raise ValueError(date+' changed after source or independent review')
        if (row.get('selected_review_passed') is not True
                or not row.get('reviewer') or not row.get('notes')):
            raise ValueError(date+' incomplete independent review')
        reviewed = row.get('reviewed_paragraphs', {})
        actual = paragraph_hashes(read_json(ROOT/'specs'/f'{date}.json'))
        if (not selected_parts().issubset(reviewed)
                or row.get('selected_paragraph_count') != len(reviewed)
                or any(actual.get(name) != digest for name, digest in reviewed.items())):
            raise ValueError(date+' incomplete or changed independently reviewed paragraphs')
    final_reviews = {'market_prose_review_sha256': require_market_prose_review(),
                     'retail_editorial_review_sha256': require_retail_editorial_review(),
                     'cited_metadata_review_sha256': require_cited_metadata_review(),
                     'author_input_acceptance_sha256': require_author_acceptance()}
    proof = {'dates': DATES, 'chronology_sha256': sha(ROOT/'audit/cited_source_dates.json'),
             'selected_review_sha256': sha(ROOT/'checks/independent_selected_review.json'),
             'attribution_sha256': sha(ROOT/'checks/source_attribution_diagnostic.json'),
             'gate_sha256': sha(Path(__file__)),
             'verifier_sha256': sha(ROOT/'tools/verify.py'), **source_proof, **final_reviews}
    if check_manifest:
        require_manifest_review(proof)
    return proof


if __name__ == '__main__':
    print(json.dumps(require_review(), indent=2))
