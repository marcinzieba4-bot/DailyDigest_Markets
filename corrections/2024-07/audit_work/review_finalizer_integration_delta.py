"""Independent finalizer schema-integration tests; no authored reports are read."""
from pathlib import Path
import copy,hashlib,json,shutil,sys,datetime as dt
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'tools'))
import finalize_reviews as f
FIX=ROOT/'engineering_scratch/finalizer_integration_fixture'
if FIX.exists():shutil.rmtree(FIX)
(FIX/'audit').mkdir(parents=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_text())
save=lambda p,x:p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
source=load(ROOT/'audit/independent_source_review.json');rows={x['date']:x for x in source['dates']}
checks=[]
def check(name,ok):
 checks.append({'check':name,'passed':bool(ok)})
def reject(name,change_receipt=None,change_source=None,rebind=True,date='2024-07-02'):
 current=copy.deepcopy(source);current_rows={x['date']:x for x in current['dates']}
 p=FIX/'audit'/f'news_ready_{date}.json';original=p.read_bytes()
 try:
  if change_receipt:
   r=load(p);change_receipt(r);save(p,r)
   if rebind:
    current['input_bindings'][p.relative_to(FIX).as_posix()]=sha(p);current_rows[date]['ready_receipt_sha256']=sha(p)
  if change_source:change_source(current,current_rows)
  try:f.frozen_source_exclusions(current,current_rows);ok=False
  except (ValueError,KeyError,TypeError,FileNotFoundError):ok=True
  check(name,ok)
 finally:p.write_bytes(original)
# Current accepted production metadata, all23 receipts. No draft/spec is loaded.
f.ROOT=ROOT
actual,bindings=f.frozen_source_exclusions(source,rows)
check('actual current23 receipt schema accepted',len(actual)==23 and len(bindings)==23)
check('actual124 removed occurrences retained exactly',sum(len(x)for x in actual.values())==124 and all(actual[d]=={x['id']for x in load(ROOT/'audit'/f'news_ready_{d}.json')['excluded']}for d in f.DATES))
check('all current receipt hashes independently double-bound',all(source['input_bindings'][str(p.relative_to(ROOT))]==sha(p)==rows[d]['ready_receipt_sha256'] for d,p in [(d,ROOT/'audit'/f'news_ready_{d}.json')for d in f.DATES]))
check('current receipt feed hashes match frozen feeds',all(rows[d]['feed_sha256']==sha(ROOT/'feeds'/f'{d}.json.gz')for d in f.DATES))
for d in f.DATES:shutil.copyfile(ROOT/'audit'/f'news_ready_{d}.json',FIX/'audit'/f'news_ready_{d}.json')
f.ROOT=FIX
reject('missing both schema forms has no empty fallback',change_source=lambda s,r:s.pop('input_bindings'))
reject('missing input_bindings receipt hash rejected',change_source=lambda s,r:s['input_bindings'].pop('audit/news_ready_2024-07-02.json'))
reject('stale input_bindings receipt hash rejected',change_source=lambda s,r:s['input_bindings'].__setitem__('audit/news_ready_2024-07-02.json','stale'))
reject('missing date-row receipt hash rejected',change_source=lambda s,r:r['2024-07-02'].pop('ready_receipt_sha256'))
reject('stale date-row receipt hash rejected',change_source=lambda s,r:r['2024-07-02'].__setitem__('ready_receipt_sha256','stale'))
reject('changed receipt bytes without rebind rejected',lambda r:r.__setitem__('status','pending'),rebind=False)
reject('wrong receipt date rejected even with both hashes rebound',lambda r:r.__setitem__('date','2024-07-03'))
reject('pending receipt status rejected even with both hashes rebound',lambda r:r.__setitem__('status','pending'))
reject('wrong ready feed hash rejected even with both hashes rebound',lambda r:r.__setitem__('ready_sha256','stale'))
reject('missing exclusion list rejected',lambda r:r.pop('excluded'))
reject('non-list exclusion payload rejected',lambda r:r.__setitem__('excluded',{}))
reject('exclusion count mismatch rejected',lambda r:r.__setitem__('excluded_items',r['excluded_items']+1))
reject('duplicate removed identity rejected',lambda r:(r['excluded'].append(copy.deepcopy(r['excluded'][0])),r.__setitem__('excluded_items',len(r['excluded']))))
reject('accepted row exclusion count mismatch rejected',change_source=lambda s,r:r['2024-07-02'].__setitem__('excluded',r['2024-07-02']['excluded']+1))
reject('accepted row ready count mismatch rejected',change_source=lambda s,r:r['2024-07-02'].__setitem__('ready_items',r['2024-07-02']['ready_items']+1))
reject('accepted row raw count mismatch rejected',change_source=lambda s,r:r['2024-07-02'].__setitem__('raw_items',r['2024-07-02']['raw_items']+1))
reject('boolean exclusion count rejected',lambda r:r.__setitem__('excluded_items',False),date='2024-07-01')
reject('negative input count rejected',lambda r:r.__setitem__('input_items',-1))
reject('empty removed identity rejected',lambda r:r['excluded'][0].__setitem__('id',''))
reject('raw screening hash mismatch rejected',lambda r:r.__setitem__('unreviewed_sha256','stale'))
reject('malformed bindings object rejected',change_source=lambda s,r:s.__setitem__('input_bindings',[]))
reject('noncanonical removed identity rejected',lambda r:r['excluded'][0].__setitem__('id','ALIAS'))
reject('receipt and accepted counters must also balance',lambda r:r.__setitem__('ready_items',r['ready_items']-1),change_source=lambda s,r:r['2024-07-02'].__setitem__('ready_items',r['2024-07-02']['ready_items']-1))
reject('boolean accepted count rejected',change_source=lambda s,r:r['2024-07-01'].__setitem__('excluded',False),date='2024-07-01')
# Strict legacy input remains usable, including two overlapping reasons for one ID.
legacy={'known_semantic_exclusions':{'by_date':{d:{'feed_sha256':rows[d]['feed_sha256'],'exclusions':[{'id':'n0001'}]}for d in f.DATES}},'known_timing_exclusions':{'by_date':{d:{'feed_sha256':rows[d]['feed_sha256'],'exclusions':[{'id':'n0001'},{'id':'n0002'}]}for d in f.DATES}}}
ids,stable=f.frozen_source_exclusions(legacy,rows)
check('legacy full23 coverage and reason overlap accepted',len(ids)==23 and all(v=={'n0001','n0002'}for v in ids.values())and stable=={})
for name,mutate in [
 ('partial legacy schema rejected',lambda x:x.pop('known_timing_exclusions')),
 ('legacy incomplete date coverage rejected',lambda x:x['known_semantic_exclusions']['by_date'].pop('2024-07-01')),
 ('legacy extra date rejected',lambda x:x['known_semantic_exclusions']['by_date'].__setitem__('2024-08-01',{})),
 ('legacy stale source hash rejected',lambda x:x['known_timing_exclusions']['by_date']['2024-07-01'].__setitem__('feed_sha256','stale')),
 ('legacy malformed exclusion list rejected',lambda x:x['known_timing_exclusions']['by_date']['2024-07-01'].__setitem__('exclusions',None)),
 ('legacy duplicate identity within one reason rejected',lambda x:x['known_timing_exclusions']['by_date']['2024-07-01']['exclusions'].append({'id':'n0001'})),
 ('legacy empty removed identity rejected',lambda x:x['known_semantic_exclusions']['by_date']['2024-07-01']['exclusions'][0].__setitem__('id','')),
]:
 x=copy.deepcopy(legacy);mutate(x)
 try:f.frozen_source_exclusions(x,rows);ok=False
 except (ValueError,KeyError,TypeError):ok=True
 check(name,ok)
# A partial legacy declaration must never bypass current schema bindings.
partial=copy.deepcopy(source);partial['known_semantic_exclusions']=legacy['known_semantic_exclusions']
try:f.frozen_source_exclusions(partial,rows);ok=False
except (ValueError,KeyError,TypeError):ok=True
check('partial legacy cannot fall back to otherwise valid current receipts',ok)
report={'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'finalizer_sha256':sha(ROOT/'tools/finalize_reviews.py'),'actual_source_acceptance_sha256':sha(ROOT/'audit/independent_source_review.json'),'actual_receipt_count':len(actual),'actual_removed_occurrences':sum(len(x)for x in actual.values()),'checks':checks,'passed':all(x['passed']for x in checks),'failures':[x for x in checks if not x['passed']],'production_drafts_or_specs_read':False,'production_inputs_modified':False}
save(ROOT/'engineering_scratch/finalizer_integration_tests.json',report)
print(json.dumps({'checks':len(checks),'passed':sum(x['passed']for x in checks),'failures':report['failures']},indent=2))
