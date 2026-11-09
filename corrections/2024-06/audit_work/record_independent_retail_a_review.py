from pathlib import Path
import datetime,gzip,hashlib,json,re,sys
R=Path('/workspace/work/june2024');sys.path.insert(0,str(R/'tools'));import verify
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def patch(date,where,old,new,reason):
 p=R/'retail_drafts'/f'{date}.json';before=p.read_bytes();s=json.loads(before);b=s
 for k in where[:-1]:b=b[k]
 assert old in b[where[-1]] and b[where[-1]].count(old)==1
 b[where[-1]]=b[where[-1]].replace(old,new)
 h=R/'audit/review_history/retail_review_a'/f'{date}_{hashlib.sha256(before).hexdigest()}.json';h.write_bytes(before)
 p.write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n')
 return {'path':where,'old':old,'new':new,'reason':reason,'before_sha256':hashlib.sha256(before).hexdigest(),'after_sha256':sha(p),'preserved_before_bytes':str(h.relative_to(R))}
def record(date,claims,chronology,fixes=None,warnings=None):
 p=R/'retail_drafts'/f'{date}.json';s=json.loads(p.read_text());notes=json.loads((R/'notes'/f'retail_{date}.json').read_text());ex=R/'exclusions'/f'{date}.json';ev=json.loads(ex.read_text());f=R/'feeds'/f'{date}.json.gz';c=R/'cards'/f'{date}.json'
 assert ev['feed_sha256']==sha(f)
 ids=list(dict.fromkeys(re.findall(r'\[\[(n\d+)\]\]',json.dumps(s,ensure_ascii=False))))
 assert not set(ids)&{v['id']for v in ev['exclusions']}
 assert notes['lead']==s['retail'][0]['title'] and notes['smaller']==[v['title']for v in s['retail'][1:]]
 errors,raw,n,words=verify.verify(date,retail_only=True);assert not errors,errors
 dispositions=warnings or [];assert sorted(raw)==sorted(x['warning']for x in dispositions),(raw,dispositions)
 r={'date':date,'status':'accepted','reviewer':'/root/june_nonretail_a, independent of the original retail author','checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'fatal_or_major_remaining':0,'retail_draft_sha256':sha(p),'feed_sha256':sha(f),'card_sha256':sha(c),'exclusions_sha256':sha(ex),'paragraphs_reviewed':13,'distinct_cited_headlines_reviewed':ids,'findings':[],'named_fixes':fixes or [],'claim_checks':claims,'chronology':{'earlier_notes_reviewed':sorted(x.stem.replace('retail_','')for x in(R/'notes').glob('retail_*.json')if x.stem.replace('retail_','')<date),'notes_match_current_selection':True,'material_change':chronology,'selection_rationale':notes['why_lead']},'reviewed_validation_warnings':dispositions,'verification':{'passed':True,'sources':n,'body_words':words,'failures':0,'warnings':len(raw)},'limitations':['Independent headline/card review; article-body details and measured cross-market retail popularity are not asserted.','Crowd motivation and hypothetical professional approaches are editorial interpretation rather than fabricated flow, position or social-count evidence.']}
 out=R/'audit'/f'independent_retail_{date}.json';assert not out.exists(),out;out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(date,'accepted',words,'words',len(ids),'sources',sha(out))
