"""Hash-bind exact July acquisition/replay inputs; never acquire or change evidence.

Author scripts, repository clones, deployments, secrets and older report sets are
outside the explicit packaging roots. Bounded lookback observations acquired for
a July cutoff may of course precede July; no prior retrospective input is reused.
"""
from pathlib import Path, PurePosixPath
import datetime as dt
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parent.parent
DATES = [dt.date(2024, 7, n).isoformat() for n in range(1, 32)
         if dt.date(2024, 7, n).weekday() < 5]
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
                   'delivery_verification.json', 'publication.json'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def safe_path(relative):
    """Validate a replay member against explicit paths; never follow symlinks."""
    rel = PurePosixPath(relative)
    if rel.is_absolute() or '..' in rel.parts or str(rel) != relative or '\\' in relative:
        raise ValueError('Unsafe source path: ' + relative)
    if set(rel.parts) & FORBIDDEN_PARTS or rel.name in FORBIDDEN_NAMES:
        raise ValueError('Excluded source path: ' + relative)
    if any(part.startswith('.') for part in rel.parts) or any(x in rel.name.lower() for x in ('secret', 'credential', '.pem', '.key')):
        raise ValueError('Sensitive source filename: ' + relative)
    # Report-date paths must be July. Cache hashes and bounded lookback records
    # are left intact; this check concerns filenames, not their observations.
    if any(month != '2024-07' for month in re.findall(r'20\d{2}-\d{2}(?=-\d{2}(?:\D|$))', relative)):
        raise ValueError('Other report-month path: ' + relative)
    allowed = any(relative.startswith(folder + '/') for folder in REPLAY_ROOTS)
    allowed |= relative in {'newest_lambda_function.py', 'code_provenance.json', 'checks/code_discovery.json'}
    allowed |= relative.startswith('audit/') and len(rel.parts) == 2 and rel.suffix in {'.json', '.jsonl', '.csv'}
    if not allowed or not relative.endswith(('.json', '.jsonl', '.json.gz', '.xml.gz', '.py', '.csv', '.log', '.txt')):
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
                     and p.name.endswith(('.json', '.jsonl', '.json.gz', '.xml.gz', '.py', '.csv', '.log', '.txt')))
    paths.update((ROOT / 'audit').glob('*.csv'))
    paths.update((ROOT / 'audit').glob('*.jsonl'))
    # Top-level acquisition and market records supplement the nested raw inputs.
    paths.update(p for p in (ROOT / 'audit').glob('*.json')
                 if p.name not in FORBIDDEN_NAMES and not p.name.startswith('independent_nonretail_')
                 and not p.name.startswith('independent_retail_'))
    for name in ('newest_lambda_function.py', 'code_provenance.json', 'checks/code_discovery.json'):
        paths.add(ROOT / name)
    return {safe_path(path.relative_to(ROOT).as_posix()) for path in paths}


def main():
    source_path = ROOT / 'audit/independent_source_review.json'
    market_path = ROOT / 'audit/independent_market_review.json'
    source = json.loads(source_path.read_text())
    market = json.loads(market_path.read_text())
    if (source.get('passed') is not True or market.get('passed') is not True
            or [row.get('date') for row in source.get('dates', [])] != DATES
            or market.get('dates') != DATES or source.get('errors') or market.get('errors')):
        raise ValueError('Accepted complete July source and market inputs required')
    paths = collect_paths()
    rows = []
    for candidate in sorted(paths):
        path = safe_path(candidate.relative_to(ROOT).as_posix())
        rows.append({'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(path), 'bytes': path.stat().st_size})
    if not rows or len({r['path'] for r in rows}) != len(rows):
        raise ValueError('Empty or duplicate packaging inputs')
    result = {
        'status': 'frozen_inputs_hash_bound', 'report_month': '2024-07', 'dates': DATES,
        'files': rows, 'file_count': len(rows),
        'source_acceptance_sha256': sha(source_path), 'market_acceptance_sha256': sha(market_path),
        'scope': 'Exact July raw RSS, parsed request caches, per-headline provenance, acquisition and staged-feed comparison proof, retained Yahoo raw payloads/action audit/Treasury inputs, independent replay code/results, actual exclusions/revisions if present, and newest-code discovery. The artifact builder separately includes final feeds, cards, specifications, component drafts, selection notes, reviews and tools. Author scratch, repository clones, secrets and earlier retrospective inputs are excluded.'}
    write(ROOT / 'audit/news_replay_inventory.json', result)
    print(json.dumps({'files': len(rows), 'bytes': sum(r['bytes'] for r in rows),
                      'inventory_sha256': sha(ROOT / 'audit/news_replay_inventory.json')}))


if __name__ == '__main__':
    main()
