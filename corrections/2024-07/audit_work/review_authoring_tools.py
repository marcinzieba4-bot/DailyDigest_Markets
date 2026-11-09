"""Root review of validation gates using isolated synthetic inputs only."""
from pathlib import Path
import copy
import datetime as dt
import gzip
import hashlib
import json
import runpy

ROOT=Path(__file__).resolve().parent.parent
env=runpy.run_path(str(ROOT/'audit_work/test_authoring_toolkit.py'))
verify=env['verify']; merge=env['merge_retail']; fix=env['FIX']; date=env['d']
checks=[]


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    checks.append({'check':name,'passed':True})


def mutation(path, change, expected):
    raw=path.read_bytes()
    try:
        value=json.loads(gzip.decompress(raw) if path.suffix=='.gz' else raw)
        change(value)
        payload=json.dumps(value).encode()
        path.write_bytes(gzip.compress(payload,mtime=0) if path.suffix=='.gz' else payload)
        return any(expected in line for line in verify.verify(date,spec_override=env['spec'])[0])
    finally:
        path.write_bytes(raw)


check('wrong card identity rejected',mutation(fix/'cards'/f'{date}.json',
    lambda x:x.__setitem__('report_date','2024-07-02'),'market card identity'))
check('uncompleted market session rejected',mutation(fix/'cards'/f'{date}.json',
    lambda x:x['markets']['AAA'].__setitem__('session',date),'MARKET session violation'))
check('stale exclusions hash rejected',mutation(fix/'exclusions'/f'{date}.json',
    lambda x:x.__setitem__('feed_sha256','stale'),'Stale source exclusions'))
check('naive news timestamp rejected',mutation(fix/'feeds'/f'{date}.json.gz',
    lambda x:x['items'][0].__setitem__('published_at','2024-06-30T12:00:00'),'cutoff/window'))
check('duplicate source identity rejected',mutation(fix/'feeds'/f'{date}.json.gz',
    lambda x:x['items'][0].__setitem__('id','n0002'),'duplicate own-date source'))
value=copy.deepcopy(env['spec'])
value['geo'][2]['parts'][-1][1]=value['geo'][2]['parts'][-1][1].replace('⚠ Divergence:','divergence')
check('required China contrary signal label enforced',any('Playbook needs' in x for x in verify.verify(date,spec_override=value)[0]))
review_path=fix/'audit'/f'independent_nonretail_{date}.json'
raw=review_path.read_bytes();target=fix/'specs'/f'{date}.json';original=target.read_bytes()
try:
    review=json.loads(raw);review['fatal_or_major_remaining']=1
    review_path.write_text(json.dumps(review))
    try:
        merge.merge(date);rejected=False
    except ValueError:
        rejected=True
    check('unresolved independent review blocks every spec write',rejected and target.read_bytes()==original)
finally:
    review_path.write_bytes(raw)

names=['digest.py','showcard.py','cited_titles.py','verify.py','check_block_ranges.py',
       'merge_retail.py','stage_reviewed.py','finalize_reviews.py','retail_quality_snapshot.py']
result={'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'passed':True,
    'script_sha256':{name:hashlib.sha256((ROOT/'tools'/name).read_bytes()).hexdigest() for name in names},
    'inherited_regressions_replayed':len(env['results']),'independent_negative_checks':checks,
    'production_evidence_or_drafts_read':False,
    'scope':'Read source and independently executed synthetic positive/negative gates for exact23-date scope/schema/word ranges, own-date sources, citation and local numeric support, FX exclusions, current review bindings and validation before atomic staging.',
    'limitations':['Numeric token membership does not prove instrument identity, sign, session, horizon, unit or economic claim; every claim still requires independent own-date review.',
        'Automated timestamp/category checks do not establish actual release timing, preview/outcome meaning or original article vintage.',
        'Title/label factual meaning, cross-section consistency, chronology and substantive editorial depth remain independent review responsibilities.']}
(ROOT/'audit/independent_authoring_tool_review.json').write_text(json.dumps(result,indent=2))
print(json.dumps({'passed':True,'regressions':len(env['results']),'additional_negatives':len(checks)}))
