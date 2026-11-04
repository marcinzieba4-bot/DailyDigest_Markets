"""Bind final report text to the independent component reviews; no network calls."""
from pathlib import Path
import datetime as dt
import gzip
import hashlib
import importlib.util
import json
import re

ROOT=Path(__file__).resolve().parent.parent
DATES=[dt.date(2024,9,n).isoformat() for n in range(1,31) if dt.date(2024,9,n).weekday()<5]
FIELDS={'retail','retail_intro'}
CITE=re.compile(r'\[\[(n\d+)\]\]')
TOKEN=re.compile(r'\[\[([^\]]+)\]\]')
FX=re.compile(r'\b(?:USD/JPY|EUR/USD|AUD/USD|USD/CNY|GBP/USD|USD/PLN|EUR/PLN)\s+(?:closed|stood|finished|ended|was|at|traded|quoted)\s+(?:at\s+)?\d',re.I)


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def component(spec):
    value={k:v for k,v in spec.items() if k not in FIELDS}
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def save(path,value):
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
    temp.replace(path)


def main():
    spec=importlib.util.spec_from_file_location('sep_final_verify',ROOT/'tools/verify.py')
    verify=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verify)
    missing=[]
    for date in DATES:
        for folder,name in [('specs',date+'.json'),('retail_drafts',date+'.json'),
            ('audit','independent_nonretail_'+date+'.json'),('audit','independent_retail_'+date+'.json')]:
            if not (ROOT/folder/name).is_file():
                missing.append(str(Path(folder)/name))
    if missing:
        print('Pending reviewed inputs:',*missing,sep='\n')
        raise SystemExit(2)
    rows=[]
    warnings={}
    errors=[]
    source_review=load(ROOT/'audit/independent_source_review.json')
    semantic=source_review['known_semantic_exclusions']['by_date']
    timing=source_review['known_timing_exclusions']['by_date']
    if set(semantic)!=set(DATES) or set(timing)!=set(DATES):
        raise ValueError('Expected all 21 own-date source exclusion records')
    excluded={date:{row['id'] for row in record['exclusions']}
              for date,record in semantic.items()}
    for date,record in timing.items():
        excluded[date].update(row['id'] for row in record['exclusions'])
    extra_path=ROOT/'audit/additional_release_exclusions.json'
    for row in load(extra_path)['exclusions']:
        excluded.setdefault(row['date'],set()).add(row['id'])
    for date in DATES:
        sp=ROOT/'specs'/(date+'.json')
        rp=ROOT/'retail_drafts'/(date+'.json')
        data=load(sp)
        retail=load(rp)
        nrp=ROOT/'audit'/('independent_nonretail_'+date+'.json')
        rrp=ROOT/'audit'/('independent_retail_'+date+'.json')
        nr=load(nrp)
        rr=load(rrp)
        fp=ROOT/'feeds'/(date+'.json.gz')
        cp=ROOT/'cards'/(date+'.json')
        if any(record[date]['feed_sha256']!=sha(fp) for record in (semantic,timing)):
            errors.append(date+': source-exclusion record does not bind current own feed')
        if nr.get('fatal_or_major_remaining')!=0 or rr.get('fatal_or_major_remaining')!=0:
            errors.append(date+': unresolved independent review finding')
        if nr.get('nonretail_content_sha256')!=component(data):
            errors.append(date+': nonretail text changed after review')
        if rr.get('retail_draft_sha256',rr.get('draft_sha256'))!=sha(rp):
            errors.append(date+': retail draft changed after review')
        for record in [nr,rr]:
            if record.get('feed_sha256')!=sha(fp) or record.get('card_sha256')!=sha(cp):
                errors.append(date+': reviewed source hash mismatch')
        if any(data.get(k)!=retail.get(k) for k in FIELDS):
            errors.append(date+': reviewed retail not merged')
        fails,warns,source_count,words=verify.verify(date)
        errors.extend(date+': '+f for f in fails)
        warnings[date]=warns
        for w in warns:
            if not ('calendar wording' in w):
                errors.append(date+': unresolved validation warning: '+w)
        prose=' '.join(t for _,_,t in verify.paragraphs(data))
        bad=[x for x in TOKEN.findall(prose) if not re.fullmatch(r'n\d+',x)]
        if bad:
            errors.append(date+': unresolved nonstandard citation tokens '+repr(bad))
        if FX.search(prose):
            errors.append(date+': forbidden numeric spot-FX mark')
        cited=set(CITE.findall(prose))
        if cited & excluded.get(date,set()):
            errors.append(date+': known late/stale source used '+repr(sorted(cited & excluded[date])))
        feed={x['id']:x for x in json.loads(gzip.decompress(fp.read_bytes()))['items']}
        for key in cited:
            if re.search(r'Trump, Appealing to Bitcoin Fans',feed[key]['title'],re.I):
                errors.append(date+': stale July NYT story used as September fresh news')
        rows.append({'date':date,'spec_sha256':sha(sp),'nonretail_content_sha256':component(data),
            'retail_draft_sha256':sha(rp),'feed_sha256':sha(fp),'card_sha256':sha(cp),
            'nonretail_review_sha256':sha(nrp),'retail_review_sha256':sha(rrp),
            'words':words,'distinct_sources':source_count,'warnings':warns})
    if errors:
        print(*errors,sep='\n')
        raise SystemExit(1)
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    save(ROOT/'audit/final_editorial_review.json',{'checked_at_utc':now,'dates':DATES,
        'reports':rows,'fatal_or_major_remaining':0,
        'scope':'Each final nonretail component and retail draft is bound to its separate-author independent review; all reviews are AI reviews of frozen headlines/cards, not human review or original article-body-vintage verification.'})
    save(ROOT/'audit/final_precision_review.json',{'checked_at_utc':now,'passed':True,
        'dates':DATES,'spec_sha256':{x['date']:x['spec_sha256'] for x in rows},
        'additional_release_exclusions_sha256':sha(extra_path),
        'source_acceptance_sha256':sha(ROOT/'audit/independent_source_review.json'),
        'market_acceptance_sha256':sha(ROOT/'audit/independent_market_review.json'),
        'scope':'Independent component review bindings, own-date validator, explicit FX-mark exclusion, known late/stale source omissions and complete citation syntax. Semantic claim findings are in the per-date independent review receipts.'})
    save(ROOT/'checks/validation_warning_review.json',{'dates':DATES,'warnings':warnings,
        'disposition':'Remaining calendar-wording diagnostics are supported by own-date preview headlines and separately reviewed in the independent nonretail receipts.'})
    print('Final editorial and precision bindings passed:',len(rows),'reports,',sum(x['words'] for x in rows),'words')


if __name__=='__main__':
    main()
