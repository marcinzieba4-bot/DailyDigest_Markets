"""Hash-bind April's exact acquisition, screened inputs and public replay payload.

Private web-research responses live in the sibling april-private-research folder.
Only finite hash commitments, document metadata and release clocks enter the public
archive. Every successful RSS response and every retained market input stays exact.
This tool acquires nothing and cannot accept its own engineering/editorial review.
"""
from pathlib import Path, PurePosixPath
import datetime as dt
import gzip
import hashlib
import json
import re
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
PRIVATE_ROOT = ROOT.parent / 'april-private-research'
DATES = [dt.date(2024, 4, n).isoformat() for n in range(1, 31) if dt.date(2024, 4, n).weekday() < 5]
REPLAY_ROOTS = ('cache/news', 'cache/rss_raw', 'audit/news_provenance', 'audit/market_raw',
    'work/source_candidates', 'work/unreviewed_feeds', 'work/acquisition_feeds',
    'exclusions', 'source_supplements', 'audit/source_amendments', 'audit/review_history', 'audit_work')
FORBIDDEN_PARTS = {'.git', '.aws', '.ssh', '__pycache__', 'node_modules', 'repo', 'repository', 'credentials', 'secrets'}
FORBIDDEN_NAMES = {'source_inventory.json', 'news_replay_inventory.json', 'artifact_manifest.json',
    'final_artifact_review.json', 'source_archive_build.json', 'delivery_verification.json',
    'publication.json', 'archive_index_reconciliation.json'}
PHYSICAL_REVIEW = 'audit/independent_physical_source_review.json'
CAPTURE_LIMITATION = 'audit_work/acquisition_capture_limitation.json'
ATTEMPT_STARTS = 'audit/news_physical_attempt_starts.jsonl'
TRANSPORT_FIELDS = ('physical_requests', 'physical_attempts', 'received_attempt_bodies', 'failed_attempts',
    'recorded_missing_response_bodies', 'discarded_error_body_limitations_sha256',
    'legacy_signature_attempt_number_collisions', 'unlogged_interrupted_attempts_maximum',
    'unlogged_interrupted_attempts_actual_count', 'all_physical_network_attempts_complete',
    'attempt_starts_ledger_sha256', 'attempt_starts_instrumentation_used', 'ledger_sha256',
    'query_plan_sha256', 'physical_source_inventory_sha256', 'journaled_attempt_starts',
    'journaled_interrupted_attempts', 'all_completed_attempts_accounted_for', 'planned_canonical_successes_complete')
PRIVATE_MANIFEST = 'audit/private_research_commitments.json'
PUBLIC_RESEARCH_MANIFEST = 'audit/public_research_manifest.json'
PUBLIC_CLOCK_EVIDENCE = 'audit/public_clock_evidence.json'
PUBLIC_RESEARCH_ATTESTATION = 'audit/public_research_attestation.json'
PUBLIC_RESEARCH_REVIEW = 'audit/independent_public_research_projection_review.json'
CODE_PROVENANCE_FILES = ('source/lambda_function.py', 'code_provenance.json')


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def is_raw_web_response(value):
    if isinstance(value, str):
        if 'content' in value and value.lstrip().startswith(('{', '[')):
            try: return is_raw_web_response(json.loads(value))
            except ValueError: pass
        return False
    if isinstance(value, list): return any(is_raw_web_response(item) for item in value)
    if not isinstance(value, dict): return False
    blocks = value.get('content')
    if isinstance(blocks, list):
        text = '\n'.join(item.get('text', '') for item in blocks if isinstance(item, dict) and item.get('type') == 'text')
        if re.search(r'https?://', text) and re.search(r'【turn|\[wordlim[: ]|Total lines:', text): return True
    return any(is_raw_web_response(item) for item in value.values())


def assert_no_raw_web_candidates(read, names):
    for name in names:
        blob = read(name)
        if blob[:2] == b'\x1f\x8b': blob = gzip.decompress(blob)
        if b'content' not in blob: continue
        try: values = [json.loads(blob)]
        except (ValueError, UnicodeDecodeError):
            values = []
            for line in blob.splitlines():
                if line.lstrip()[:1] in {b'{', b'['}:
                    try: values.append(json.loads(line))
                    except (ValueError, UnicodeDecodeError): pass
        if any(is_raw_web_response(value) for value in values):
            raise ValueError('Private raw research response entered public candidates: ' + name)


def private_path(name):
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or str(p) != name or '\\' in name:
        raise ValueError('Unsafe private research commitment name')
    path = PRIVATE_ROOT / name
    if (not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(PRIVATE_ROOT)
        or any(p.is_symlink() for p in path.parents if p.is_relative_to(PRIVATE_ROOT))):
        raise ValueError('Missing/unsafe private research original: ' + name)
    return path


def scan_private_research():
    """Reject private responses within ROOT; enumerate actual sibling originals."""
    in_root = []
    for folder in ['audit_work', 'audit']:
        for path in (ROOT / folder).rglob('*'):
            if not path.is_file() or not path.name.endswith(('.json', '.json.gz')): continue
            try:
                blob = path.read_bytes()
                if path.suffix == '.gz': blob = gzip.decompress(blob)
                if is_raw_web_response(json.loads(blob)): in_root.append(path.relative_to(ROOT).as_posix())
            except (ValueError, UnicodeDecodeError): continue
    if in_root: raise ValueError('Move raw research outside the public root: ' + repr(sorted(in_root)))
    names=sorted(p.relative_to(PRIVATE_ROOT).as_posix() for p in PRIVATE_ROOT.rglob('*')
                  if p.is_file() and not p.name.startswith('.') and p.name.endswith(('.json', '.json.gz')))
    for name in names: private_path(name)
    return names


def private_commitments():
    path = ROOT / PRIVATE_MANIFEST
    obj = json.loads(path.read_bytes())
    if set(obj) != {'schema', 'scope', 'files'} or obj['schema'] != 'april-private-research-commitments-v1':
        raise ValueError('Explicit April private-research commitment manifest required')
    if not isinstance(obj['scope'], str) or not obj['scope'].strip() or len(obj['scope']) > 500:
        raise ValueError('Explicit bounded private-research commitment scope required')
    rows = obj['files']
    if not isinstance(rows, list) or not rows: raise ValueError('Private research commitments are empty')
    out = {}
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {'path', 'sha256', 'bytes'} or row.get('path') in out
            or not isinstance(row.get('path'), str) or not re.fullmatch(r'[0-9a-f]{64}', str(row.get('sha256')))
            or type(row.get('bytes')) is not int or row['bytes'] <= 0):
            raise ValueError('Invalid private-research commitment')
        out[row['path']] = row
    if list(out) != sorted(out): raise ValueError('Private commitments must be sorted')
    return out


def preserve_private_commitments(rows):
    """Preserve reviewed manifest bytes; a changed original set needs fresh review."""
    path = ROOT / PRIVATE_MANIFEST
    if path.exists():
        original = path.read_bytes()
        if list(private_commitments().values()) != rows:
            raise ValueError('Private research original set/bytes changed; refresh independent commitments first')
        if path.read_bytes() != original:
            raise ValueError('Private commitments changed during public preparation')
        return hashlib.sha256(original).hexdigest()
    write(path, {'schema': 'april-private-research-commitments-v1',
        'scope': 'Hashes of external sibling private research originals; their response prose is not exported.',
        'files': rows})
    if list(private_commitments().values()) != rows:
        raise ValueError('New private commitments differ from retained original rows')
    return sha(path)


def public_document_headers():
    sources = {}
    header = re.compile(r'^([^\n]{1,500}?)\s+\((https?://[^\s)]+)\)\s*\r?\n(?=【turn[^】]*】)', re.M)
    for name in sorted(private_commitments()):
        blob = private_path(name).read_bytes()
        if name.endswith('.gz'): blob = gzip.decompress(blob)
        value = json.loads(blob)
        if isinstance(value, dict) and isinstance(value.get('result'), dict): value=value['result']
        for block in value.get('content', []) if isinstance(value, dict) else []:
            if not isinstance(block, dict) or block.get('type') != 'text': continue
            for title, url in header.findall(block.get('text', '')):
                title = ' '.join(title.split()[:25])[:240]
                item = sources.setdefault(url, {'url': url, 'title': title, 'private_response_refs': [], 'quote': ''})
                if name not in item['private_response_refs']: item['private_response_refs'].append(name)
    return [sources[url] for url in sorted(sources)]


def public_clock_rows(schedule):
    keys = ['label', 'release_utc', 'calendar_release_utc_date', 'timing_precision', 'eligible_edition', 'earliest_pub_date', 'kind', 'evidence']
    return [{key: row[key] for key in keys if key in row} for row in schedule['guards']]


def validate_public_research_bundle(read, names, source, *, local_originals=False, require_review=True):
    names = set(names)
    def record(name):
        if name not in names: raise ValueError('Missing public research projection member: ' + name)
        return json.loads(read(name))
    manifest_blob = read(PUBLIC_RESEARCH_MANIFEST); manifest = record(PUBLIC_RESEARCH_MANIFEST)
    evidence_blob = read(PUBLIC_CLOCK_EVIDENCE); evidence = record(PUBLIC_CLOCK_EVIDENCE)
    attestation_blob = read(PUBLIC_RESEARCH_ATTESTATION); attestation = record(PUBLIC_RESEARCH_ATTESTATION)
    private = record(PRIVATE_MANIFEST)
    if set(private)!={'schema','scope','files'} or not isinstance(private.get('files'),list) or not private['files']:
        raise ValueError('Explicit nonempty private commitment rows required')
    for row in private['files']:
        if (not isinstance(row,dict) or set(row)!={'path','sha256','bytes'} or not isinstance(row.get('path'),str)
            or PurePosixPath(row['path']).is_absolute() or '..' in PurePosixPath(row['path']).parts
            or str(PurePosixPath(row['path']))!=row['path'] or '\\' in row['path']
            or not re.fullmatch(r'[0-9a-f]{64}',str(row.get('sha256')))
            or type(row.get('bytes')) is not int or row['bytes']<=0):
            raise ValueError('Invalid private original research hash commitment')
    commitments = {row['path']: row for row in private['files']}
    if (private.get('schema') != 'april-private-research-commitments-v1'
        or list(commitments) != sorted(commitments) or len(commitments) != len(private['files'])):
        raise ValueError('Invalid/duplicate private research hash manifest')
    expected_manifest = {'schema': 'april-public-research-projection-v1',
        'status': 'public_projection_with_private_original_hash_commitments',
        'source_acceptance_sha256': hashlib.sha256(read('audit/independent_source_review.json')).hexdigest(),
        'private_commitments_sha256': hashlib.sha256(read(PRIVATE_MANIFEST)).hexdigest(),
        'clock_policy_path': 'audit_work/april_release_schedule.json',
        'clock_policy_sha256': hashlib.sha256(read('audit_work/april_release_schedule.json')).hexdigest(),
        'evidence_path': PUBLIC_CLOCK_EVIDENCE, 'evidence_sha256': hashlib.sha256(evidence_blob).hexdigest(),
        'private_files': list(commitments.values()), 'private_file_count': len(commitments),
        'export_scope': 'Compact clock evidence; original full research responses are private and are not publicly byte-replayed.'}
    if manifest != expected_manifest: raise ValueError('Public research manifest/source/clock/hash binding changed')
    if set(evidence) != {'schema', 'clock_policy_sha256', 'clock_rows', 'sources', 'quote_word_limit_per_url', 'scope'}:
        raise ValueError('Unexpected public clock-evidence fields')
    if (evidence.get('schema') != 'april-public-clock-evidence-v1'
        or evidence.get('clock_policy_sha256') != manifest['clock_policy_sha256']
        or evidence.get('clock_rows') != public_clock_rows(json.loads(read(manifest['clock_policy_path'])))
        or evidence.get('quote_word_limit_per_url') != 25
        or evidence.get('scope') != 'Factual clock metadata from unchanged guards and document headings/URLs only; no article-body text or quotations.'):
        raise ValueError('Public clock facts/scope changed')
    urls = []
    for item in evidence.get('sources', []):
        if (set(item) != {'url', 'title', 'private_response_refs', 'quote'}
            or not isinstance(item['url'], str) or not item['url'].startswith(('https://', 'http://'))
            or not isinstance(item['title'], str) or len(item['title']) > 240 or len(item['title'].split()) > 25
            or item['quote'] != '' or not item['private_response_refs']
            or len(set(item['private_response_refs'])) != len(item['private_response_refs'])
            or not set(item['private_response_refs']) <= set(commitments)):
            raise ValueError('Public research metadata exceeds finite no-quotation scope')
        urls.append(item['url'])
    if not urls or urls != sorted(set(urls)): raise ValueError('Empty/unsorted public document metadata')
    expected_attestation = {'schema': 'april-public-research-export-attestation-v1', 'status': 'hash_and_scope_attestation',
        'manifest_sha256': hashlib.sha256(manifest_blob).hexdigest(), 'evidence_sha256': hashlib.sha256(evidence_blob).hexdigest(),
        'validator_sha256': hashlib.sha256(read('tools/build_source_inventory.py')).hexdigest(),
        'source_acceptance_sha256': manifest['source_acceptance_sha256'],
        'private_originals_retained_locally': True, 'public_original_research_byte_replay': False,
        'financial_RSS_market_feed_guard_or_proof_omitted': False, 'copied_article_body_words': 0, 'independent_acceptance': False}
    if attestation != expected_attestation: raise ValueError('Public research hash/scope attestation changed')
    if local_originals:
        if scan_private_research() != list(commitments): raise ValueError('External private original set changed')
        for name, row in commitments.items():
            path = private_path(name)
            if sha(path) != row['sha256'] or path.stat().st_size != row['bytes']:
                raise ValueError('Private original research bytes changed: ' + name)
        if evidence['sources'] != public_document_headers(): raise ValueError('Document metadata differs from private response headings')
    else: assert_no_raw_web_candidates(read, names)
    if require_review:
        review = record(PUBLIC_RESEARCH_REVIEW)
        expected = {'manifest_sha256': hashlib.sha256(manifest_blob).hexdigest(),
            'evidence_sha256': hashlib.sha256(evidence_blob).hexdigest(), 'attestation_sha256': hashlib.sha256(attestation_blob).hexdigest(),
            'source_acceptance_sha256': manifest['source_acceptance_sha256'], 'validator_sha256': attestation['validator_sha256']}
        if (review.get('status') != 'accepted' or review.get('passed') is not True
            or type(review.get('fatal_or_major_remaining')) is not int or review['fatal_or_major_remaining'] != 0
            or review.get('scope') != 'public_research_projection_engineering_only'
            or any(review.get(k) != v for k, v in expected.items())):
            raise ValueError('Separate current engineering review of public research export required')
    return {'commitments': commitments, 'manifest_sha256': hashlib.sha256(manifest_blob).hexdigest(),
        'private_response_count': len(commitments), 'public_clock_rows': len(evidence['clock_rows']),
        'public_document_URLs': len(urls), 'original_research_byte_replay': False,
        'local_originals_verified': local_originals, 'independent_review_required': require_review}


def public_research_export(*, require_review=True):
    source = json.loads((ROOT / 'audit/independent_source_review.json').read_bytes())
    names = {PRIVATE_MANIFEST, PUBLIC_RESEARCH_MANIFEST, PUBLIC_CLOCK_EVIDENCE, PUBLIC_RESEARCH_ATTESTATION,
        PUBLIC_RESEARCH_REVIEW, 'audit/independent_source_review.json', 'audit_work/april_release_schedule.json', 'tools/build_source_inventory.py'}
    return validate_public_research_bundle(lambda name: (ROOT / name).read_bytes(), names, source,
                                          local_originals=True, require_review=require_review)


def prepare_public_research():
    """Derive finite public commitments/metadata; never write an acceptance."""
    names=scan_private_research()
    if not names: raise ValueError('No retained private research originals')
    rows=[{'path': n, 'sha256': sha(private_path(n)), 'bytes': private_path(n).stat().st_size} for n in names]
    commitments_sha = preserve_private_commitments(rows)
    source = json.loads((ROOT/'audit/independent_source_review.json').read_bytes())
    if source.get('input_bindings', {}).get(PRIVATE_MANIFEST) != commitments_sha:
        raise ValueError('Private commitments are not bound by current independent source review')
    source_sha=sha(ROOT/'audit/independent_source_review.json');clock_sha=sha(ROOT/'audit_work/april_release_schedule.json')
    evidence={'schema':'april-public-clock-evidence-v1', 'clock_policy_sha256':clock_sha,
        'clock_rows':public_clock_rows(json.loads((ROOT/'audit_work/april_release_schedule.json').read_bytes())),
        'sources':public_document_headers(), 'quote_word_limit_per_url':25,
        'scope':'Factual clock metadata from unchanged guards and document headings/URLs only; no article-body text or quotations.'}
    write(ROOT/PUBLIC_CLOCK_EVIDENCE,evidence)
    manifest={'schema':'april-public-research-projection-v1','status':'public_projection_with_private_original_hash_commitments',
        'source_acceptance_sha256':source_sha,'private_commitments_sha256':sha(ROOT/PRIVATE_MANIFEST),
        'clock_policy_path':'audit_work/april_release_schedule.json','clock_policy_sha256':clock_sha,
        'evidence_path':PUBLIC_CLOCK_EVIDENCE,'evidence_sha256':sha(ROOT/PUBLIC_CLOCK_EVIDENCE),
        'private_files':rows,'private_file_count':len(rows),
        'export_scope':'Compact clock evidence; original full research responses are private and are not publicly byte-replayed.'}
    write(ROOT/PUBLIC_RESEARCH_MANIFEST,manifest)
    write(ROOT/PUBLIC_RESEARCH_ATTESTATION,{'schema':'april-public-research-export-attestation-v1','status':'hash_and_scope_attestation',
        'manifest_sha256':sha(ROOT/PUBLIC_RESEARCH_MANIFEST),'evidence_sha256':sha(ROOT/PUBLIC_CLOCK_EVIDENCE),
        'validator_sha256':sha(Path(__file__)),'source_acceptance_sha256':source_sha,
        'private_originals_retained_locally':True,'public_original_research_byte_replay':False,
        'financial_RSS_market_feed_guard_or_proof_omitted':False,'copied_article_body_words':0,'independent_acceptance':False})
    return public_research_export(require_review=False)


def safe_path(relative):
    rel=PurePosixPath(relative)
    if rel.is_absolute() or '..' in rel.parts or str(rel)!=relative or '\\' in relative:
        raise ValueError('Unsafe source path: '+relative)
    if set(rel.parts)&FORBIDDEN_PARTS or rel.name in FORBIDDEN_NAMES or any(p.startswith('.') for p in rel.parts):
        raise ValueError('Excluded source path: '+relative)
    if any(x in rel.name.lower() for x in ('secret','credential','.pem','.key')):
        raise ValueError('Sensitive source filename: '+relative)
    if any(month!='2024-04' for month in re.findall(r'20\d{2}-\d{2}(?=-\d{2}(?:\D|$))',relative)):
        raise ValueError('Other report-month path: '+relative)
    allowed=any(relative.startswith(folder+'/') for folder in REPLAY_ROOTS)
    allowed |= relative in CODE_PROVENANCE_FILES
    allowed |= len(rel.parts) == 2 and rel.parts[0] == 'tools' and rel.suffix == '.py'
    allowed |= relative.startswith('audit/') and len(rel.parts)==2 and rel.suffix in {'.json','.jsonl','.csv'}
    if not allowed or not relative.endswith(('.json','.jsonl','.json.gz','.xml.gz','.http-error.gz','.py','.csv','.log','.txt')):
        raise ValueError('Unapproved replay path: '+relative)
    path=ROOT/rel
    if (not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(ROOT)
        or any(p.is_symlink() for p in path.parents if p.is_relative_to(ROOT))):
        raise ValueError('Missing/unsafe replay member: '+relative)
    return path


def collect_paths():
    paths=set()
    for folder in REPLAY_ROOTS:
        paths.update(p for p in (ROOT/folder).rglob('*') if p.is_file() and p.name not in FORBIDDEN_NAMES
            and '__pycache__' not in p.parts and p.name.endswith(('.json','.jsonl','.json.gz','.xml.gz','.http-error.gz','.py','.csv','.log','.txt')))
    paths.update((ROOT/'audit').glob('*.csv'));paths.update((ROOT/'audit').glob('*.jsonl'))
    paths.update(p for p in (ROOT/'audit').glob('*.json') if p.name not in FORBIDDEN_NAMES
        and not p.name.startswith(('independent_nonretail_','independent_retail_')))
    paths.update(ROOT/n for n in CODE_PROVENANCE_FILES)
    require_code_provenance()
    return {safe_path(p.relative_to(ROOT).as_posix()) for p in paths}


def require_code_provenance(source=None, read=None, names=None):
    """Bind the actual retained repository source without claiming deployed equality."""
    read = read or (lambda name: safe_path(name).read_bytes())
    if names is not None and not set(CODE_PROVENANCE_FILES) <= set(names):
        raise ValueError('Retained newest source/provenance missing from replay')
    payload, metadata = (read(name) for name in CODE_PROVENANCE_FILES)
    provenance = json.loads(metadata)
    if (provenance.get('source_path') != 'lambda_function.py'
        or type(provenance.get('source_bytes')) is not int
        or provenance['source_bytes'] != len(payload)
        or provenance.get('source_sha256') != hashlib.sha256(payload).hexdigest()
        or not re.fullmatch(r'[0-9a-f]{40}', provenance.get('source_commit', ''))):
        raise ValueError('Retained newest source differs from code provenance')
    if source is not None:
        bindings = source.get('input_bindings', {})
        for name, blob in zip(CODE_PROVENANCE_FILES, (payload, metadata)):
            if bindings.get(name) != hashlib.sha256(blob).hexdigest():
                raise ValueError('Source review lacks current retained-code binding: ' + name)
    return {'retained_source_path': CODE_PROVENANCE_FILES[0],
        'repository_source_path': provenance['source_path'],
        'source_commit': provenance['source_commit'],
        'source_sha256': provenance['source_sha256'], 'source_bytes': len(payload),
        'code_provenance_sha256': hashlib.sha256(metadata).hexdigest(),
        'deployed_source_equality_asserted': False}


def require_ready_receipts(source):
    bindings=source.get('input_bindings')
    if not isinstance(bindings,dict) or not bindings:raise ValueError('Current source bindings required')
    if [r.get('date')for r in source.get('dates',[])]!=DATES:raise ValueError('Complete22-date screening scope required')
    for row in source['dates']:
        date=row['date'];name=f'audit/news_ready_{date}.json';p=safe_path(name);r=json.loads(p.read_bytes())
        if (bindings.get(name)!=sha(p) or row.get('ready_receipt_sha256')!=sha(p) or r.get('date')!=date
            or r.get('status')!='ready' or r.get('ready_sha256')!=row.get('feed_sha256')
            or r.get('unreviewed_sha256')!=row.get('raw_sha256')):raise ValueError('Stale screening receipt: '+date)
        counts=[r.get(k)for k in ('input_items','ready_items','excluded_items')]
        if (any(type(v)is not int or v<0 for v in counts) or counts!=[row.get(k)for k in ('raw_items','ready_items','excluded')]
            or not isinstance(r.get('excluded'),list) or counts[2]!=len(r['excluded']) or counts[0]!=counts[1]+counts[2]):
            raise ValueError('Invalid source-screening counts: '+date)
        ids=[x.get('id')if isinstance(x,dict)else None for x in r['excluded']]
        if any(not isinstance(x,str)or not re.fullmatch(r'n\d{4,6}',x)for x in ids)or len(set(ids))!=len(ids):
            raise ValueError('Invalid screening exclusions: '+date)


def utc_clock(value):
    if not isinstance(value,str)or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)',value):
        raise ValueError('Actual explicit UTC clock required')
    return dt.datetime.fromisoformat(value.replace('Z','+00:00'))
def attempt_identity(row):
    if not isinstance(row.get('signature'),str)or not row['signature']or type(row.get('attempt'))is not int or row['attempt']<1:
        raise ValueError('Invalid physical attempt identity')
    utc_clock(row.get('started_at_utc'));return row['signature'],row['attempt'],row['started_at_utc']


def inspect_transport():
    """Replay actual canonical/attempt bytes and derive an unsigned inventory."""
    plan=json.loads(safe_path('audit/news_query_plan.json').read_bytes())
    if plan.get('dates')!=DATES or plan.get('status')!='all_requests_acquired_caps_resolved':
        raise ValueError('Complete final April query plan required for transport replay')
    planned=plan.get('requests',[])
    if not planned or len({r.get('signature') for r in planned})!=len(planned):raise ValueError('Invalid complete query plan')
    ledger_path=safe_path('audit/news_physical_requests.jsonl');starts_path=safe_path(ATTEMPT_STARTS)
    ledger=[json.loads(s)for s in ledger_path.read_text().splitlines()if s.strip()]
    starts=[json.loads(s)for s in starts_path.read_text().splitlines()if s.strip()]
    if not ledger or not starts:raise ValueError('Complete modern start/completion ledgers required')
    ids={};startmap={};bodies=set();signatures={};missing=[]
    for row in starts:
        attempt_identity(row);key=row.get('attempt_id')
        if not isinstance(key,str)or not key or key in startmap:raise ValueError('Missing/duplicate actual start ID')
        startmap[key]=row
    for row in ledger:
        attempt_identity(row);key=row.get('attempt_id')
        if not isinstance(key,str)or not key or key in ids:raise ValueError('Missing/duplicate completion ID')
        if key not in startmap or any(startmap[key].get(k)!=row.get(k)for k in ['signature','request_url','attempt','attempt_id','started_at_utc']):
            raise ValueError('Start/completion identity mismatch')
        if utc_clock(row.get('finished_at_utc'))<utc_clock(row['started_at_utc']):raise ValueError('Attempt finishes before start')
        if row.get('status')not in {'fetched','failed'}:raise ValueError('Unknown request result')
        ids[key]=row;signatures.setdefault(row['signature'],[]).append(row)
        body=row.get('raw_response_path')
        if body:
            if body in bodies or not body.startswith('cache/rss_raw/attempts/'):raise ValueError('Reused/non-attempt response body')
            bodies.add(body);p=safe_path(body)
            if sha(p)!=row.get('raw_compressed_sha256')or hashlib.sha256(gzip.decompress(p.read_bytes())).hexdigest()!=row.get('raw_sha256'):
                raise ValueError('Physical response bytes changed: '+body)
        elif row['status']=='fetched':raise ValueError('Successful request lost its body')
        else:missing.append(row)
    interrupted=[row for row in starts if row['attempt_id']not in ids]
    limitation=json.loads(safe_path(CAPTURE_LIMITATION).read_bytes())
    if (limitation.get('unmatched_attempt_starts')!=interrupted
        or type(limitation.get('unmatched_attempt_start_count_at_review'))is not int
        or limitation['unmatched_attempt_start_count_at_review']!=len(interrupted)):
        raise ValueError('Journaled interrupted start set differs from explicit outage disclosure')
    if interrupted and limitation.get('status')!='explicit_environment_outage_capture_gap':
        raise ValueError('Actual journaled outage requires its explicit capture disclosure')
    rows=[]
    for signature,attempts in sorted(signatures.items()):
        parsed=safe_path('cache/news/'+signature+'.json.gz');cache=json.loads(gzip.decompress(parsed.read_bytes()))
        raw=safe_path(cache['raw_response_path']);raw_sha=hashlib.sha256(gzip.decompress(raw.read_bytes())).hexdigest()
        retained=cache.get('physical_attempts',[])
        if cache.get('signature')!=signature or cache.get('status')!='fetched'or cache.get('response_format_verified')is not True or not retained:
            raise ValueError('Canonical successful parsed cache missing')
        if any(ids.get(a.get('attempt_id'))!=a or a.get('signature')!=signature or a.get('request_url')!=cache.get('request_url')for a in retained):
            raise ValueError('Canonical attempt differs from ledger')
        success=[a for a in retained if a['status']=='fetched']
        if not success or success[-1]['raw_sha256']!=raw_sha or cache.get('raw_sha256')!=raw_sha or cache.get('raw_response_compressed_sha256')!=sha(raw):
            raise ValueError('Canonical RSS bytes differ from successful response')
        if any(a.get('request_url')!=cache.get('request_url')for a in attempts):raise ValueError('Request URL changed for physical signature')
        rows.append({'signature':signature,'parsed_cache_path':parsed.relative_to(ROOT).as_posix(),'parsed_cache_sha256':sha(parsed),
            'raw_xml_path':raw.relative_to(ROOT).as_posix(),'raw_xml_compressed_sha256':sha(raw),
            'raw_xml_uncompressed_sha256':raw_sha,'physical_attempts':len(retained)})
    if {r['signature'] for r in planned}!=set(signatures):raise ValueError('Physical signature set differs from complete plan')
    for row in interrupted:
        if row['signature']not in signatures or not any(r.get('status')=='fetched'and r.get('request_url')==row.get('request_url')for r in signatures[row['signature']]):
            raise ValueError('Interrupted query has no retained exact-URL canonical success')
    by_signature={r['signature']:r for r in rows}
    for planned_row in planned:
        current=by_signature[planned_row['signature']]
        if (planned_row.get('status')!='fetched' or planned_row.get('cache_path')!=current['parsed_cache_path']
            or planned_row.get('cache_sha256')!=current['parsed_cache_sha256']
            or planned_row.get('raw_response_path')!=current['raw_xml_path']
            or planned_row.get('raw_response_compressed_sha256')!=current['raw_xml_compressed_sha256']
            or planned_row.get('raw_sha256')!=current['raw_xml_uncompressed_sha256']):
            raise ValueError('Physical canonical bytes differ from final query-plan declaration')
    present={p.relative_to(ROOT).as_posix()for p in (ROOT/'cache/rss_raw/attempts').rglob('*')if p.is_file()}
    if present!=bodies:raise ValueError('Attempt body directory differs from immutable ledger')
    collisions=[{'signature':k[0],'attempt':k[1],'records':n}for k,n in Counter((r['signature'],r['attempt'])for r in ledger).items()if n>1]
    return {'inventory':{'query_plan_sha256':sha(safe_path('audit/news_query_plan.json')),'files':rows},
        'missing_attempts':missing,'interrupted_attempt_starts':interrupted,'counts':{'physical_requests':len(rows),'physical_attempts':len(ledger),
        'received_attempt_bodies':len(bodies),'failed_attempts':sum(r['status']=='failed'for r in ledger),
        'recorded_missing_response_bodies':len(missing),'legacy_signature_attempt_number_collisions':collisions,
        'unlogged_interrupted_attempts_maximum':0,'unlogged_interrupted_attempts_actual_count':0,
        'all_physical_network_attempts_complete':not bool(interrupted),'attempt_starts_instrumentation_used':True,
        'journaled_attempt_starts':len(starts),'journaled_interrupted_attempts':len(interrupted),
        'all_completed_attempts_accounted_for':True,'planned_canonical_successes_complete':True,
        'attempt_starts_ledger_sha256':sha(starts_path),'ledger_sha256':sha(ledger_path),
        'query_plan_sha256':sha(safe_path('audit/news_query_plan.json'))}}


def require_physical_ledger(source, *, physical_review_only=False):
    p=safe_path(PHYSICAL_REVIEW);proof=json.loads(p.read_bytes())
    if (proof.get('status')!='physical_infrastructure_replay_passed'or proof.get('passed')is not True
        or proof.get('errors')or proof.get('authoring_acceptance')is not False or proof.get('dates')!=DATES):
        raise ValueError('Independent exact22-date physical replay acceptance required')
    if physical_review_only:
        if source!=proof:raise ValueError('Physical-only mode needs actual independent receipt')
    elif source.get('prior_physical_review_sha256')!=sha(p):raise ValueError('Final source acceptance lost physical review binding')
    current=inspect_transport();inventory_path=safe_path('audit_work/physical_source_inventory.json')
    if json.loads(inventory_path.read_bytes())!=current['inventory']:raise ValueError('Physical inventory changed')
    expected=dict(current['counts'],physical_source_inventory_sha256=sha(inventory_path))
    limitation_path=safe_path(CAPTURE_LIMITATION);limitation=json.loads(limitation_path.read_bytes())
    if (limitation.get('affected_attempts')!=current['missing_attempts']
        or limitation.get('recorded_failed_attempts_missing_bodies')!=len(current['missing_attempts'])
        or any(r.get('status')!='failed'for r in current['missing_attempts'])):
        raise ValueError('Actual failed-body capture disclosure differs from ledger')
    expected['discarded_error_body_limitations_sha256']=sha(limitation_path)
    for k,v in expected.items():
        if type(proof.get(k))is not type(v)or proof[k]!=v:raise ValueError('Physical receipt differs from actual replay: '+k)
    if not physical_review_only:
        for k in TRANSPORT_FIELDS:
            if type(source.get(k))is not type(proof.get(k))or source.get(k)!=proof.get(k):raise ValueError('Final source/physical proof differs: '+k)
    for name,digest in proof.get('input_bindings',{}).items():
        if sha(safe_path(name))!=digest:raise ValueError('Independent physical input changed: '+name)
    return dict(current['counts'],physical_review_only=physical_review_only)


def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--prepare-public-research',action='store_true');parser.add_argument('--inspect-transport',action='store_true');args=parser.parse_args()
    if args.prepare_public_research:
        result=prepare_public_research();print(json.dumps({k:v for k,v in result.items()if k!='commitments'},indent=2));return
    if args.inspect_transport:
        result=inspect_transport();write(ROOT/'audit_work/physical_source_inventory_candidate.json',result['inventory'])
        write(ROOT/'audit_work/transport_counts_candidate.json',{'counts':result['counts'],'missing_attempts':result['missing_attempts'],'interrupted_attempt_starts':result['interrupted_attempt_starts']})
        print(json.dumps(result['counts'],indent=2));return
    source_path=ROOT/'audit/independent_source_review.json';market_path=ROOT/'audit/independent_market_review.json'
    source=json.loads(source_path.read_bytes());market=json.loads(market_path.read_bytes())
    if (source.get('passed')is not True or market.get('passed')is not True or [r.get('date')for r in source.get('dates',[])]!=DATES
        or market.get('dates')!=DATES or source.get('errors')or market.get('errors')):raise ValueError('Accepted complete April source/market inputs required')
    require_ready_receipts(source);require_physical_ledger(source);require_code_provenance(source);public=public_research_export();paths=collect_paths()
    rows=[{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size}for p in sorted(paths)]
    assert_no_raw_web_candidates(lambda n:(ROOT/n).read_bytes(),[r['path']for r in rows])
    if not rows or len({r['path']for r in rows})!=len(rows):raise ValueError('Empty/duplicate packaging inputs')
    result={'status':'frozen_inputs_hash_bound','report_month':'2024-04','dates':DATES,'files':rows,'file_count':len(rows),
        'source_acceptance_sha256':sha(source_path),'market_acceptance_sha256':sha(market_path),
        'public_research_projection':{k:v for k,v in public.items()if k!='commitments'},
        'scope':'Exact April RSS/caches/attempt bodies, own-date provenance and screening, bounded market/Treasury inputs, actual audit/tool dependencies, and compact external-private-research hash commitments. No private response prose or prior retrospective inputs.'}
    write(ROOT/'audit/news_replay_inventory.json',result);print(json.dumps({'files':len(rows),'bytes':sum(r['bytes']for r in rows),'inventory_sha256':sha(ROOT/'audit/news_replay_inventory.json')}))


if __name__=='__main__':main()
