"""Hash-bind exact June acquisition/replay inputs; never acquire or change evidence.

Author scripts, repository clones, deployments, secrets and older report sets are
outside the explicit packaging roots. Bounded lookback observations acquired for
a June cutoff may of course precede June; no prior retrospective input is reused.
"""
from pathlib import Path, PurePosixPath
import datetime as dt
import hashlib
import gzip
import json
import re
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
DATES = [dt.date(2024, 6, n).isoformat() for n in range(3, 29)
         if dt.date(2024, 6, n).weekday() < 5]
REPLAY_ROOTS = (
    'cache/news', 'cache/rss_raw', 'audit/news_provenance', 'audit/market_raw',
    'work/source_candidates', 'work/unreviewed_feeds', 'work/acquisition_feeds',
    'exclusions', 'source_supplements', 'audit/source_amendments',
    'audit/review_history', 'audit_work',
)
FORBIDDEN_PARTS = {'.git', '.aws', '.ssh', '__pycache__', 'node_modules', 'repo',
                   'repository', 'credentials', 'secrets'}
FORBIDDEN_NAMES = {'source_inventory.json', 'news_replay_inventory.json',
                   'artifact_manifest.json', 'final_artifact_review.json',
                   'source_archive_build.json', 'delivery_verification.json',
                   'publication.json', 'archive_index_reconciliation.json'}
PHYSICAL_REVIEW = 'audit/independent_physical_source_review.json'
CAPTURE_LIMITATION = 'audit_work/acquisition_capture_limitation.json'
ATTEMPT_STARTS = 'audit/news_physical_attempt_starts.jsonl'
TRANSPORT_FIELDS = ('physical_requests', 'physical_attempts', 'received_attempt_bodies', 'failed_attempts',
                    'recorded_missing_response_bodies', 'discarded_error_body_limitations_sha256',
                    'legacy_signature_attempt_number_collisions', 'unlogged_interrupted_attempts_maximum',
                    'unlogged_interrupted_attempts_actual_count', 'all_physical_network_attempts_complete',
                    'attempt_starts_ledger_sha256', 'attempt_starts_instrumentation_used',
                    'ledger_sha256', 'query_plan_sha256', 'physical_source_inventory_sha256')

PUBLIC_RESEARCH_MANIFEST = "audit/public_research_manifest.json"
PUBLIC_CLOCK_EVIDENCE = "audit/public_clock_evidence.json"
PUBLIC_RESEARCH_ATTESTATION = "audit/public_research_attestation.json"
PUBLIC_RESEARCH_REVIEW = "audit/independent_public_research_projection_review.json"
PRIVATE_RESEARCH_PATHS = frozenset(('audit_work/june17_china_release_timing_search.json', 'audit_work/june17_nbs_primary_release_pages.json', 'audit_work/june17_nbs_primary_release_search.json', 'audit_work/june_calendar_web_initial.json', 'audit_work/june_calendar_web_policy.json', 'audit_work/june_calendar_web_releases.json', 'audit_work/june_company_calendar_web_1.json', 'audit_work/june_company_calendar_web_2.json', 'audit_work/june_company_calendar_web_3.json', 'audit_work/june_company_calendar_web_4.json', 'audit_work/june_company_calendar_web_5.json', 'audit_work/june_company_calendar_web_6.json', 'audit_work/june_pending_calendar_evidence.json', 'audit_work/provenance_calendar_clock_final_details.json', 'audit_work/provenance_calendar_corporate_clocks.json', 'audit_work/provenance_calendar_final_clock_check.json', 'audit_work/provenance_calendar_gus_exact_dates.json', 'audit_work/provenance_calendar_historic_exact.json', 'audit_work/provenance_calendar_japan_clocks.json', 'audit_work/provenance_calendar_japan_date_clock.json', 'audit_work/provenance_calendar_japan_official_details.json', 'audit_work/provenance_calendar_japan_precise_search.json', 'audit_work/provenance_calendar_japan_schedule_search.json', 'audit_work/provenance_calendar_official_crosschecks.json', 'audit_work/provenance_calendar_poland_calendar.json', 'audit_work/provenance_calendar_poland_details.json', 'audit_work/provenance_calendar_poland_nbp.json', 'audit_work/provenance_calendar_primary_opens.json', 'audit_work/provenance_gme_june3_boundary_search.json', 'audit_work/provenance_gme_june3_original_pages.json', 'audit_work/provenance_gme_june3_primary_posts.json', 'audit_work/provenance_observed_livestream_milestone_pages.json', 'audit_work/provenance_observed_livestream_milestone_search.json'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def is_raw_web_response(value):
    if isinstance(value, str):
        if 'content' in value and value.lstrip().startswith(('{', '[')):
            try: decoded = json.loads(value)
            except ValueError: return False
            return is_raw_web_response(decoded) if isinstance(decoded, (dict, list)) else False
        return False
    if isinstance(value, list): return any(is_raw_web_response(item) for item in value)
    if not isinstance(value, dict): return False
    blocks = value.get('content')
    if isinstance(blocks, list):
        text = '\n'.join(item.get('text', '') for item in blocks if isinstance(item, dict) and item.get('type') == 'text')
        if re.search(r'https?://', text) and re.search(r'【turn|\[wordlim:|Total lines:', text): return True
    return any(is_raw_web_response(item) for item in value.values())


def assert_no_raw_web_candidates(read, names):
    """Inspect parseable MCP JSON/JSONL regardless of path, suffix or gzip."""
    for name in names:
        blob = read(name)
        if blob[:2] == b'\x1f\x8b': blob = gzip.decompress(blob)
        # The cheap filter avoids JSON-parsing financial XML or plain voice
        # text; escaped/nested JSON still retains these literal marker words.
        if b'content' not in blob or not any(marker in blob for marker in
                ['【turn'.encode(), b'\\u3010turn', b'[wordlim:', b'Total lines:']):
            continue
        try: values = [json.loads(blob)]
        except (ValueError, UnicodeDecodeError):
            values = []
            for line in blob.splitlines():
                if line.lstrip()[:1] in {b'{', b'['}:
                    try: values.append(json.loads(line))
                    except (ValueError, UnicodeDecodeError): pass
        if any(is_raw_web_response(value) for value in values):
            raise ValueError('Raw MCP web response is prohibited in public candidates: ' + name)


def scan_private_research():
    found = set()
    for folder in ['audit_work', 'audit']:
        for path in (ROOT / folder).rglob('*'):
            if not path.is_file() or not path.name.endswith(('.json', '.json.gz')): continue
            try:
                blob = path.read_bytes()
                if path.name.endswith('.gz'): blob = gzip.decompress(blob)
                value = json.loads(blob)
            except (ValueError, UnicodeDecodeError): continue
            if is_raw_web_response(value): found.add(path.relative_to(ROOT).as_posix())
    if found != PRIVATE_RESEARCH_PATHS:
        raise ValueError('Raw web-response set changed; explicit public projection/review required: ' + repr(sorted(found ^ PRIVATE_RESEARCH_PATHS)))
    return found


def public_document_headers():
    """Document metadata only: no paragraph or article-body text is copied."""
    sources = {}
    header = re.compile(r'^([^\n]{1,500}?)\s+\((https?://[^\s)]+)\)\s*\r?\n(?=【turn[^】]*】)', re.M)
    for name in sorted(PRIVATE_RESEARCH_PATHS):
        value = json.loads(safe_path(name).read_bytes())
        for block in value['content']:
            if not isinstance(block, dict) or block.get('type') != 'text': continue
            for title, url in header.findall(block.get('text', '')):
                title = ' '.join(title.split()[:25])[:240]
                item = sources.setdefault(url, {'url': url, 'title': title, 'private_response_refs': [], 'quote': ''})
                if name not in item['private_response_refs']: item['private_response_refs'].append(name)
    return [sources[url] for url in sorted(sources)]


def public_clock_rows(schedule):
    keys = ['label', 'release_utc', 'calendar_release_utc_date', 'timing_precision',
            'eligible_edition', 'earliest_pub_date', 'kind', 'evidence']
    return [{key: row[key] for key in keys} for row in schedule['guards']]


def validate_public_research_bundle(read, names, source, *, local_originals=False, require_review=True):
    """Validate a finite public projection; never waive local original bindings."""
    names = set(names)
    def record(name):
        if name not in names: raise ValueError('Missing public research projection member: ' + name)
        return json.loads(read(name))
    manifest_blob = read(PUBLIC_RESEARCH_MANIFEST); manifest = record(PUBLIC_RESEARCH_MANIFEST)
    evidence_blob = read(PUBLIC_CLOCK_EVIDENCE); evidence = record(PUBLIC_CLOCK_EVIDENCE)
    attestation_blob = read(PUBLIC_RESEARCH_ATTESTATION); attestation = record(PUBLIC_RESEARCH_ATTESTATION)
    expected_manifest_keys = {'schema', 'status', 'source_acceptance_sha256', 'clock_policy_path', 'clock_policy_sha256',
                              'evidence_path', 'evidence_sha256', 'private_files', 'private_file_count', 'export_scope'}
    if (set(manifest) != expected_manifest_keys or manifest.get('schema') != 'june-public-research-projection-v1'
            or manifest.get('status') != 'public_projection_with_private_original_hash_commitments'
            or manifest.get('export_scope') != 'Compact clock evidence; original full research responses are private and are not publicly byte-replayed.'
            or manifest.get('source_acceptance_sha256') != hashlib.sha256(read('audit/independent_source_review.json')).hexdigest()
            or manifest.get('evidence_path') != PUBLIC_CLOCK_EVIDENCE
            or manifest.get('evidence_sha256') != hashlib.sha256(evidence_blob).hexdigest()):
        raise ValueError('Public research manifest scope/source/evidence binding changed')
    rows = manifest.get('private_files'); commitments = {}
    if not isinstance(rows, list): raise ValueError('Private response commitments must be an ordered list')
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {'path', 'sha256', 'bytes', 'frozen_source_binding_sha256'}
                or row.get('path') not in PRIVATE_RESEARCH_PATHS
                or not isinstance(row.get('sha256'), str) or re.fullmatch(r'[0-9a-f]{64}', row['sha256']) is None
                or type(row.get('bytes')) is not int or row['bytes'] <= 0 or row['path'] in commitments
                or row.get('frozen_source_binding_sha256') != source.get('input_bindings', {}).get(row['path'])
                or (row['frozen_source_binding_sha256'] is not None and row['sha256'] != row['frozen_source_binding_sha256'])):
            raise ValueError('Invalid or altered explicit private raw-response commitment')
        commitments[row['path']] = row
    if (list(commitments) != sorted(PRIVATE_RESEARCH_PATHS) or type(manifest.get('private_file_count')) is not int
            or manifest['private_file_count'] != len(PRIVATE_RESEARCH_PATHS)):
        raise ValueError('Public projection must list the exact reviewed raw web-response set')
    if not local_originals and set(commitments) & names:
        raise ValueError('Private raw web response entered public archive')
    policy_path = 'audit_work/june_release_schedule.json'
    if manifest.get('clock_policy_path') != policy_path or manifest.get('clock_policy_sha256') != hashlib.sha256(read(policy_path)).hexdigest():
        raise ValueError('Public clock projection policy binding changed')
    if set(evidence) != {'schema', 'clock_policy_sha256', 'clock_rows', 'sources', 'quote_word_limit_per_url', 'scope'}:
        raise ValueError('Unexpected public evidence fields; raw research prose is prohibited')
    if (evidence.get('schema') != 'june-public-clock-evidence-v1'
            or evidence.get('clock_policy_sha256') != manifest['clock_policy_sha256']
            or evidence.get('clock_rows') != public_clock_rows(json.loads(read(policy_path)))
            or type(evidence.get('quote_word_limit_per_url')) is not int or evidence['quote_word_limit_per_url'] != 25
            or evidence.get('scope') != 'Factual clock metadata from unchanged guards and document headings/URLs only; no article-body text or quotations.'):
        raise ValueError('Public clock facts or declared compact scope changed')
    sources = evidence.get('sources'); urls = set()
    if not isinstance(sources, list): raise ValueError('Public document metadata must be a list')
    for item in sources:
        if (not isinstance(item, dict) or set(item) != {'url', 'title', 'private_response_refs', 'quote'}
                or not isinstance(item.get('url'), str) or not item['url'].startswith(('https://', 'http://'))
                or item['url'] in urls or not isinstance(item.get('title'), str)
                or len(item['title']) > 240 or len(item['title'].split()) > 25
                or item.get('quote') != '' or not isinstance(item.get('private_response_refs'), list)
                or not item['private_response_refs'] or len(item['private_response_refs']) != len(set(item['private_response_refs']))
                or not set(item['private_response_refs']) <= set(commitments)):
            raise ValueError('Public research prose/quote/URL metadata exceeded the finite projection')
        urls.add(item['url'])
    if len(sources) == 0 or [item['url'] for item in sources] != sorted(urls):
        raise ValueError('Empty/unsorted public document metadata')
    expected_attestation = {
        'schema': 'june-public-research-export-attestation-v1', 'status': 'hash_and_scope_attestation',
        'manifest_sha256': hashlib.sha256(manifest_blob).hexdigest(),
        'evidence_sha256': hashlib.sha256(evidence_blob).hexdigest(),
        'validator_sha256': hashlib.sha256(read('tools/build_source_inventory.py')).hexdigest(),
        'source_acceptance_sha256': manifest['source_acceptance_sha256'],
        'private_originals_retained_locally': True, 'public_original_research_byte_replay': False,
        'financial_RSS_market_feed_guard_or_proof_omitted': False, 'copied_article_body_words': 0,
        'independent_acceptance': False,
    }
    if (attestation != expected_attestation
            or any(type(attestation.get(key)) is not type(value) for key, value in expected_attestation.items())):
        raise ValueError('Public research hash/scope attestation changed')
    if local_originals:
        scan_private_research()
        for name, row in commitments.items():
            path = safe_path(name)
            if sha(path) != row['sha256'] or path.stat().st_size != row['bytes'] or not is_raw_web_response(json.loads(path.read_bytes())):
                raise ValueError('Private original research bytes changed: ' + name)
        if sources != public_document_headers(): raise ValueError('Public document metadata differs from original response headings')
    else:
        assert_no_raw_web_candidates(read, names)
    if require_review:
        review = record(PUBLIC_RESEARCH_REVIEW)
        expected = {'manifest_sha256': hashlib.sha256(manifest_blob).hexdigest(),
                    'evidence_sha256': hashlib.sha256(evidence_blob).hexdigest(),
                    'attestation_sha256': hashlib.sha256(attestation_blob).hexdigest(),
                    'source_acceptance_sha256': manifest['source_acceptance_sha256'],
                    'validator_sha256': attestation['validator_sha256']}
        if (review.get('status') != 'accepted' or review.get('passed') is not True
                or type(review.get('fatal_or_major_remaining')) is not int or review['fatal_or_major_remaining'] != 0
                or review.get('scope') != 'public_research_projection_engineering_only'
                or any(review.get(key) != value for key, value in expected.items())):
            raise ValueError('Current separate engineering review of public research export required')
    return {'commitments': commitments, 'manifest_sha256': hashlib.sha256(manifest_blob).hexdigest(),
            'private_response_count': len(commitments), 'public_clock_rows': len(evidence['clock_rows']),
            'public_document_URLs': len(sources), 'original_research_byte_replay': False,
            'local_originals_verified': local_originals, 'independent_review_required': require_review}


def public_research_export(*, require_review=True):
    source = json.loads((ROOT / 'audit/independent_source_review.json').read_bytes())
    names = set(PRIVATE_RESEARCH_PATHS) | {PUBLIC_RESEARCH_MANIFEST, PUBLIC_CLOCK_EVIDENCE, PUBLIC_RESEARCH_ATTESTATION,
            PUBLIC_RESEARCH_REVIEW, 'audit/independent_source_review.json', 'audit_work/june_release_schedule.json', 'tools/build_source_inventory.py'}
    return validate_public_research_bundle(lambda name: (ROOT / name).read_bytes(), names, source,
                                          local_originals=True, require_review=require_review)


def safe_path(relative):
    """Validate a replay member against explicit paths; never follow symlinks."""
    rel = PurePosixPath(relative)
    if rel.is_absolute() or '..' in rel.parts or str(rel) != relative or '\\' in relative:
        raise ValueError('Unsafe source path: ' + relative)
    if set(rel.parts) & FORBIDDEN_PARTS or rel.name in FORBIDDEN_NAMES:
        raise ValueError('Excluded source path: ' + relative)
    if any(part.startswith('.') for part in rel.parts) or any(x in rel.name.lower() for x in ('secret', 'credential', '.pem', '.key')):
        raise ValueError('Sensitive source filename: ' + relative)
    # Report-date paths must be June. Cache hashes and bounded lookback records
    # are left intact; this check concerns filenames, not their observations.
    if any(month != '2024-06' for month in re.findall(r'20\d{2}-\d{2}(?=-\d{2}(?:\D|$))', relative)):
        raise ValueError('Other report-month path: ' + relative)
    allowed = any(relative.startswith(folder + '/') for folder in REPLAY_ROOTS)
    allowed |= relative in {'newest_lambda_function.py', 'code_provenance.json', 'checks/code_discovery.json'}
    allowed |= relative.startswith('audit/') and len(rel.parts) == 2 and rel.suffix in {'.json', '.jsonl', '.csv'}
    error_body = relative.startswith('cache/rss_raw/attempts/') and relative.endswith('.http-error.gz')
    if not allowed or not (relative.endswith(('.json', '.jsonl', '.json.gz', '.xml.gz', '.py', '.csv', '.log', '.txt')) or error_body):
        raise ValueError('Unapproved replay path: ' + relative)
    path = ROOT / rel
    if (not path.is_file() or not path.resolve().is_relative_to(ROOT)
            or path.is_symlink() or any(p.is_symlink() for p in path.parents if p.is_relative_to(ROOT))):
        raise ValueError('Missing or unsafe replay member: ' + relative)
    return path


def collect_paths():
    paths = set()
    for folder in REPLAY_ROOTS:
        base = ROOT / folder
        paths.update(p for p in base.rglob('*') if p.is_file()
                     and p.name not in FORBIDDEN_NAMES and '__pycache__' not in p.parts
                     and (p.name.endswith(('.json', '.jsonl', '.json.gz', '.xml.gz', '.py', '.csv', '.log', '.txt'))
                          or (p.relative_to(ROOT).as_posix().startswith('cache/rss_raw/attempts/') and p.name.endswith('.http-error.gz'))))
    paths.update((ROOT / 'audit').glob('*.csv'))
    paths.update((ROOT / 'audit').glob('*.jsonl'))
    # Top-level acquisition and market records supplement the nested raw inputs.
    paths.update(p for p in (ROOT / 'audit').glob('*.json')
                 if p.name not in FORBIDDEN_NAMES and not p.name.startswith('independent_nonretail_')
                 and not p.name.startswith('independent_retail_'))
    for name in ('newest_lambda_function.py', 'code_provenance.json', 'checks/code_discovery.json'):
        paths.add(ROOT / name)
    return {safe_path(path.relative_to(ROOT).as_posix()) for path in paths}


def require_ready_receipts(source):
    """Bind the current per-date screening schema, including every exclusion."""
    bindings = source.get('input_bindings')
    if not isinstance(bindings, dict) or not bindings:
        raise ValueError('Current source input_bindings required')
    for row in source['dates']:
        date = row['date']; relative = f'audit/news_ready_{date}.json'
        path = safe_path(relative); receipt = json.loads(path.read_text())
        digest = sha(path)
        if (bindings.get(relative) != digest or row.get('ready_receipt_sha256') != digest
                or receipt.get('date') != date or receipt.get('status') != 'ready'
                or receipt.get('ready_sha256') != row.get('feed_sha256')
                or receipt.get('unreviewed_sha256') != row.get('raw_sha256')):
            raise ValueError('Current source screening receipt missing or stale: ' + date)
        counts = [receipt.get(key) for key in ('input_items', 'ready_items', 'excluded_items')]
        accepted = [row.get(key) for key in ('raw_items', 'ready_items', 'excluded')]
        excluded = receipt.get('excluded')
        if (any(type(value) is not int or value < 0 for value in counts + accepted)
                or counts != accepted or not isinstance(excluded, list)
                or counts[2] != len(excluded) or counts[0] != counts[1] + counts[2]):
            raise ValueError('Current source screening counts changed: ' + date)
        identities = [item.get('id') if isinstance(item, dict) else None for item in excluded]
        if (any(not isinstance(identity, str) or re.fullmatch(r'n\d{4,6}', identity) is None for identity in identities)
                or len(identities) != len(set(identities))):
            raise ValueError('Current source screening exclusion IDs invalid: ' + date)


def utc_clock(value):
    if (not isinstance(value, str)
            or re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)', value) is None):
        raise ValueError('Physical clock must retain its explicit actual UTC timestamp')
    return dt.datetime.fromisoformat(value.replace('Z', '+00:00'))


def attempt_identity(row):
    signature, attempt = row.get('signature'), row.get('attempt')
    if not isinstance(signature, str) or not signature or type(attempt) is not int or attempt < 1:
        raise ValueError('Invalid physical ledger attempt identity')
    utc_clock(row.get('started_at_utc'))
    return signature, attempt, row['started_at_utc']


def transport_records(ledger, proof, limitation, starts):
    """Validate immutable actual identities and only the exact disclosed losses.

    The original ordinal is not globally unique after the interrupted legacy
    process. Preserve it; the actual UTC start distinguishes physical attempts.
    """
    if (proof.get('status') != 'physical_infrastructure_replay_passed' or proof.get('passed') is not True
            or proof.get('errors') or proof.get('authoring_acceptance') is not False or proof.get('dates') != DATES):
        raise ValueError('Accepted exact20-date independent physical replay required')
    identities = set(); bodies = set(); per_signature = {}; modern = {}; successful = {}
    for row in ledger:
        identity = attempt_identity(row)
        if identity in identities:
            raise ValueError('Duplicate physical signature/ordinal/actual-start identity')
        identities.add(identity); signature = row['signature']
        if utc_clock(row.get('finished_at_utc')) < utc_clock(row['started_at_utc']):
            raise ValueError('Physical attempt finish precedes actual UTC start')
        if row.get('status') not in {'fetched', 'failed'}:
            raise ValueError('Unknown physical attempt outcome')
        per_signature[signature] = per_signature.get(signature, 0) + 1
        body = row.get('raw_response_path')
        if body:
            if not isinstance(body, str) or not body.startswith('cache/rss_raw/attempts/') or body in bodies:
                raise ValueError('Reused/non-immutable physical body path')
            bodies.add(body)
        if row['status'] == 'fetched':
            if not body:
                raise ValueError('Fetched physical attempt lost its body')
            if signature not in successful or utc_clock(row['finished_at_utc']) > utc_clock(successful[signature]['finished_at_utc']):
                successful[signature] = row
        if 'attempt_id' in row:
            identity_id = row['attempt_id']
            if not isinstance(identity_id, str) or not identity_id.strip() or identity_id in modern:
                raise ValueError('Modern physical attempt_id missing or reused')
            modern[identity_id] = row
    missing = [row for row in ledger if not row.get('raw_response_path')]
    declared = limitation.get('affected_attempts')
    count = limitation.get('recorded_failed_attempts_missing_bodies')
    if (limitation.get('status') != 'disclosed_capture_limitation' or not isinstance(declared, list)
            or type(count) is not int or count < 0 or count != len(declared)
            or type(proof.get('recorded_missing_response_bodies')) is not int
            or count != proof['recorded_missing_response_bodies'] or len(missing) != count):
        raise ValueError('Physical missing-body disclosure count changed')
    declared_map = {attempt_identity(row): row for row in declared}
    if (len(declared_map) != len(declared) or {attempt_identity(row): row for row in missing} != declared_map
            or any(row.get('status') != 'failed' or row.get('error_type') != 'HTTPError'
                   or re.search(r'(?<!\d)503(?!\d)', row.get('error', '')) is None for row in declared)):
        raise ValueError('Only exact hash-bound disclosed original HTTP503 rows may lack bodies')
    collisions = [{'signature': key[0], 'attempt': key[1], 'records': count}
                  for key, count in Counter((row['signature'], row['attempt']) for row in ledger).items() if count > 1]
    if proof.get('legacy_signature_attempt_number_collisions') != collisions:
        raise ValueError('Legacy ordinal collision disclosure changed')
    if (type(proof.get('attempt_starts_instrumentation_used')) is not bool
            or proof['attempt_starts_instrumentation_used'] != bool(modern)
            or (starts is None) != (proof.get('attempt_starts_ledger_sha256') is None)):
        raise ValueError('Attempt-start instrumentation/proof schema changed')
    if modern:
        if not isinstance(starts, list):
            raise ValueError('Modern physical start ledger required')
        startmap = {}
        for row in starts:
            attempt_identity(row); identity_id = row.get('attempt_id')
            if not isinstance(identity_id, str) or not identity_id.strip() or identity_id in startmap:
                raise ValueError('Modern start IDs missing or duplicated')
            startmap[identity_id] = row
        if set(startmap) != set(modern):
            raise ValueError('Modern started/completed attempt ID sets differ')
        for identity_id, row in modern.items():
            if any(startmap[identity_id].get(key) != row.get(key) for key in
                   ['signature', 'request_url', 'attempt', 'attempt_id', 'started_at_utc']):
                raise ValueError('Modern start/completion identity differs')
    elif starts is not None:
        raise ValueError('No fabricated unused attempt-start ledger is permitted')
    if (proof.get('recorded_transport_bodies_complete_except_declared_58') is not True
            or type(proof.get('unlogged_interrupted_attempts_maximum')) is not int
            or not 0 <= proof['unlogged_interrupted_attempts_maximum'] <= 16
            or proof.get('unlogged_interrupted_attempts_actual_count') is not None
            or proof.get('all_physical_network_attempts_complete') is not False):
        raise ValueError('Physical transport limitation scope changed')
    expected = [proof.get(key) for key in ('physical_attempts', 'received_attempt_bodies', 'failed_attempts')]
    if (any(type(value) is not int or value < 0 for value in expected)
            or expected != [len(ledger), len(bodies), sum(row['status'] == 'failed' for row in ledger)]):
        raise ValueError('Physical proof/ledger counts changed')
    return {'identities': identities, 'bodies': bodies, 'per_signature': per_signature, 'successful': successful,
            'ledger_rows': {attempt_identity(row): row for row in ledger},
            'recorded_missing_response_bodies': count, 'modern_attempt_ids': len(modern)}


def require_physical_ledger(source, *, physical_review_only=False):
    """Bind actual physical proof and bytes; physical-only mode never accepts prose."""
    proof_path = safe_path(PHYSICAL_REVIEW); proof = json.loads(proof_path.read_text())
    if physical_review_only:
        if source != proof:
            raise ValueError('Physical-only replay requires the actual retained independent receipt')
    else:
        if source.get('prior_physical_review_sha256') != sha(proof_path):
            raise ValueError('Independent physical proof binding missing or changed')
        for key in TRANSPORT_FIELDS:
            if key not in source or type(source[key]) is not type(proof.get(key)) or source[key] != proof.get(key):
                raise ValueError('Current source/physical transport proof differs: ' + key)
    ledger_path = safe_path('audit/news_physical_requests.jsonl')
    physical_path = safe_path('audit_work/physical_source_inventory.json')
    if (sha(ledger_path) != proof.get('ledger_sha256') or sha(physical_path) != proof.get('physical_source_inventory_sha256')
            or sha(safe_path('audit/news_query_plan.json')) != proof.get('query_plan_sha256')):
        raise ValueError('Physical ledger/inventory acceptance changed')
    limitation_path = safe_path(CAPTURE_LIMITATION)
    if (sha(limitation_path) != proof.get('discarded_error_body_limitations_sha256')
            or proof.get('input_bindings', {}).get(CAPTURE_LIMITATION) != sha(limitation_path)):
        raise ValueError('Physical failed-body whitelist hash changed')
    historical_context = {}
    for name, expected in proof.get('input_bindings', {}).items():
        # Coverage is historical phase context in the physical receipt. The
        # semantic projection updates it by design; the final source receipt
        # and source freeze separately bind its current bytes.
        if name == 'audit/news_coverage.json':
            current = sha(safe_path(name))
            if not physical_review_only and source.get('input_bindings', {}).get(name) != current:
                raise ValueError('Final source must bind current semantic coverage bytes')
            historical_context[name] = {'earlier_physical_review_sha256': expected, 'current_sha256': current,
                                        'original_bytes_retained': False,
                                        'status': 'original_coverage_bytes_unreplayable_auxiliary_phase_metadata',
                                        'reason': 'Coverage changes during semantic projection by design; only this named historical phase context differs. Current coverage requires fresh final source/freeze replay.'}
            continue
        if sha(safe_path(name)) != expected:
            raise ValueError('Independent physical input binding changed: ' + name)
    ledger = [json.loads(line) for line in ledger_path.read_text().splitlines() if line.strip()]
    inventory = json.loads(physical_path.read_text()); rows = inventory.get('files', [])
    starts_path = ROOT / ATTEMPT_STARTS
    starts = None
    if starts_path.exists():
        starts_path = safe_path(ATTEMPT_STARTS)
        if sha(starts_path) != proof.get('attempt_starts_ledger_sha256'):
            raise ValueError('Modern physical attempt-start ledger changed')
        starts = [json.loads(line) for line in starts_path.read_text().splitlines() if line.strip()]
    records = transport_records(ledger, proof, json.loads(limitation_path.read_text()), starts)
    signatures, bodies = records['per_signature'], records['bodies']
    if (type(proof.get('physical_requests')) is not int or proof['physical_requests'] != len(rows)
            or inventory.get('query_plan_sha256') != proof['query_plan_sha256']
            or len({row['signature'] for row in rows}) != len(rows)
            or {row['signature'] for row in rows} != set(signatures)
            or set(records['successful']) != set(signatures)):
        raise ValueError('Physical ledger/canonical signature scope changed')
    current_cache_attempts = set(); query_urls = {}
    for row in ledger:
        body = row.get('raw_response_path')
        if body:
            path = safe_path(body)
            if sha(path) != row.get('raw_compressed_sha256') or hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest() != row.get('raw_sha256'):
                raise ValueError('Physical immutable attempt bytes changed: ' + body)
    for row in rows:
        parsed = safe_path(row['parsed_cache_path']); raw = safe_path(row['raw_xml_path'])
        cache = json.loads(gzip.decompress(parsed.read_bytes()))
        attempts = cache.get('physical_attempts')
        if (not isinstance(attempts, list) or not attempts or type(row.get('physical_attempts')) is not int
                or row['physical_attempts'] != len(attempts) or cache.get('signature') != row['signature']
                or cache.get('status') != 'fetched' or cache.get('response_format_verified') is not True
                or not isinstance(cache.get('request_url'), str) or not cache['request_url']):
            raise ValueError('Current canonical cache attempt schema/count changed')
        query_urls[row['signature']] = cache['request_url']; successful = []
        for attempt in attempts:
            identity = attempt_identity(attempt)
            if (identity in current_cache_attempts or records['ledger_rows'].get(identity) != attempt
                    or attempt['signature'] != row['signature'] or attempt.get('request_url') != cache['request_url']):
                raise ValueError('Current cache attempt differs from immutable physical ledger')
            current_cache_attempts.add(identity)
            if attempt['status'] == 'fetched': successful.append(attempt)
        if (sha(parsed) != row['parsed_cache_sha256'] or sha(raw) != row['raw_xml_compressed_sha256']
                or hashlib.sha256(gzip.decompress(raw.read_bytes())).hexdigest() != row['raw_xml_uncompressed_sha256']
                or not successful or successful[-1]['raw_sha256'] != row['raw_xml_uncompressed_sha256']
                or cache.get('raw_response_path') != row['raw_xml_path']
                or cache.get('raw_sha256') != row['raw_xml_uncompressed_sha256']
                or cache.get('raw_response_compressed_sha256') != row['raw_xml_compressed_sha256']):
            raise ValueError('Physical canonical pair/successful-response bytes changed: ' + row['signature'])
    if any(row.get('request_url') != query_urls[row['signature']] for row in ledger):
        raise ValueError('Historical/current physical attempt URL differs from planned canonical query')
    present = {path.relative_to(ROOT).as_posix() for path in (ROOT / 'cache/rss_raw/attempts').rglob('*') if path.is_file()}
    if present != bodies:
        raise ValueError('Physical immutable-body directory differs from ledger')
    return {'physical_attempts': len(ledger), 'received_attempt_bodies': len(bodies), 'canonical_physical_requests': len(rows),
            'recorded_missing_response_bodies': records['recorded_missing_response_bodies'],
            'modern_attempt_ids': records['modern_attempt_ids'], 'physical_review_only': physical_review_only,
            'historical_superseded_cache_attempts': len(ledger) - len(current_cache_attempts),
            'all_physical_network_attempts_complete': False, 'unlogged_interrupted_attempts_maximum': proof['unlogged_interrupted_attempts_maximum'],
            'unlogged_interrupted_attempts_actual_count': None,
            'physical_proof_historical_context_only': historical_context}


def main():
    source_path = ROOT / 'audit/independent_source_review.json'
    market_path = ROOT / 'audit/independent_market_review.json'
    source = json.loads(source_path.read_text())
    market = json.loads(market_path.read_text())
    if (source.get('passed') is not True or market.get('passed') is not True
            or [row.get('date') for row in source.get('dates', [])] != DATES
            or market.get('dates') != DATES or source.get('errors') or market.get('errors')):
        raise ValueError('Accepted complete June source and market inputs required')
    require_ready_receipts(source)
    require_physical_ledger(source)
    public = public_research_export()
    paths = collect_paths()
    rows = []
    for candidate in sorted(paths):
        path = safe_path(candidate.relative_to(ROOT).as_posix())
        rows.append({'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(path), 'bytes': path.stat().st_size})
    if not rows or len({r['path'] for r in rows}) != len(rows):
        raise ValueError('Empty or duplicate packaging inputs')
    result = {
        'status': 'frozen_inputs_hash_bound', 'report_month': '2024-06', 'dates': DATES,
        'files': rows, 'file_count': len(rows),
        'source_acceptance_sha256': sha(source_path), 'market_acceptance_sha256': sha(market_path),
        'public_research_projection': {key: value for key, value in public.items() if key != 'commitments'},
        'scope': 'Exact June raw RSS, parsed request caches, per-headline provenance, acquisition and staged-feed comparison proof, retained Yahoo raw payloads/action audit/Treasury inputs, independent replay code/results, actual exclusions/revisions if present, and newest-code discovery. The artifact builder separately includes final feeds, cards, specifications, component drafts, selection notes, reviews and tools. Author scratch, repository clones, secrets and earlier retrospective inputs are excluded.'}
    write(ROOT / 'audit/news_replay_inventory.json', result)
    print(json.dumps({'files': len(rows), 'bytes': sum(r['bytes'] for r in rows),
                      'inventory_sha256': sha(ROOT / 'audit/news_replay_inventory.json')}))


if __name__ == '__main__':
    main()
