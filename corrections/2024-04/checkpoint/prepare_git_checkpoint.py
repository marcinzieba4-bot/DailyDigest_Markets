"""Prepare an exact April checkpoint after verified delivery; copy only with --go.

No commit, push, acquisition, publication or existing-checkpoint edit occurs.
Private research originals and raw/binary artifacts remain outside Git.
"""
from pathlib import Path, PurePosixPath
import argparse, datetime as dt, gzip, hashlib, json, os, re, shutil, subprocess, sys, tempfile, zipfile
ROOT = Path('/workspace/work/april2024')
REPO = Path('/workspace/DailyDigest_Markets')
DEST = Path('corrections/2024-04')
BASE = '5991208ed7f2d3a2763f261c0c3ba2b63b7d752f'
BRANCH = 'codex/apr-2024-retrospective-20261110'
DATES = [dt.date(2024, 4, n).isoformat() for n in range(1, 31) if dt.date(2024, 4, n).weekday() < 5]
PLAN = ROOT / 'work/git_checkpoint_plan.json'
sys.path.insert(0, str(ROOT / 'tools'))
import build_source_inventory as inventory

def sha(b):
    return hashlib.sha256(b).hexdigest()

def digest(p):
    return sha(p.read_bytes())

def encoded(x):
    return (json.dumps(x, ensure_ascii=False, indent=2) + '\n').encode()

def git(*args):
    p = subprocess.run(['git', *args], cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode:
        raise ValueError('Git check failed: ' + args[0])
    return p.stdout

def safe(name):
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name or (str(p) != name) or (p.name.lower() == 'claude.md'):
        raise ValueError('Unsafe checkpoint path')
    f = ROOT / name
    if not f.is_file() or f.is_symlink() or (not f.resolve().is_relative_to(ROOT)):
        raise ValueError('Missing/unsafe input ' + name)
    if any((x.is_symlink() for x in f.parents if x.is_relative_to(ROOT))):
        raise ValueError('Symlink input ' + name)
    return f

def repo_identity():
    if not Path(git('rev-parse', '--show-toplevel').decode().strip()).resolve() == REPO:
        raise ValueError('Checkpoint requirement failed at original line 34')
    if not git('branch', '--show-current').decode().strip() == BRANCH:
        raise ValueError('Checkpoint requirement failed at original line 35')
    if not git('rev-parse', 'HEAD').decode().strip() == BASE:
        raise ValueError('Checkpoint requirement failed at original line 36')
    if not not git('status', '--porcelain', '-z'):
        raise ValueError('Clean April branch required')
    if not not (REPO / DEST).exists():
        raise ValueError('Refusing existing checkpoint overwrite')

def scan(blobs):
    values = {k: v for k, v in os.environ.items() if v and re.search('password|passwd|secret|token|api.?key|access.?key|private.?key|aws_key', k, re.I)}
    if not {'AWS_KEY', 'AWS_SECRET'} <= set(values):
        raise ValueError('Configured AWS values must be compared in process')
    hits = []
    for name, body in blobs:
        batches = [body] + ([gzip.decompress(body)] if name.endswith('.gz') else [])
        for key, value in values.items():
            forms = {value.encode(), json.dumps(value, ensure_ascii=False)[1:-1].encode()}
            if any((form in b for form in forms for b in batches)):
                hits.append({'path': name, 'variable': key})
    if not not hits:
        raise ValueError('Configured credential matched checkpoint selection; no values recorded')
    return {'passed': True, 'variables_compared': sorted(values), 'values_recorded': False}

def runtime_versions():
    code = "import sys,json,importlib.metadata as m; names=['boto3','botocore','beautifulsoup4','playwright','pypdf','PyMuPDF','exchange-calendars','pandas','numpy']; versions={}; exec(\"for n in names:\\n try: versions[n]=m.version(n)\\n except m.PackageNotFoundError: versions[n]=None\"); print(json.dumps({'python':sys.version.split()[0],'packages':versions}))"
    records = {}
    for role, executable in [('artifacts', '/workspace/work/april-runtime/bin/python'), ('market_news_publication', '/workspace/.report-tools/bin/python')]:
        run = subprocess.run([executable, '-c', code], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        records[role] = {'executable_at_build': executable, **json.loads(run.stdout)}
    browser = subprocess.run(['/usr/bin/chromium', '--version'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return {'runtimes': records, 'chromium': browser.stdout.decode().strip(), 'scope': 'Observed installed runtime versions; dependencies are not bundled. Historical delivered artifact bytes are retained in the verified download ZIP.'}

def build():
    repo_identity()
    manifest = json.loads(safe('checks/artifact_manifest.json').read_bytes())
    publication = json.loads(safe('checks/publication.json').read_bytes())
    delivery = json.loads(safe('checks/delivery_verification.json').read_bytes())
    if not (manifest['dates'] == DATES and manifest['complete_month'] is True):
        raise ValueError('Checkpoint requirement failed at original line 55')
    if not (manifest['artifact_targets'] == 71 and manifest['report_zip_members'] == 69):
        raise ValueError('Checkpoint requirement failed at original line 56')
    if not (publication['manifest_sha256'] == digest(ROOT / 'checks/artifact_manifest.json') and publication['dates'] == DATES):
        raise ValueError('Checkpoint requirement failed at original line 57')
    if not (publication['stage'] == 'origin_verified' and len(publication['confirmed']) == 71 and (len(publication['targets']) == 71)):
        raise ValueError('Checkpoint requirement failed at original line 58')
    if not (publication['latest_write_performed'] is False and publication['lambda_write_performed'] is False):
        raise ValueError('Checkpoint requirement failed at original line 59')
    if not (delivery['artifact_manifest_sha256'] == digest(ROOT / 'checks/artifact_manifest.json') and delivery['publication_receipt_sha256'] == digest(ROOT / 'checks/publication.json')):
        raise ValueError('Delivery receipt does not bind current publication/manifest')
    if not (delivery['passed'] is True and len(delivery['objects']) == 71):
        raise ValueError('Checkpoint requirement failed at original line 61')
    if not all((x['origin_sha256_pass'] and x['public_sha256_pass'] for x in delivery['objects'])):
        raise ValueError('Checkpoint requirement failed at original line 62')
    if not (len(delivery['public_report_zip_members']) == 66 and all((x['sha256_pass'] for x in delivery['public_report_zip_members']))):
        raise ValueError('Checkpoint requirement failed at original line 63')
    if not (delivery['lambda_code_and_runtime_unchanged'] is True and delivery['invalidation_status'] == 'Completed'):
        raise ValueError('Checkpoint requirement failed at original line 64')
    public = inventory.public_research_export()
    source = manifest['frozen_source_archive']
    archive = source['archive']
    zp = safe(archive['path'])
    if not (digest(zp) == archive['sha256'] and zp.stat().st_size == archive['bytes']):
        raise ValueError('Checkpoint requirement failed at original line 67')
    with zipfile.ZipFile(zp) as z:
        raw = z.read('source_inventory.json')
        rows = json.loads(raw)
        names = z.namelist()
        if not (len(names) == len(set(names)) and set(names) == {x['path'] for x in rows} | {'source_inventory.json'}):
            raise ValueError('Checkpoint requirement failed at original line 70')
        if not (sha(json.dumps(rows, sort_keys=True).encode()) == source['inventory_sha256'] and len(rows) == source['files']):
            raise ValueError('Checkpoint requirement failed at original line 71')
        if not all((not PurePosixPath(n).is_absolute() and '..' not in PurePosixPath(n).parts and ('\\' not in n) for n in names)):
            raise ValueError('Checkpoint requirement failed at original line 72')
    ext = {x['path']: x for x in rows}
    paths = {'AUTHORING.md', 'BRIEF.md', 'code_provenance.json', 'source/lambda_function.py'}
    for d in DATES:
        for folder, suffix in [('cards', '.json'), ('feeds', '.json.gz'), ('specs', '.json'), ('nonretail_drafts', '.json'), ('retail_drafts', '.json'), ('exclusions', '.json'), ('html', '.html')]:
            paths.add(folder + '/' + d + suffix)
        paths.update(['json/' + d + '_Market_Intelligence.json', 'notes/retail_' + d + '.json', 'notes/' + d + '_nonretail.json'])
    paths.update(('collection/' + n for n in ['2024-04.html', 'methodology.txt', 'What_Retail_Is_Playing_2024-04.html']))
    # Canonical delivered retail collection is retained under collection/.
    omitted = []
    forbidden = {'__pycache__', 'cache', 'work', 'market_raw', 'pdf', 'node_modules', '.git'}
    for folder, extensions in [('tools', {'.py'}), ('data', {'.json'}), ('reference', {'.txt', '.json'}), ('audit', {'.json', '.jsonl', '.gz', '.csv'}), ('checks', {'.json'}), ('audit_work', {'.py', '.json', '.txt', '.csv'})]:
        for p in (ROOT / folder).rglob('*'):
            if not p.is_file() or p.suffix not in extensions or set(p.relative_to(ROOT).parts) & forbidden:
                continue
            rel = p.relative_to(ROOT).as_posix()
            if p.name.lower() == 'claude.md':
                continue
            if p.stat().st_size > 1000000 or p.suffix == '.jsonl':
                proof = ext.get(rel)
                if not (proof and proof['sha256'] == digest(p) and (proof['bytes'] == p.stat().st_size)):
                    raise ValueError(('Omitted proof must be exact source-ZIP member', rel))
                omitted.append(proof)
                continue
            if p.suffix == '.gz' and (not rel.startswith('audit/news_provenance/')):
                continue
            if p.suffix == '.csv' and rel != 'audit/treasury_retained.csv':
                continue
            paths.add(rel)
    copied = []
    blobs = []
    for name in sorted(paths):
        p = safe(name)
        body = p.read_bytes()
        decoded = gzip.decompress(body) if name.endswith('.gz') else body
        decoded.decode('utf-8')
        inventory.assert_no_raw_web_candidates(lambda _: decoded, [name])
        proof = ext.get(name)
        artifact = next((a for report in manifest['reports'] for a in report['files'].values() if a['path'] == name), None)
        if artifact is None:
            artifact = next((a for a in manifest['collection'].values() if a['path'] == name), None)
        if proof is not None:
            if not (proof['sha256'] == sha(body) and proof['bytes'] == len(body)):
                raise ValueError(('Source differs from delivered frozen-source ZIP', name))
        if artifact is not None:
            if not (artifact['sha256'] == sha(body) and artifact['bytes'] == len(body)):
                raise ValueError(('Artifact differs from delivered manifest', name))
        if name.split('/')[0] in {'cards', 'feeds', 'specs', 'nonretail_drafts', 'retail_drafts', 'exclusions', 'tools', 'data', 'source', 'notes', 'reference'} or name in {'AUTHORING.md', 'BRIEF.md', 'code_provenance.json'}:
            if not proof is not None:
                raise ValueError(('Core input missing delivered source binding', name))
        copied.append({'path': name, 'sha256': sha(body), 'bytes': len(body)})
        blobs.append((name, body))
    external = {'status': 'external_complete_frozen_source_archive', 'archive': archive, 'url': 'https://zembihf.xyz/reports/2024-04/April_2024_Frozen_Sources.zip', 'inventory_member_sha256': sha(raw), 'inventory_canonical_sha256': source['inventory_sha256'], 'inventory_files': len(rows), 'large_proof_files_omitted_from_Git': omitted, 'public_research_manifest_sha256': public['manifest_sha256'], 'private_response_count': public['private_response_count'], 'private_originals_public': False, 'restore': 'Verify ZIP and source_inventory digests before extracting omitted raw/replay families into an isolated April ROOT. Do not replace historical evidence with a new acquisition.'}
    generated = {'.gitignore': b'__pycache__/\ncache/\nwork/\npdf/\ncollection/*.zip\n*.tmp\n*.log\n', 'checkpoint/external_raw_sources.json': encoded(external), 'checkpoint/prepare_git_checkpoint.py': Path(__file__).read_bytes(), 'README.md': b'April 2024 retrospective checkpoint\n\n22 Monday-Friday editions, April 1-30, including exchange holidays. Final reports preserve the wide nine-section format and independently reviewed retail chronology.\n\nPublic archive: https://zembihf.xyz/reports/2024-04.html\nRetail collection: https://zembihf.xyz/reports/2024-04/What_Retail_Is_Playing_2024-04.html\nReports, including PDFs: https://zembihf.xyz/reports/2024-04/April_2024_Weekday_Reports.zip\n\nRead BRIEF.md and AUTHORING.md before replay. Exact original code, final specifications, feeds, cards, selection notes, independent reviews and HTML/JSON delivery are preserved here. Raw request/provider responses, large transport inventories and binary deliverables remain in the verified frozen-source ZIP; checkpoint/external_raw_sources.json binds it. Full clock-research responses stay private; public clock metadata and original hash commitments do not claim byte replay of private originals.\n\nRestore missing raw families under /workspace/work/april2024 with the recorded dependencies, and restore audit_work/shared_retail_quality_original.py under /workspace/work/retail-quality/retail_quality.py. No acquisition, publication, Lambda invocation, deployment, email or Telegram occurs merely by restoring this checkpoint.\n'}
    # Retain exact delivered bytes; scope whitespace-style exceptions to the
    # concrete immutable files that require them, with hashes and counts.
    whitespace_rows = []
    attribute_lines = ['# Exact delivered/source bytes; see checkpoint/whitespace_preservation.json.']
    for name, body in blobs:
        if name.endswith('.gz'):
            continue
        trailing = sum(bool(re.search(rb'[ \t]+$', line)) for line in body.splitlines())
        final_blank = body.endswith(b'\n\n')
        flags = (['-blank-at-eol'] if trailing else []) + (['-blank-at-eof'] if final_blank else [])
        if flags:
            attribute_lines.append(json.dumps(name) + ' whitespace=' + ','.join(flags))
            whitespace_rows.append({'path': name, 'sha256': sha(body), 'trailing_whitespace_lines': trailing, 'multiple_final_newlines': final_blank, 'attribute': ','.join(flags)})
    generated['.gitattributes'] = ('\n'.join(attribute_lines) + '\n').encode()
    generated['checkpoint/whitespace_preservation.json'] = encoded({'scope': 'Observed whitespace in exact delivered/source bytes is retained. Only these exact paths receive the listed style exceptions; byte equality against the delivered source ZIP/artifact manifest remains mandatory.', 'files': whitespace_rows})
    generated['checkpoint/runtime_versions.json'] = encoded(runtime_versions())
    generated['checkpoint/copied_source_inventory.json'] = encoded({'source_root': str(ROOT), 'files': copied, 'generated_files': [{'path': n, 'sha256': sha(b), 'bytes': len(b)} for n, b in sorted(generated.items())]})
    checked = scan(blobs + list(generated.items()))
    plan = {'status': 'ready_after_verified_delivery', 'branch': BRANCH, 'base': BASE, 'destination': str(DEST), 'files': copied, 'generated': [{'path': n, 'sha256': sha(b), 'bytes': len(b)} for n, b in sorted(generated.items())], 'credential_scan': checked, 'delivery_bindings': {n: digest(ROOT / 'checks' / n) for n in ['artifact_manifest.json', 'publication.json', 'delivery_verification.json']}, 'script_sha256': digest(Path(__file__))}
    return (plan, generated)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--go', action='store_true')
    p.add_argument('--plan-sha256')
    a = p.parse_args()
    plan, generated = build()
    if not a.go:
        PLAN.write_bytes(encoded(plan))
        print(json.dumps({'ready': True, 'plan_sha256': digest(PLAN), 'files': len(plan['files']) + len(generated), 'credential_scan': plan['credential_scan']}))
        return
    if not (a.plan_sha256 and digest(PLAN) == a.plan_sha256 and (json.loads(PLAN.read_bytes()) == plan)):
        raise ValueError('Exact current reviewed plan required')
    staging = Path(tempfile.mkdtemp(prefix='april-git-checkpoint-', dir=ROOT / 'work'))
    try:
        for row in plan['files']:
            p = staging / row['path']
            p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(safe(row['path']), p)
            if not digest(p) == row['sha256']:
                raise ValueError('Checkpoint requirement failed at original line 122')
        for name, body in generated.items():
            p = staging / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(body)
        scan([(p.relative_to(staging).as_posix(), p.read_bytes()) for p in staging.rglob('*') if p.is_file()])
        repo_identity()
        staging.rename(REPO / DEST)
        git('add', '--', str(DEST))
        staged = [x.decode() for x in git('diff', '--cached', '--name-only', '-z').split(b'\x00') if x]
        if not (len(staged) == len(plan['files']) + len(generated) and all((x.startswith(str(DEST) + '/') for x in staged))):
            raise ValueError('Checkpoint requirement failed at original line 127')
        git('-c', 'core.whitespace=cr-at-eol', 'diff', '--cached', '--check', '--', str(DEST))
        (ROOT / 'work/git_checkpoint_copy_receipt.json').write_bytes(encoded({'status': 'copied_and_staged', 'plan_sha256': a.plan_sha256, 'files': len(staged), 'branch': BRANCH, 'base': BASE, 'existing_checkpoint_changes': False, 'commit_performed': False, 'push_performed': False}))
        print('Copied and staged', len(staged), 'April checkpoint files; no commit or push')
    finally:
        if staging.exists():
            shutil.rmtree(staging)
if __name__ == '__main__':
    main()
