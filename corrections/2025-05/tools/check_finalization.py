"""Run only after real publication, live verification and a successful finalizer.

In-memory corruption cases must be rejected; real delivery/input receipts remain
byte-identical. This script does not fabricate review or publication receipts.
"""
from pathlib import Path
import copy, importlib.util, json, sys, datetime, hashlib
from unittest.mock import patch

root=Path.cwd()
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
m=module('may_finalizer',root/'tools/finalize.py')
original=m.read
receipts={name:original(name) for name in [
    'checks/publication.json','checks/live_verification.json',
    'checks/source_archive_publication.json']}
protected=[root/name for name in receipts]+[
    root/'checks/final_validation.json',root/'checks/retail_quality.json',
    root/'audit/cited_source_dates.json',root/'audit/canonical_source_exceptions.json',
    root/'checks/independent_selected_review.json',root/'checks/source_attribution_diagnostic.json']
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
before={str(path):sha(path) for path in protected}
passed=[]
for name in ['stale_origin_target','stale_origin_confirmation','stale_public_delivery','stale_source_bytes']:
    data=copy.deepcopy(receipts)
    if name=='stale_origin_target':data['checks/publication.json']['targets'][0]['sha256']='0'*64
    elif name=='stale_origin_confirmation':next(iter(data['checks/publication.json']['confirmed_targets'].values()))['sha256']='0'*64
    elif name=='stale_public_delivery':data['checks/live_verification.json']['artifacts'][0]['sha256']='0'*64
    else:data['checks/source_archive_publication.json']['bytes']+=1
    with patch.object(m,'read',lambda key:data[key] if key in data else original(key)),patch.object(sys,'argv',['finalize.py']):
        try:m.main()
        except ValueError as e:
            assert any(x in str(e) for x in ['exact artifact manifest','exact origin SHA proof','Frozen-source delivery']),str(e)
        else:raise AssertionError('Accepted '+name)
    assert all(sha(Path(path))==digest for path,digest in before.items())
    passed.append(name)
gate=module('may_review_regression',root/'tools/review_gate.py')
exceptions=json.loads((root/'audit/canonical_source_exceptions.json').read_text())['exceptions']
if exceptions:
    proof=(root/exceptions[0]['timing_proof_file']).resolve();real_sha=gate.sha
    with patch.object(gate,'sha',lambda path:'0'*64 if path.resolve()==proof else real_sha(path)):
        try:gate.require_review()
        except ValueError as e:assert 'Timing proof changed' in str(e)
        else:raise AssertionError('Accepted changed timing proof')
    passed.append('changed_timing_proof')
else:
    # A changed exception inventory must be rejected even when there are none.
    exception_path=(root/'audit/canonical_source_exceptions.json').resolve();real_sha=gate.sha
    with patch.object(gate,'sha',lambda path:'0'*64 if path.resolve()==exception_path else real_sha(path)):
        try:gate.require_review()
        except ValueError as e:assert 'Timing exceptions or source auditor changed' in str(e)
        else:raise AssertionError('Accepted changed exception inventory')
    passed.append('changed_timing_exception_inventory')
assert all(sha(Path(path))==digest for path,digest in before.items())
record={'passed':True,'checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'finalizer_rejects':passed,'real_receipts_unchanged':True,
        'protected_receipt_sha256':before}
(root/'checks/tooling_regression.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
