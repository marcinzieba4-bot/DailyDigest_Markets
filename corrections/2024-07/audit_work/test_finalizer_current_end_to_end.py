"""Synthetic end-to-end current receipt schema and stability checks only."""
from pathlib import Path
import copy,contextlib,gzip,hashlib,io,json,shutil,sys
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'tools'))
import finalize_reviews as f,merge_retail,verify
FIX=ROOT/'engineering_scratch/current_finalizer_end_to_end'
if FIX.exists():shutil.rmtree(FIX)
shutil.copytree(ROOT/'engineering_scratch/fixtures',FIX)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_text())
save=lambda p,x:p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
source=load(FIX/'audit/independent_source_review.json')
for name in ['known_semantic_exclusions','known_timing_exclusions']:source.pop(name)
source['input_bindings']={}
for row in source['dates']:
 date=row['date']
 raw=copy.deepcopy(json.loads(gzip.decompress((FIX/'feeds'/f'{date}.json.gz').read_bytes())))
 raw['items'].append({**raw['items'][0],'id':'n999999','title':'Synthetic discarded source'})
 rawbytes=gzip.compress(json.dumps(raw).encode(),mtime=0)
 rawpath=FIX/'work/unreviewed_feeds'/f'{date}.json.gz';rawpath.parent.mkdir(parents=True,exist_ok=True);rawpath.write_bytes(rawbytes)
 ready={'date':date,'status':'ready','input_items':51,'ready_items':50,'excluded_items':1,
        'ready_sha256':row['feed_sha256'],'unreviewed_sha256':sha(rawpath),
        'excluded':[{'id':'n999999','guard':'Synthetic explicit exclusion'}]}
 path=FIX/'audit'/f'news_ready_{date}.json';save(path,ready)
 row.update(raw_items=51,ready_items=50,excluded=1,raw_sha256=sha(rawpath),ready_receipt_sha256=sha(path))
 source['input_bindings'][path.relative_to(FIX).as_posix()]=sha(path)
save(FIX/'audit/independent_source_review.json',source)
f.ROOT=merge_retail.ROOT=FIX;verify.C=str(FIX)
checks=[]
def check(name,ok):
 assert ok,name
 checks.append({'check':name,'passed':True})
with contextlib.redirect_stdout(io.StringIO()):code=f.main()
check('full23 current-schema synthetic finalization passes',code==0 and load(FIX/'audit/final_editorial_review.json')['all_23_ready']is True)
editorial=FIX/'audit/final_editorial_review.json';original_editorial=editorial.read_bytes()
source_path=FIX/'audit/independent_source_review.json';original_source=source_path.read_bytes()
value=load(source_path);value['input_bindings'].pop('audit/news_ready_2024-07-02.json');save(source_path,value)
try:
 with contextlib.redirect_stdout(io.StringIO()):f.main()
 failed=False
except ValueError:failed=True
finally:source_path.write_bytes(original_source)
check('full current-schema missing binding fails before new final receipt',failed and editorial.read_bytes()==original_editorial)
retained=FIX/'exclusions/2024-07-01.json';original_retained=retained.read_bytes();value=load(retained);value['exclusions']=[{'id':'n0001','reason':'Synthetic retained-source exclusion'}];save(retained,value)
with contextlib.redirect_stdout(io.StringIO()):code=f.main()
retained.write_bytes(original_retained)
check('current schema does not bypass retained own-date exclusions',code==1 and editorial.read_bytes()==original_editorial)
receipt=FIX/'audit/news_ready_2024-07-02.json';original_receipt=receipt.read_bytes()
original_gate=f.retail_quality_snapshot.require_review
def mutate_after_screening(root):
 result=original_gate(root);receipt.write_bytes(original_receipt+b' ');return result
f.retail_quality_snapshot.require_review=mutate_after_screening
try:
 with contextlib.redirect_stdout(io.StringIO()):f.main()
 failed=False
except ValueError as exc:failed='changed during final binding'in str(exc)
finally:
 receipt.write_bytes(original_receipt);f.retail_quality_snapshot.require_review=original_gate
check('all current ready receipts participate in final stability check',failed and editorial.read_bytes()==original_editorial)
report={'purpose':'Synthetic full current-schema finalization; no production reports read or written.','passed':True,'checks':checks,'finalizer_sha256':sha(ROOT/'tools/finalize_reviews.py'),'production_inputs_modified':False}
save(ROOT/'audit/finalizer_current_schema_end_to_end_tests.json',report)
print(json.dumps({'checks':len(checks),'passed':True}))
