"""Observed retained headline timing safety only; no author story selection."""
import gzip,json,re,sys
from pathlib import Path
R=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(R/'tools'))
from expand_capped_news import DATES
from ready_feeds import guard_hit,SEMANTIC_GUARDS,NAMED
families=[
 ('IT_outage','2024-07-19',r'outage|IT failure|computer crash|blue.screen|CrowdStrike|flight.{0,30}(?:cancel|ground)'),
 ('Biden_withdrawal','2024-07-19',r'Biden.*(?:withdraw|drop.{0,12}out|quits?|ends?|steps? aside|stand.{0,12}down|not seek|out of (?:the )?race)'),
 ('VP_nomination','2024-07-15',r'(?:Trump|Vance).*(?:running mate|nomination|nominat|VP pick|vice.presiden)|(?:running mate|VP pick).*(?:Trump|Vance)'),
 ('UK_status','2024-07-05',r'(?:Labour|Starmer|Sunak).*(?:election|exit.poll|victory|majority|landslide|prime minister|Downing Street|conced)|UK.*(?:exit.poll|landslide|election result)'),
 ('France_status','2024-07-05',r'(?:France|French).*(?:election|parliament|left.wing|Le Pen|National Rally)'),
 ('Trump_shooting','2024-07-12',r'Trump.*(?:shoot|shot|assassination|gunman|ear injury|rally attack)'),
 ('ETH_ETF_status','2024-07-23',r'(?=.*(?:Ethereum|ether|\bETH\b))(?=.*ETF)'),
]
rows={};blocked={};names={(x['date'],x['id'])for x in NAMED}
for date in DATES:
 stamp=date.isoformat();p=R/'work/source_candidates/unreviewed_feeds'/(stamp+'.json.gz');d=json.load(gzip.open(p,'rt'))
 for x in d['items']:
  for family,end,pattern in families:
   if stamp>end or not re.search(pattern,x['title'],re.I):continue
   hit=next((label for label,rx in SEMANTIC_GUARDS if rx.search(x['title'])),None)or guard_hit(x['title'],x['published_at'][:10],stamp)
   if(stamp,x['id'])in names:hit='named vintage omission'
   target=blocked if hit else rows;k=(family,x['title'],x['published_at'],x['src']);r=target.setdefault(k,dict(family=family,title=x['title'],published_at=x['published_at'],src=x['src'],dates=[],identities=[],guard=hit))
   r['dates'].append(stamp);r['identities'].append(dict(date=stamp,id=x['id']))
result=dict(purpose='Observed headline timing/status safety only; no retrospective story selection or future-outcome query.',retained=list(rows.values()),blocked=list(blocked.values()))
(R/'audit_work/unscheduled_eth_safety_candidates.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print('retained unique',len(rows),'blocked unique',len(blocked))
for i,x in enumerate(result['retained']):print(i,json.dumps({k:v for k,v in x.items()if k!='identities'},ensure_ascii=False))
