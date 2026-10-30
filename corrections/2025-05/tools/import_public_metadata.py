"""Verify a captured public-URL-only CI payload before importing its mappings.

Run from this month directory. The default is verification only; --import-cache
writes the canonical cache and a hash-bound ingestion receipt. The separate
GitHub connector records the exact commit/run/job association in run_binding.json.
No network requests, publisher bodies, credentials or report edits are involved.
"""
from pathlib import Path
import argparse
import base64
import datetime as dt
import gzip
import hashlib
import json
import re
import urllib.parse

ROOT = Path(__file__).resolve().parent.parent
FILES = {
    '.github/workflows/may2025-metadata-recovery.yml',
    'corrections/2025-05/recovery/input.json',
    'corrections/2025-05/recovery/resolve_news_url.py',
    'corrections/2025-05/recovery/run.py',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def verify(batch):
    manifest = json.loads((batch/'code_manifest.json').read_text())
    remote = json.loads((batch/'remote_files.json').read_text())
    binding = json.loads((batch/'run_binding.json').read_text())
    checked = json.loads((batch/'remote_code_verification.json').read_text())
    assert set(manifest) == FILES == {r['path'] for r in remote}
    assert binding['commit_sha'] == checked['head']
    assert binding['job_run_id'] == binding['run_id'] and binding['conclusion'] == 'success'
    for row in remote:
        raw = row['content'].encode() if row['encoding'] in ('utf-8', 'utf8') else base64.b64decode(row['content'], validate=True)
        assert sha(raw) == manifest[row['path']]['sha256']
        assert raw == (batch/'source'/row['path']).read_bytes()
    log_raw = (batch/'job.log').read_bytes()
    log = log_raw.decode('utf-8-sig')
    parts = re.findall(r'MAY2025_PAYLOAD_B64:([A-Za-z0-9+/=]+)', log)
    expected = re.findall(r'MAY2025_PAYLOAD_SHA256:([0-9a-f]{64})', log)
    assert parts and len(expected) == 1 and 'MAY2025_PAYLOAD_END' in log
    payload = base64.b64decode(''.join(parts), validate=True)
    assert sha(payload) == expected[0], 'Payload SHA mismatch'
    bundle = json.loads(gzip.decompress(payload))
    raw = bundle['canonical_metadata_json'].encode()
    receipt = json.loads(bundle['receipt_json'])
    records = json.loads(raw)
    input_path = 'corrections/2025-05/recovery/input.json'
    requested = set(json.loads((batch/'source'/input_path).read_text())['urls'])
    assert all(urllib.parse.urlsplit(u).scheme == 'https'
               and urllib.parse.urlsplit(u).hostname == 'news.google.com'
               and urllib.parse.urlsplit(u).path.startswith(('/rss/articles/', '/articles/'))
               for u in requested)
    assert receipt['input_sha256'] == manifest[input_path]['sha256']
    assert receipt['resolver_sha256'] == manifest['corrections/2025-05/recovery/resolve_news_url.py']['sha256']
    assert receipt['output_sha256'] == sha(raw)
    assert set(records) == requested and len(records) == receipt['records']
    assert receipt['failures'] == 0 and not any(r.get('error') for r in records.values())
    for row in records.values():
        u = urllib.parse.urlsplit(row['canonical_url'])
        assert u.scheme in ('http', 'https') and u.hostname
        assert u.hostname not in {'news.google.com', 'google.com', 'www.google.com', 'consent.google.com', 'accounts.google.com'}
        assert '/sorry/' not in u.path and row.get('publisher_body_fetched') is False
    proof = {'purpose': 'Hash-verified public Google News canonical metadata; no publisher bodies or report prose.',
             'workflow_run_id': binding['run_id'], 'workflow_job_id': binding['job_id'],
             'commit_sha': binding['commit_sha'], 'temporary_pr': 5,
             'input_sha256': receipt['input_sha256'], 'resolver_sha256': receipt['resolver_sha256'],
             'runner_sha256': manifest['corrections/2025-05/recovery/run.py']['sha256'],
             'workflow_sha256': manifest['.github/workflows/may2025-metadata-recovery.yml']['sha256'],
             'output_sha256': receipt['output_sha256'], 'payload_sha256': sha(payload),
             'job_log_sha256': sha(log_raw), 'records': len(records), 'failures': 0,
             'all_hash_checks_passed': True, 'requested_url_set_exact': True,
             'exact_head_four_files_verified': True, 'run_completion': binding,
             'original_body_vintage_proven': False, 'frozen_feeds_changed': False, 'specs_changed': False,
             'files': str(batch.relative_to(ROOT))}
    return records, proof, bundle, payload


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('batch_directory')
    ap.add_argument('--import-cache', action='store_true')
    args = ap.parse_args()
    batch = (ROOT/args.batch_directory).resolve()
    assert batch.is_relative_to(ROOT/'work'), 'Expected a captured batch under work/'
    records, proof, bundle, payload = verify(batch)
    if args.import_cache:
        cache_path = ROOT/'audit/canonical_all_cited_urls.json'
        before = cache_path.read_bytes() if cache_path.exists() else b'{}'
        cache = json.loads(before)
        for url, row in records.items():
            prior = cache.get(url, {}).get('canonical_url')
            assert not prior or prior == row['canonical_url'], 'Existing canonical mapping conflicts'
        cache.update(records)
        raw = (json.dumps(cache, ensure_ascii=False, indent=2)+'\n').encode()
        tmp = cache_path.with_suffix('.tmp')
        tmp.write_bytes(raw)
        tmp.replace(cache_path)
        proof.update(ingested_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                     cache_before_sha256=sha(before), cache_after_sha256=sha(raw),
                     existing_mapping_conflicts=0, invalid_canonical_results=0)
        (batch/'canonical_metadata.json').write_text(bundle['canonical_metadata_json'])
        (batch/'receipt.json').write_text(bundle['receipt_json'])
        (batch/'payload.gz').write_bytes(payload)
        name = batch.name.removeprefix('recovery_')
        (ROOT/'audit'/f'metadata_ci_ingestion_{name}.json').write_text(json.dumps(proof, indent=2)+'\n')
    print(json.dumps({'verified': True, 'records': len(records), 'cache_imported': args.import_cache}))


if __name__ == '__main__':
    main()
