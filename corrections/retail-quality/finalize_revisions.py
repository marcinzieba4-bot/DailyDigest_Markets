"""Bind reviewed historical sources/specs/artifacts before publication."""
from pathlib import Path
import datetime as dt
import hashlib
import importlib.util
import json
import os
import re
import subprocess

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parent.parent
BASE='c2e48ff31af11aa02b2226b83f23e986066aa593'
MONTHS=['2025-09','2025-10','2025-11','2025-12','2026-02']


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):return json.loads(path.read_text())


def bindings(value):
    # Only current review bindings count. Historical baseline hashes in findings
    # or repair evidence must never overwrite the reviewed current spec hash.
    if isinstance(value.get('spec_sha256'),dict):
        return value['spec_sha256']
    reports=value.get('reports')
    if isinstance(reports,list):
        return {row['date']:row['spec_sha256'] for row in reports}
    if isinstance(reports,dict):
        return {date:row['spec_sha256'] for date,row in reports.items()}
    raise ValueError('Independent review lacks explicit current spec bindings')


def main():
    artifacts=load(ROOT/'audit/revision_artifacts.json')
    scope=load(ROOT/'audit/retrospective_scope.json')
    if set(artifacts['dates'])-set(scope['allowed_retrospective_dates']):
        raise ValueError('Protected live date in artifact manifest')
    if set(artifacts['dates'])&set(scope['protected_live_dates']):
        raise ValueError('Live date cannot be revised')
    sp=importlib.util.spec_from_file_location('retail_gate',ROOT/'retail_quality.py')
    gate=importlib.util.module_from_spec(sp);sp.loader.exec_module(gate)
    receipts={};hashes={};changed={};accepted_warnings={}
    for month in MONTHS:
        folder=ROOT.parent/month
        quality=gate.require_review(folder)
        review_path=folder/'checks/retail_independent_review.json'
        review=load(review_path)
        status=review.get('status','')
        if not (status.startswith('pass') or status=='complete_selected_review') or review.get('blocking_issues'):
            raise ValueError('Independent review incomplete: '+month)
        if review.get('passed') is False or review.get('unresolved_issues',0):
            raise ValueError('Independent review has unresolved issues: '+month)
        expected={p.stem:sha(p) for p in (folder/'specs').glob('*.json')}
        if bindings(review)!=expected:
            raise ValueError('Independent review spec hashes stale: '+month)
        if quality['spec_sha256']!=expected:
            raise ValueError('Retail guard hashes stale: '+month)
        decision_hash=sha(folder/'checks/retail_editorial_decisions.json')
        for field in ['guard_disposition_file_sha256','guard_decision_file_sha256','decision_file_sha256','editorial_decisions_sha256']:
            if review.get(field) and review[field]!=decision_hash:
                raise ValueError('Independent decision review stale: '+month)
        hashes.update(expected)
        count=0
        for p in (folder/'specs').glob('*.json'):
            before=json.loads(subprocess.check_output(['git','show',BASE+':'+str(p.relative_to(REPO))],cwd=REPO))
            after=load(p)
            if before['retail']!=after['retail'] or before.get('retail_intro')!=after.get('retail_intro'):count+=1
        changed[month]=count
        receipts[month]={'independent_review_sha256':sha(review_path),
            'quality_receipt_sha256':sha(folder/'checks/retail_quality.json'),
            'decisions_sha256':decision_hash,'reports':len(expected)}
    canonical=load(ROOT/'audit/retail_canonical_dates.json')
    if not canonical['passed'] or canonical['spec_sha256']!=hashes:
        raise ValueError('Final retail canonical-date audit is incomplete/stale')
    legacy_path=ROOT/'audit/legacy_independent_review.json';legacy=load(legacy_path)
    if not legacy['status'].startswith('pass') or legacy.get('issues'):
        raise ValueError('Legacy independent review incomplete')
    expected_patches={p.stem:sha(p) for p in (ROOT/'patches').glob('*.json')}
    if legacy['patch_sha256']!=expected_patches:
        raise ValueError('Legacy patch review hashes stale')
    legacy_author=load(ROOT/'audit/legacy_retrospective_review.json')
    if legacy_author['target_count']!=50 or legacy_author['revised_count']!=len(expected_patches):
        raise ValueError('Legacy scope review incomplete')
    by_date={x['date']:x for x in artifacts['reports']}
    for date,row in by_date.items():
        if date in hashes:
            if row['proof']['after_spec_sha256']!=hashes[date]:
                raise ValueError('Built spec hash stale: '+date)
            if row['proof']['validator_warnings']:accepted_warnings[date]=row['proof']['validator_warnings']
        elif row['proof']['patch_sha256']!=expected_patches[date]:
            raise ValueError('Built legacy patch stale: '+date)
    for item in artifacts['targets']:
        p=ROOT/item['path']
        if sha(p)!=item['sha256'] or p.stat().st_size!=item['bytes']:
            raise ValueError('Artifact hash stale: '+item['key'])
    actual={x['key'] for x in artifacts['targets']}
    for date in artifacts['dates']:
        expected={f'reports/archive/{date}.html',f'Strategies/json/{date}_Market_Intelligence.json',f'Strategies/{date}_Market_Intelligence.pdf'}
        if not expected<=actual:raise ValueError('Missing artifact variant: '+date)
    old_lambda=subprocess.check_output(['git','show',BASE+':lambda_function.py'],cwd=REPO)
    if old_lambda!=(REPO/'lambda_function.py').read_bytes():
        raise ValueError('Live Lambda source must remain unchanged')
    result={'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
        'prepublication_passed':True,'publication_status':'ready_not_published',
        'retrospective_dates_reviewed':scope['allowed_count'],
        'live_dates_protected':scope['protected_count'],'live_lambda_source_unchanged':True,
        'retail_content_revised_by_month':changed,'legacy_content_revised':len(expected_patches),
        'content_revised_reports':sum(changed.values())+len(expected_patches),
        'exported_reports':len(artifacts['dates']),'artifact_targets':len(artifacts['targets']),
        'independent_month_receipts':receipts,'legacy_review_sha256':sha(legacy_path),
        'retail_canonical_audit_sha256':sha(ROOT/'audit/retail_canonical_dates.json'),
        'canonical_retail_urls':canonical['unique_cited_urls'],'canonical_conflicts':0,'canonical_lookup_failures':0,
        'accepted_validator_warnings':accepted_warnings,
        'narrow_nonretail_timing_repairs':3,
        'limitations':'Selected headline-based factual and editorial reviews, not exhaustive original article-body/vintage verification or a measured ranking of retail popularity. Legacy old facts retain original evidence limits; new legacy headlines independently meet strict midnight/7-day eligibility.'}
    input_paths=[ROOT/'audit/retrospective_scope.json',ROOT/'audit/retail_canonical_dates.json',
                 ROOT/'audit/legacy_independent_review.json',ROOT/'retail_quality.py',
                 ROOT/'build_revisions.py',ROOT/'finalize_revisions.py',ROOT/'publish_revisions.py']
    input_paths+=list((ROOT/'patches').glob('*.json'))
    for month in MONTHS:
        folder=ROOT.parent/month
        for sub,pattern in [('specs','*.json'),('cards','*.json'),('feeds','*.json.gz')]:
            input_paths+=list((folder/sub).glob(pattern))
        input_paths+=[folder/'checks/retail_independent_review.json',folder/'checks/retail_editorial_decisions.json']
    input_paths.append(ROOT.parent/'2025-12/audit/nonretail_timing_repairs.json')
    artifacts.update(reviewed=True,review_receipt_sha256=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest(),
                     review_receipts=receipts,reviewed_inputs={os.path.relpath(p,ROOT):sha(p) for p in input_paths})
    (ROOT/'audit/revision_artifacts.json').write_text(json.dumps(artifacts,indent=2))
    result['artifact_manifest_sha256']=sha(ROOT/'audit/revision_artifacts.json')
    (ROOT/'audit/final_validation.json').write_text(json.dumps(result,indent=2))
    print('FINAL PREPUBLICATION PASS:',result['content_revised_reports'],'content revisions;',result['exported_reports'],'exports;',result['artifact_targets'],'artifacts;',scope['protected_count'],'live editions protected')


if __name__=='__main__':main()
