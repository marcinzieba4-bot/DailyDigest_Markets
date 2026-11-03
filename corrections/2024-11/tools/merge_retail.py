"""Merge the independently authored same-date retail text into staged reports."""
from pathlib import Path
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parent.parent
FIELDS={'retail_intro','retail'}


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def merge(date):
    target=ROOT/'specs'/(date+'.json')
    source=ROOT/'retail_drafts'/(date+'.json')
    old=json.loads(target.read_text())
    retail=json.loads(source.read_text())
    if old['date']!=date or retail['date']!=date:
        raise ValueError('Date identity mismatch')
    if len(retail.get('retail',[]))!=4 or not retail.get('retail_intro'):
        raise ValueError('Four complete retail narratives required')
    before={k:v for k,v in old.items() if k not in FIELDS}
    result={**old,**{k:retail[k] for k in FIELDS}}
    assert before=={k:v for k,v in result.items() if k not in FIELDS}
    temp=target.with_suffix('.merge.tmp')
    temp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    temp.replace(target)
    out=ROOT/'checks'/('retail_merge_'+date+'.json')
    out.write_text(json.dumps({'date':date,'retail_source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'spec_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
        'nonretail_content_sha256':digest(before),'nonretail_preserved':True},indent=2)+'\n')
    print(date,'retail merged; nonretail preserved')


if __name__=='__main__':
    for date in sys.argv[1:]:
        merge(date)
