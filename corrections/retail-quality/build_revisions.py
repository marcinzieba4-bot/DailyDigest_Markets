"""Build retail-only archive revisions without remote writes.

Canonical report specs may change only retail/retail_intro. Legacy patches are
applied to exact reviewed origin snapshots; all bytes outside retail survive.
"""
from pathlib import Path
import argparse
import copy
import datetime as dt
import hashlib
import gzip
import importlib.util
import json
import os
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
BASE = 'c2e48ff31af11aa02b2226b83f23e986066aa593'
MONTHS = ['2025-09', '2025-10', '2025-11', '2025-12', '2026-02']
TIMING_PATHS = {
    '2025-12-11': ('n5045', ['sectors',8,'parts',1,1]),
    '2025-12-19': ('n3727', ['sectors',8,'parts',0,1]),
    '2025-12-30': ('n2738', ['anticipatory',2,'parts',1,1]),
}


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def load(path):
    return json.loads(path.read_text())


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def bounds(page):
    match = re.search(r'<h2\b[^>]*>[^<]*What Retail Is Playing\s*</h2>', page, re.I)
    if not match:
        raise ValueError('Retail heading not found')
    end = re.search(r'<hr\b', page[match.end():], re.I)
    if not end:
        end = re.search(r'</body\s*>', page[match.end():], re.I)
    if not end:
        raise ValueError('Retail/footer boundary not found')
    return match.start(), match.end()+end.start()


def replace_sequence(values, before, after):
    if not before:
        raise ValueError('Empty original retail JSON sequence')
    matches = [i for i in range(len(values)-len(before)+1) if values[i:i+len(before)] == before]
    if len(matches) != 1:
        raise ValueError('Retail JSON sequence not uniquely found')
    i = matches[0]
    return values[:i]+after+values[i+len(before):]


def patch_json(original, old_fragment, new_fragment, parser):
    result = copy.deepcopy(original)
    before, after = parser.sections(old_fragment), parser.sections(new_fragment)
    if len(before) != 1 or len(after) != 1 or len(result['sections']) != 1:
        raise ValueError('Unexpected legacy JSON section shape')
    for field in ['subheadings', 'body']:
        result['sections'][0][field] = replace_sequence(result['sections'][0][field], before[0][field], after[0][field])
    result['retail_revised_at_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
    result['retail_revision_scope'] = 'Editorial selection and carryover treatment; original report cutoff preserved.'
    return result


def validate_spec_scope(before, after, date, repairs):
    expected=copy.deepcopy(before)
    approved=[]
    for row in repairs:
        if row['date']!=date:
            continue
        allowed=TIMING_PATHS.get(date)
        if not allowed or row['path']!=allowed[1] or row['removed_source_ids']!=[allowed[0]]:
            raise ValueError('Unapproved non-retail repair path/source: '+date)
        old=expected;new=after
        for key in row['path'][:-1]:
            old=old[key];new=new[key]
        key=row['path'][-1]
        if old[key]!=row['before'] or new[key]!=row['after'] or allowed[0] in row['after']:
            raise ValueError('Timing repair does not match exact reviewed values: '+date)
        old[key]=row['after'];approved.append(row)
    for field in set(expected)|set(after):
        if field not in ['retail','retail_intro'] and (field not in expected or field not in after or expected[field]!=after[field]):
            raise ValueError('Non-retail spec changed outside exact timing repairs: '+date+' '+field)
    return approved


def changed_specs():
    found = {}
    repair_path=REPO/'corrections/2025-12/audit/nonretail_timing_repairs.json'
    repairs=load(repair_path)['repairs'] if repair_path.exists() else []
    for month in MONTHS:
        folder = REPO/'corrections'/month
        for p in sorted((folder/'specs').glob('*.json')):
            relative = p.relative_to(REPO)
            raw = subprocess.check_output(['git', 'show', BASE+':'+str(relative)], cwd=REPO)
            before, after = json.loads(raw), load(p)
            if before == after and month not in ['2025-09','2025-10','2025-11']:
                continue
            approved=validate_spec_scope(before,after,p.stem,repairs)
            found[p.stem] = (folder, sha(raw), sha(p.read_bytes()),approved)
    return found


def target(path, key, originals):
    blob = path.read_bytes()
    return {'path': os.path.relpath(path, ROOT), 'key': key, 'sha256': sha(blob),
            'bytes': len(blob), 'content_type': ('text/html; charset=utf-8' if key.endswith('.html') else
                'application/json' if key.endswith('.json') else 'application/pdf' if key.endswith('.pdf') else
                'application/zip' if key.endswith('.zip') else 'text/plain; charset=utf-8'),
            'expected_original_sha256': originals[key]['sha256']}


def build(dates=None):
    from playwright.sync_api import sync_playwright
    from pypdf import PdfReader
    specs = changed_specs()
    patches = {p.stem: p for p in (ROOT/'patches').glob('*.json')}
    selected = sorted(set(specs)|set(patches))
    allowed = set(load(ROOT/'audit/retrospective_scope.json')['allowed_retrospective_dates'])
    protected = set(selected)-allowed
    if protected:
        raise ValueError('Live editions are protected: '+repr(sorted(protected)))
    if dates:
        selected = [d for d in selected if d in dates]
    originals = {x['key']: x for x in load(ROOT/'audit/published_snapshots.json')}
    originals.update({x['key']: x for x in load(ROOT/'audit/published_pdf_snapshots.json') if 'sha256' in x})
    parser = module(REPO/'corrections/2025-09/tools/render.py', 'paragraph_parser')
    for name in ['html', 'json', 'pdf', 'audit/builds']:
        (ROOT/name).mkdir(parents=True, exist_ok=True)
    rows, targets = [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path='/usr/bin/chromium', args=['--no-sandbox'])
        page = browser.new_page(viewport={'width':1440, 'height':1000})
        for date in selected:
            original_html = (ROOT/'work/published/html'/f'{date}.html').read_text()
            a, b = bounds(original_html)
            hp, jp, pp = ROOT/'html'/f'{date}.html', ROOT/'json'/f'{date}.json', ROOT/'pdf'/f'{date}.pdf'
            if date in specs:
                folder, before_sha, after_sha, timing_repairs = specs[date]
                verifier = module(folder/'tools/verify.py', 'verify_'+date.replace('-', '_'))
                failures, warnings, source_count, words = verifier.verify(date)
                if failures:
                    raise ValueError(date+' '+repr(failures))
                checked = None
                manifest_path = folder/'checks/artifact_manifest.json'
                if date[:7] in ['2025-09','2025-10','2025-11'] and manifest_path.exists():
                    candidate = next((x for x in load(manifest_path)['reports'] if x['date']==date),None)
                    if candidate and candidate['spec_sha256']==after_sha and all(
                        (folder/f['path']).exists() and sha((folder/f['path']).read_bytes())==f['sha256']
                        for f in candidate['files'].values()):
                        checked = candidate
                if checked:
                    new_html = (folder/checked['files']['html']['path']).read_text()
                else:
                    if date[:7] in ['2025-09','2025-10','2025-11']:
                        raise ValueError('Rebuild checked month artifacts before retail export: '+date)
                    renderer = module(folder/'tools/render.py', 'render_'+date.replace('-', '_'))
                    new_html = renderer.render(date)
                na, _ = bounds(new_html)
                if not timing_repairs and re.sub(r'\s+', ' ', original_html[:a]) != re.sub(r'\s+', ' ', new_html[:na]):
                    raise ValueError('Non-retail HTML prefix differs: '+date)
                # Keep even the original non-retail whitespace byte-for-byte.
                if not timing_repairs:
                    new_html = original_html[:a]+new_html[na:]
                payload = load(folder/'json'/f'{date}_Market_Intelligence.json')
                if date[:7] not in ['2025-09','2025-10','2025-11']:
                    current_spec=load(folder/'specs'/f'{date}.json')
                    ids=set(re.findall(r'\[\[(n\d+)\]\]',json.dumps(current_spec['retail'])))
                    ids.update(source for repair in timing_repairs for source in repair['added_source_ids'])
                    with gzip.open(folder/'feeds'/f'{date}.json.gz','rt') as stream:
                        feed=json.load(stream)
                    payload['retail_revision_evidence']={e['id']:e for e in feed['items'] if e['id'] in ids}
                proof = {'kind':'canonical', 'before_spec_sha256':before_sha, 'after_spec_sha256':after_sha,
                         'retail_spec_changed':before_sha!=after_sha,
                         'nonretail_spec_unchanged':not timing_repairs,
                         'approved_nonretail_timing_repairs':timing_repairs,
                         'words':words, 'distinct_sources':source_count,
                         'validator_warnings':warnings}
            else:
                patch = load(patches[date])
                if patch['before_html_sha256'] != sha(original_html.encode()):
                    raise ValueError('Legacy original hash mismatch: '+date)
                fragment = patch['retail_html']
                if not patch.get('provenance') or not patch.get('cutoff_preserved'):
                    raise ValueError('Missing legacy provenance/cutoff proof: '+date)
                new_html = original_html[:a]+fragment+'\n'+original_html[b:]
                original_json = load(ROOT/'work/published/json'/f'{date}.json')
                payload = patch_json(original_json, original_html[a:b], fragment, parser)
                payload['retail_revision_evidence'] = {
                    row['feed_item']['id']:row['feed_item'] for row in patch['provenance'] if row.get('feed_item')}
                payload['retail_new_headline_cutoff_utc'] = date+'T00:00:00Z'
                if payload.get('news_cutoff_utc') != original_json.get('news_cutoff_utc') or payload['generated_at'] != original_json['generated_at']:
                    raise ValueError('Original cutoff changed: '+date)
                proof = {'kind':'legacy', 'patch_sha256':sha(patches[date].read_bytes()),
                         'nonretail_html_prefix_suffix_unchanged':True,
                         'provenance_scope':'Own-report facts only; original article vintages not reverified.'}
            hp.write_text(new_html)
            if jp.exists() and 'retail_revised_at_utc' in payload:
                previous_payload = load(jp)
                left = {k:v for k,v in previous_payload.items() if k!='retail_revised_at_utc'}
                right = {k:v for k,v in payload.items() if k!='retail_revised_at_utc'}
                if left == right and 'retail_revised_at_utc' in previous_payload:
                    payload['retail_revised_at_utc'] = previous_payload['retail_revised_at_utc']
            jp.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
            inputs = {'html_sha256':sha(hp.read_bytes()), 'json_sha256':sha(jp.read_bytes())}
            receipt = ROOT/'audit/builds'/f'{date}.json'
            prior = load(receipt) if receipt.exists() else {}
            month_pdf = None
            month_manifest_path = REPO/'corrections'/date[:7]/'checks/artifact_manifest.json'
            if date in specs and month_manifest_path.exists():
                month_row = next((r for r in load(month_manifest_path)['reports'] if r['date']==date),None)
                if month_row and month_row['spec_sha256']==specs[date][2] and month_row['files']['html']['sha256']==inputs['html_sha256']:
                    candidate = REPO/'corrections'/date[:7]/month_row['files']['pdf']['path']
                    if candidate.exists() and sha(candidate.read_bytes())==month_row['files']['pdf']['sha256']:
                        month_pdf = (candidate,month_row)
            if prior.get('html_sha256')==inputs['html_sha256'] and pp.exists() and prior.get('pdf_sha256')==sha(pp.read_bytes()) and (not month_pdf or prior['pdf_sha256']==month_pdf[1]['files']['pdf']['sha256']):
                proof.update(prior['browser_checks'])
            elif month_pdf:
                pp.write_bytes(month_pdf[0].read_bytes())
                proof.update(pdf_pages=month_pdf[1]['pdf_pages'],desktop_overflow=False,
                             mobile_overflow=month_pdf[1]['mobile_overflow'],
                             pdf_reused_from_checked_month_manifest_sha256=sha(month_manifest_path.read_bytes()))
            else:
                page.set_viewport_size({'width':1440,'height':1000})
                page.set_content(new_html, wait_until='load')
                if page.evaluate('document.documentElement.scrollWidth>innerWidth'):
                    raise ValueError('Desktop overflow: '+date)
                page.pdf(path=str(pp), format='A4', print_background=True,
                         margin={'top':'14mm','bottom':'16mm','left':'14mm','right':'14mm'})
                text=' '.join(p.extract_text() or '' for p in PdfReader(pp).pages)
                if 'What Retail Is Playing' not in text:
                    raise ValueError('PDF missing retail section: '+date)
                page.set_viewport_size({'width':390,'height':844})
                # Legacy pages have fixed old layouts. Verify the changed retail
                # fragment fits its existing container; do not redesign the report.
                overflow = page.evaluate('document.documentElement.scrollWidth>innerWidth')
                proof.update(pdf_pages=len(PdfReader(pp).pages), desktop_overflow=False,
                             mobile_overflow=overflow)
                if date[:7] in ['2025-09','2025-10','2025-11'] and overflow:
                    raise ValueError('Responsive report overflow: '+date)
            browser_checks={k:proof[k] for k in ['pdf_pages','desktop_overflow','mobile_overflow']}
            row={'date':date, 'original_html_sha256':sha(original_html.encode()),
                 'nonretail_prefix_sha256':sha(original_html[:a].encode()), **inputs,
                 'pdf_sha256':sha(pp.read_bytes()), 'proof':proof, 'browser_checks':browser_checks}
            receipt.write_text(json.dumps(row,indent=2))
            rows.append(row)
            for path,key in [(hp,f'reports/archive/{date}.html'),(jp,f'Strategies/json/{date}_Market_Intelligence.json'),
                             (pp,f'Strategies/{date}_Market_Intelligence.pdf')]:
                targets.append(target(path,key,originals))
            print(date, proof['kind'], proof['pdf_pages'], 'pages; retail-only scope checked',flush=True)
        browser.close()
    if not dates:
        originals.update(load(ROOT/'audit/original_collection_hashes.json'))
        by_key={x['key']:x for x in targets}
        for month in ['2025-09','2025-10','2025-11']:
            folder=REPO/'corrections'/month
            manifest=load(folder/'checks/artifact_manifest.json')
            if not manifest['complete_month']:
                raise ValueError('Incomplete month collection: '+month)
            archive=next(v for k,v in manifest['collection'].items() if k.endswith('.zip'))
            with zipfile.ZipFile(folder/archive['path']) as bundle:
                for row in manifest['reports']:
                    for fmt,f in row['files'].items():
                        key={'html':f"reports/archive/{row['date']}.html",
                             'json':f"Strategies/json/{row['date']}_Market_Intelligence.json",
                             'pdf':f"Strategies/{row['date']}_Market_Intelligence.pdf"}[fmt]
                        if sha(bundle.read(f['path']))!=by_key[key]['sha256']:
                            raise ValueError('ZIP differs from revised origin artifact: '+key)
            for name,f in manifest['collection'].items():
                path=folder/f['path']
                if sha(path.read_bytes())!=f['sha256']:
                    raise ValueError('Collection changed after check: '+str(path))
                key='reports/'+name if name.endswith('.html') else f'reports/{month}/'+name
                targets.append(target(path,key,originals))
    result={'built_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(), 'dates':selected,
            'reviewed':False, 'reports':rows, 'targets':targets}
    (ROOT/'audit/revision_artifacts.json').write_text(json.dumps(result,indent=2))
    print('Built',len(rows),'revisions; editorial final gate remains required',flush=True)


if __name__=='__main__':
    args=argparse.ArgumentParser(description=__doc__)
    args.add_argument('dates',nargs='*')
    build(args.parse_args().dates)
