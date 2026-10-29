"""Audit frozen own-date feeds without changing them or exposing future evidence to writers."""
import datetime as dt, gzip, importlib.util, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location('guard',ROOT/'posthoc/release_guard.py')
guard=importlib.util.module_from_spec(sp);sp.loader.exec_module(guard)
summary=[]
for path in sorted((ROOT/'feeds').glob('*.json.gz')):
    feed=json.loads(gzip.decompress(path.read_bytes()));rows=[]
    for item in feed['items']:
        result=guard.screen_item(item,feed['cutoff_utc'])
        if result['exclude'] or result['review']:
            rows.append({'id':item['id'],'title':item['title'],**result})
    audit={'date':feed['date'],'cutoff_utc':feed['cutoff_utc'],'items_checked':len(feed['items']),'flagged':rows,
           'exclude_count':sum(bool(x['exclude']) for x in rows),'review_count':sum(bool(x['review']) for x in rows),
           'audited_at':dt.datetime.now(dt.timezone.utc).isoformat()}
    (ROOT/'audit'/('primary_release_guard_'+feed['date']+'.json')).write_text(json.dumps(audit,indent=2)+'\n')
    summary.append({k:audit[k] for k in ['date','items_checked','exclude_count','review_count']})
    print(feed['date'],audit['exclude_count'],audit['review_count'])
(ROOT/'audit/primary_release_guard_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
