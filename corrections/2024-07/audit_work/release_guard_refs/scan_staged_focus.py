"""One bounded read-only scan of staged source headlines in the requested scope."""
from pathlib import Path
import sys,json,gzip,re,hashlib,datetime as dt
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'));import ready_feeds as policy
rx_japan=re.compile(r'(?=.*(?:Japan|Japanese|Tokyo|Tankan))(?=.*(?:Tankan|household spending|wages|base pay|CPI|inflation|PMI|trade surplus|retail sales))',re.I)
rx_gus=re.compile(r'\bGUS\b|(?=.*(?:Poland|Polish|Polsk\w*))(?=.*(?:wages|industrial output|industrial production|retail sales|unemployment))',re.I)
rx_uk=re.compile(r'(?=.*(?:\bUK\b|Britain|British|Labour|Starmer|Sunak))(?=.*(?:exit.poll|election|prime minister|Downing Street|concede))',re.I)
rx_company=re.compile(r'(?=.*(?<!\w)(?:Samsung|SK Hynix|ASML|Microsoft|AMD|Meta|TSMC|Taiwan Semiconductor)(?!\w))(?=.*(?:earnings|results|revenue|sales|profit|guidance|forecast|bookings|EPS))',re.I)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
seen={};inputs=[];named={(x['date'],x['id']):x for x in policy.NAMED}
for path in sorted((R/'work/source_candidates/feeds').glob('2024-07-*.json.gz')):
 data=json.load(gzip.open(path,'rt'));date=data['date']
 inputs.append({'date':date,'path':str(path.relative_to(R)),'sha256':sha(path),'staged_schedule_sha256':data.get('release_schedule_sha256')})
 for x in data['items']:
  if not '2024-06-01'<=x['published_at'][:10]<'2024-08-01':continue
  if not any(rx.search(x['title'])for rx in [rx_japan,rx_gus,rx_uk,rx_company]):continue
  key=(x['title'],x['url'])
  row=seen.setdefault(key,{k:x[k]for k in ['title','url','published_at','src']})
  hit=named.get((date,x['id']),{}).get('guard')or next((label for label,pattern in policy.SEMANTIC_GUARDS if pattern.search(x['title'])),None)or policy.guard_hit(x['title'],x['published_at'][:10],date)
  row.setdefault('appearances',[]).append({'date':date,'id':x['id'],'current_policy_exclusion':hit})
rows=sorted(seen.values(),key=lambda x:(x['appearances'][0]['date'],x['published_at'],x['title']))
out={'purpose':'One bounded actual staged-headline scan; provisional old candidates do not establish authoring acceptance.',
     'scope':'June/July-dated staged records matching Japanese release clocks, GUS/Poland releases, UK election status, and seven named company clocks.',
     'generated_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'schedule_sha256':sha(policy.SCHEDULE_PATH),
     'screening_tool_sha256':sha(R/'tools/ready_feeds.py'),'named_exclusions_sha256':sha(policy.NAMED_PATH),
     'input_candidates':inputs,'distinct_headlines':len(rows),'headlines':rows}
p=Path(__file__).with_name('focused_staged_headline_scan.json');p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
for i,x in enumerate(rows):
 app=x['appearances'];blocked=[a for a in app if a['current_policy_exclusion']]
 print(f"{i+1:03d} | {app[0]['date']} {app[0]['id']} | {x['published_at']} | {x['src']} | {x['title']}"+((' | CURRENT EXCLUDES '+','.join(a['date']+':'+str(a['current_policy_exclusion'])for a in blocked))if blocked else''))
print('SCANNED',len(inputs),'provisional candidates;',len(rows),'distinct matching headlines')
