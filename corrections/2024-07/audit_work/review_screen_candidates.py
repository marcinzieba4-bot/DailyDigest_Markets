"""Create current-screen editorial candidates without touching frozen/feed destinations."""
import collections,gzip,hashlib,json,sys
from pathlib import Path
R=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(R/'tools'))
from expand_capped_news import DATES,sha
from ready_feeds import screen
rows={};date_rows=[];out=R/'audit_work/screen_candidate_review';out.mkdir(exist_ok=True)
for date in DATES:
 raw=json.load(gzip.open(R/'work/source_candidates/unreviewed_feeds'/(date.isoformat()+'.json.gz'),'rt'));receipt=screen(date,raw=raw,persist=False);receipt.pop('_payload')
 (out/(date.isoformat()+'.json')).write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n');date_rows.append(dict(date=date.isoformat(),ready=receipt['ready_items'],excluded=receipt['excluded_items'],by_guard=receipt['excluded_by_guard']))
 for x in receipt['excluded']:
  key=(x['guard'],x['title'],x['published_at'],x['src']);row=rows.setdefault(key,dict(guard=x['guard'],title=x['title'],published_at=x['published_at'],src=x['src'],dates=[],ids=[]))
  row['dates'].append(date.isoformat());row['ids'].append(dict(date=date.isoformat(),id=x['id']))
result=dict(phase='current_screen_editorial_review_candidates_no_acceptance',dates=date_rows,unique_excluded=list(rows.values()),screening_tool_sha256=sha(R/'tools/ready_feeds.py'),schedule_sha256=sha(R/'audit_work/july_release_schedule.json'),named_exclusions_sha256=sha(R/'audit_work/july_named_source_exclusions.json'))
(out/'all.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n');print('23 dates',sum(x['ready']for x in date_rows),'ready',sum(x['excluded']for x in date_rows),'excluded occurrences',len(rows),'unique exclusions')
for i,x in enumerate(result['unique_excluded']):print(i,json.dumps({k:v for k,v in x.items()if k!='ids'},ensure_ascii=False))
