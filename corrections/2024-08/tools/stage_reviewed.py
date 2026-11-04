"""Merge only current, separately reviewed components and run own-date final validation."""
from pathlib import Path
import datetime as dt,hashlib,importlib.util,json
ROOT=Path(__file__).resolve().parent.parent
DATES=[dt.date(2024,8,n).isoformat() for n in range(1,32) if dt.date(2024,8,n).weekday()<5]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
component=lambda j:hashlib.sha256(json.dumps(j,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
load=lambda p:json.loads(p.read_text())
module=importlib.util.spec_from_file_location('aug_verify',ROOT/'tools/verify.py');verify=importlib.util.module_from_spec(module);module.loader.exec_module(verify)
ready=[];pending=[];errors=[]
for date in DATES:
    paths=[ROOT/'nonretail_drafts'/f'{date}.json',ROOT/'retail_drafts'/f'{date}.json',ROOT/'audit'/f'independent_nonretail_{date}.json',ROOT/'audit'/f'independent_retail_{date}.json']
    if not all(p.is_file() for p in paths):pending.append(date);continue
    nr,retail,nreview,rreview=map(load,paths)
    expected={'feed_sha256':sha(ROOT/'feeds'/f'{date}.json.gz'),'card_sha256':sha(ROOT/'cards'/f'{date}.json')}
    if (nreview.get('fatal_or_major_remaining')!=0 or rreview.get('fatal_or_major_remaining')!=0
        or nreview.get('nonretail_content_sha256')!=component(nr)
        or rreview.get('retail_draft_sha256',rreview.get('draft_sha256'))!=sha(paths[1])
        or any(review.get(k)!=v for review in [nreview,rreview] for k,v in expected.items())):
        errors.append({'date':date,'error':'Component review is unresolved or stale'});continue
    if {'retail','retail_intro'}&set(nr):raise ValueError('Nonretail author has retail keys')
    result={**nr,'retail_intro':retail['retail_intro'],'retail':retail['retail']}
    assert component({k:v for k,v in result.items() if k not in {'retail','retail_intro'}})==component(nr)
    path=ROOT/'specs'/f'{date}.json';blob=(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode()
    if not path.exists() or path.read_bytes()!=blob:
        temp=path.with_suffix('.merge.tmp');temp.write_bytes(blob);temp.replace(path)
    fail,warn,count,words=verify.verify(date)
    ready.append({'date':date,'words':words,'sources':count,'failures':fail,'warnings':warn,'spec_sha256':sha(path)})
    errors.extend({'date':date,'error':message} for message in fail)
report={'ready':ready,'pending':pending,'errors':errors,'ready_count':len(ready),'total_words':sum(x['words'] for x in ready)}
(ROOT/'checks/staged_reviewed.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'ready':len(ready),'pending':pending,'errors':errors,'warnings':{x['date']:x['warnings']for x in ready if x['warnings']},'total_words':report['total_words']},ensure_ascii=False,indent=2))
