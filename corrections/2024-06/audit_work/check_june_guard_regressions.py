"""Owner-side June actual/preview/stage regression fixtures, never independent acceptance."""
import sys,json,hashlib
from pathlib import Path
R=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(R/'tools'))
from ready_feeds import guard_hit,SCHEDULE_PATH
from fetch_news import semantic_category
CASES=[
 ('Biden stumbles in presidential debate; six decades of history may explain it','2024-06-27','2024-06-28',True),
 ('Biden and Trump trade insults in presidential debate; investors may worry','2024-06-27','2024-06-28',True),
 ('Biden and Trump will trade insults in presidential debate','2024-06-27','2024-06-28',False),
 ('Cut rates - then what? Five questions for the ECB','2024-06-02','2024-06-03',False),
 ('ECB Is Set to Begin Cuts But Path Beyond Gets Murkier','2024-06-05','2024-06-06',False),
 ('Euro area bank interest rate statistics: April 2024 - European Central Bank','2024-06-05','2024-06-06',False),
 ('How to watch the CNN Biden-Trump presidential debate','2024-06-25','2024-06-26',False),
 ('What time is the first US presidential debate tonight?','2024-06-27','2024-06-28',False),
 ('The Biden-Trump presidential debate: what to watch for','2024-06-27','2024-06-28',False),
 ('Presidential Debates in History That Moved the Needle','2024-06-24','2024-06-25',False),
 ('Biden and Trump trade insults in presidential debate','2024-06-27','2024-06-28',True),
 ('Apple faces pressure to show off AI following splashy events at OpenAI, Google and Microsoft','2024-06-09','2024-06-10',False),
 ('Polska: minimalne wynagrodzenie rośnie','2024-06-19','2024-06-20',False),
 ('Polska: przeciętne wynagrodzenie rośnie','2024-06-19','2024-06-20',True),
 ('NBP expected to keep interest rates unchanged','2024-06-04','2024-06-05',False),
 ('NBP keeps interest rates unchanged; ECB expected to keep rates steady','2024-06-04','2024-06-05',True),
 ('ECB cuts interest rates; another move may follow','2024-06-05','2024-06-06',True),
 ('ECB expected to cut interest rates on Thursday','2024-06-05','2024-06-06',False),
 ('ECB cuts interest rates','2024-06-06','2024-06-07',False),
 ('US May payrolls rise; Fed could wait longer','2024-06-06','2024-06-07',True),
 ('US May payrolls expected to rise','2024-06-06','2024-06-07',False),
 ('US May payrolls rise','2024-06-07','2024-06-10',False),
 ('US May CPI inflation at 3.3%','2024-06-11','2024-06-12',True),
 ('US May CPI inflation falls; markets may gain','2024-06-11','2024-06-12',True),
 ('US CPI inflation may fall in May','2024-06-11','2024-06-12',False),
 ('US CPI inflation preview: what to expect','2024-06-11','2024-06-12',False),
 ('Fed holds interest rates; September cut may follow','2024-06-11','2024-06-12',True),
 ('Fed expected to hold interest rates','2024-06-11','2024-06-12',False),
 ('Fed holds interest rates','2024-06-12','2024-06-13',False),
 ('BOJ keeps interest rates unchanged','2024-06-13','2024-06-14',True),
 ('BOJ to discuss bond buying at policy meeting','2024-06-13','2024-06-14',False),
 ('BOJ keeps interest rates unchanged','2024-06-14','2024-06-17',False),
 ('Bank of England holds interest rates; cuts may follow','2024-06-19','2024-06-20',True),
 ('Bank of England expected to hold interest rates','2024-06-19','2024-06-20',False),
 ('Japan wages rise in April','2024-06-04','2024-06-05',False),
 ('Japan household spending rises in April','2024-06-06','2024-06-07',False),
 ('Japan Q1 GDP shrinks','2024-06-09','2024-06-10',False),
 ('Japan May national core CPI inflation rises','2024-06-20','2024-06-21',False),
 ('Japan Tokyo CPI inflation rises','2024-06-27','2024-06-28',False),
 ('Japan May industrial production rises','2024-06-27','2024-06-28',False),
 ('Apple unveiled Apple Intelligence at WWDC; iOS18 will launch later','2024-06-09','2024-06-10',True),
 ('Apple will unveil AI at WWDC','2024-06-09','2024-06-10',False),
 ('Apple announces date for WWDC developer conference','2024-06-09','2024-06-10',False),
 ('Nvidia stock split completed; shares will rise','2024-06-06','2024-06-07',True),
 ('Nvidia stock split will become effective Friday','2024-06-06','2024-06-07',False),
 ('Nvidia announces stock split for June','2024-06-06','2024-06-07',False),
 ('Nvidia begins trading on a split-adjusted basis','2024-06-09','2024-06-10',True),
 ('Nvidia will begin split-adjusted trading Monday','2024-06-09','2024-06-10',False),
 ('Chipotle split-adjusted trading begins as investors will buy','2024-06-25','2024-06-26',True),
 ('Chipotle split-adjusted trading will begin Wednesday','2024-06-25','2024-06-26',False),
 ('Biden stumbles in presidential debate; Trump may benefit','2024-06-27','2024-06-28',True),
 ('Biden Trump presidential debate preview: what to expect','2024-06-27','2024-06-28',False),
 ('Broadcom reports earnings beat; shares may rise','2024-06-11','2024-06-12',True),
 ('Broadcom expected to report earnings growth','2024-06-11','2024-06-12',False),
 ('GitLab reports first quarter earnings growth','2024-06-02','2024-06-03',True),
 ('GitLab reports first quarter earnings growth','2024-06-03','2024-06-04',False),
 ('GameStop reports quarterly sales decline','2024-06-06','2024-06-07',True),
 ('GameStop reports quarterly sales decline','2024-06-07','2024-06-10',False),
 ('Poland retail sales rise','2024-06-23','2024-06-24',True),
 ('Poland retail sales rise','2024-06-24','2024-06-25',False),
 ('Poland June flash inflation rises','2024-06-27','2024-06-28',True),
 ('US PCE inflation falls; rate cuts may come','2024-06-27','2024-06-28',True),
 ('US PCE inflation expected to fall','2024-06-27','2024-06-28',False),
]
result=[]
for title,pub,cut,blocked in CASES:
 hit=guard_hit(title,pub,cut);result.append(dict(title=title,published=pub,cutoff=cut,expected_blocked=blocked,actual_guard=hit,passed=bool(hit)==blocked))
AGE=[('US May CPI inflation falls','monthly','monthly'),('Nvidia launches new product','monthly','news'),('Oracle quarterly earnings beat estimates','monthly','result'),('Apple earnings preview','result','news'),('Oracle earnings date announced','result','news'),('Upcoming Micron quarterly results','result','news'),('US CPI inflation may fall','monthly','news')]
for title,cat,expected in AGE:result.append(dict(title=title,category=cat,expected_category=expected,actual_category=semantic_category(title,cat),passed=semantic_category(title,cat)==expected))
out={'status':'owner_regressions_only_not_independent_acceptance','cases':result,'passed':all(x['passed']for x in result),'release_schedule_sha256':hashlib.sha256(SCHEDULE_PATH.read_bytes()).hexdigest(),'screening_tool_sha256':hashlib.sha256((R/'tools/ready_feeds.py').read_bytes()).hexdigest()}
(R/'audit_work/june_guard_regressions.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'passed':out['passed'],'cases':len(result),'failures':[x for x in result if not x['passed']]},indent=2));raise SystemExit(not out['passed'])
