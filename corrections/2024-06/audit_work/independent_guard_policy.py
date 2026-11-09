"""Independent June projection of inspected declarative guards, without owner functions.
The source table supplies event identities; separate control flow applies the reviewed
clause masks and independently selected actual/preview/boundary fixtures.
"""
from pathlib import Path
import ast,importlib.util,json,re,datetime as dt,hashlib
ROOT=Path(__file__).resolve().parent.parent
s=importlib.util.spec_from_file_location('independent_replay',ROOT/'audit_work/review_sources.py');a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
OBSERVED_PREVIEWS=frozenset()
DISPOSITIONS=a.READ(ROOT/'audit_work/june_observed_semantic_dispositions.json')['dispositions']
EVENT_DISPOSITIONS={(x['title'],x['guard']):x for x in DISPOSITIONS}
OBSERVED_PREVIEW_TITLES=frozenset(x['title']for x in DISPOSITIONS if x['disposition']=='preview')

def load():
 tree=ast.parse((ROOT/'tools/ready_feeds.py').read_text())
 node=next(n.value for n in tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='OBSERVED_COMPANY_PREVIEWS'for t in n.targets))
 assert isinstance(node,ast.Call)and isinstance(node.func,ast.Name)and node.func.id=='frozenset'and not node.args,'June has no unexplained exact-title preview exemptions'
 return a.patterns(ROOT/'tools/ready_feeds.py'),a.semantic_patterns(),a.READ(ROOT/'audit_work/june_release_schedule.json')

def guard(title,published,stamp,sp,fp,schedule):
 normal=sp['NEUTRALISE'].sub('',title)
 for event in schedule['guards']:
  if not(stamp<event['eligible_edition'] and event['earliest_pub_date']<=published<stamp and re.search(event['pattern'],title,re.I)):continue
  kind=event['kind'];label=event['label']
  if (title,label)in EVENT_DISPOSITIONS:continue
  if kind.startswith('split_'):
   remaining=re.sub(r'\b(?:split.adjusted|post.split)\s+trading\s+(?:will|is expected to|is set to|is scheduled to|to)\s+(?:begin|start|commence)\b','',normal,flags=re.I)
   remaining=sp['FORWARD_ACTION'].sub('',remaining)
   remaining=re.sub(r'\b(?:will|could|would|may|might|expected to|scheduled to|set to|plans? to|to)\s+(?:be\s+)?(?:split|distribute|distribute[ds]|complete|completed|become effective|effective|begin|start|commence|trade)\b[^,;.!?]{0,45}','',remaining,flags=re.I)
   expressions={
    'split_distribution':r'(?:has|have|had|was|were).{0,12}(?:split|distributed)|split.{0,25}(?:completed|effective|took effect)|(?:completed|completes|distributed|distributes).{0,30}(?:split|shares)|split.adjusted',
    'split_trading':r'split.adjusted.{0,35}(?:trading|trade)|(?:begins?|began|starts?|started|commences?|commenced).{0,35}(?:trading|trade).{0,25}split|(?:first|debut).{0,20}(?:day|session).{0,25}(?:after|following).{0,20}split'}
   if re.search(expressions[kind],remaining,re.I):return label
   continue
  if kind=='staged_event':
   remaining=sp['FORWARD_ACTION'].sub('',normal)
   actual=r'\b(?:trade insults|exchange accusations|attack(?:s|ed)?|accus(?:es|ed)|approved|approves?|authorized|authorizes?|voted|votes?|unveils?|unveiled|introduced|introduces|announced|revealed|reveals|launches?|launched|debuts?|debuted|clash(?:es|ed)?|spar(?:s|red)?|stumbles?|stumbled|rattles?|rattled|dominates?|dominated|wins?|won|loses?|lost|performance|takeaways|highlights|recap|what.{0,10}learned|fact.check)\b'
   if re.search(actual,remaining,re.I):return label
   historical=bool(re.search(r'debates? in history|presidential debate history|six decades of|facts about presidential|questions about presidential|presidential debates.{0,20}healthy democracy|most memorable.{0,25}debate history|which presidential debates drew',normal,re.I))
   prospective=r'how to watch|what time|what to (?:watch|know)|watching for|what.{0,3}at stake|faces? pressure to|to face off|faces? (?:Trump|Biden) in (?:the )?first.{0,20}debate|preview|what to expect|ahead of|set to|scheduled|plans? to|will|could|would|may|might|to (?:host|hold|begin|unveil|announce)|announces?.{0,30}(?:date|schedule)'
   if historical or re.search(prospective,normal,re.I):continue
   return label
  remaining=re.sub(r'\b(?:is|are)\s+(?:set|expected|likely|poised)\s+to\s+(?:begin|start|commence)\s+(?:rate\s+)?(?:cuts|hikes)\b','',normal,flags=re.I)
  remaining=re.sub(r'\b(?:expected to|forecast to|likely to|seen to|set to|will|could|would|may|might)\s+(?:keep|hold|leave)\b[^,;.!?]{0,50}\b(?:unchanged|steady|on hold)\b','',remaining,flags=re.I)
  for name in ['FORWARD_ACTION','MODAL_SUBJECT_ACTION','PENDING_POLICY_ACTION','PENDING_FINANCIAL_CLAUSE','FUTURE_RATE_NOUN']:remaining=sp[name].sub('',remaining)
  directly_governed=remaining!=normal
  if re.match(r'^\s*(?:what\s+)?if\b',normal,re.I):
   remaining=remaining.replace(re.split(r'[?;.!]',normal,maxsplit=1)[0],'',1);directly_governed=True
  calendar=bool(re.search(r'announc\w*.*(?:webcast|conference call|date|schedule)|sets? (?:the )?date|date for .*results',normal,re.I))
  preview=bool(directly_governed or calendar or sp['EXPLICIT_PREVIEW'].search(normal)or fp['PREVIEW'].search(normal)or sp['ADDITIONAL_FORWARD'].search(normal)or re.search(r'Outlook for|optimism about|before (?:Q[1-4] |quarterly )?(?:earnings|results)|nears? (?:the )?earnings|earnings to (?:reflect|show|test|reveal|shed)|here.s what you need to know|meeting started|(?:earnings|profits?|revenue|sales) (?:seen|expected|forecast) [a-z]+',normal,re.I))
  if kind in {'company_result','company_operation'}:
   financial=sp['MARKET_CLAUSE'].sub('',remaining)
   if sp['FINANCIAL_COMPLETION_HINT'].search(financial)or sp['FINANCIAL_OUTCOME'].search(financial):return label
   if re.search(r'court|lawsuit|appeal|tax',title,re.I)and not re.search(r'earnings|results|profits?|EPS|quarter',title,re.I):continue
   if preview:continue
   return label
  if kind=='policy':
   if sp['POLICY_OUTCOME'].search(remaining):return label
   if preview or sp['FORWARD'].search(normal):continue
   return label
  if sp['COMPLETED'].search(sp['MARKET_CLAUSE'].sub('',remaining)):return label
  if preview or sp['FORWARD'].search(normal):continue
  return label
 return None

# These are synthetic semantic controls, not historical factual evidence.
CASES=[
 ('US May ISM manufacturing contracts as services could rebound','2024-06-02','2024-06-03',True),
 ('US May ISM manufacturing expected to contract','2024-06-02','2024-06-03',False),
 ('US May ISM manufacturing contracts','2024-06-03','2024-06-04',False),
 ('China May Caixin manufacturing PMI expands','2024-06-02','2024-06-03',True),
 ('China May Caixin manufacturing PMI may expand','2024-06-02','2024-06-03',False),
 ('Japan real wages fell in April','2024-06-03','2024-06-04',True),
 ('Japan real wages fell in April','2024-06-04','2024-06-05',False),
 ('Japan April household spending rises','2024-06-05','2024-06-06',True),
 ('Japan April household spending rises','2024-06-06','2024-06-07',False),
 ('Japan Q1 GDP shrank less than expected','2024-06-06','2024-06-07',True),
 ('Japan Q1 GDP shrank less than expected','2024-06-09','2024-06-10',False),
 ('Japan May national CPI rises more than expected','2024-06-19','2024-06-20',True),
 ('Japan May national CPI rises more than expected','2024-06-20','2024-06-21',False),
 ('Tokyo June CPI rises','2024-06-26','2024-06-27',True),
 ('Tokyo June CPI rises','2024-06-27','2024-06-28',False),
 ('Japan May industrial output rebounds','2024-06-26','2024-06-27',True),
 ('Japan May industrial output rebounds','2024-06-27','2024-06-28',False),
 ('Japan May unemployment rate falls','2024-06-26','2024-06-27',True),
 ('Japan May unemployment rate falls','2024-06-27','2024-06-28',False),
 ('ECB cuts interest rates while Fed could hold','2024-06-05','2024-06-06',True),
 ('ECB expected to cut interest rates','2024-06-05','2024-06-06',False),
 ('ECB cuts interest rates','2024-06-06','2024-06-07',False),
 ('Can the Fed cut rates at June FOMC meeting?','2024-06-11','2024-06-12',False),
 ('FOMC holds rates as equities could gain','2024-06-11','2024-06-12',True),
 ('US May CPI rises less than expected','2024-06-11','2024-06-12',True),
 ('US May CPI expected to rise less than forecast','2024-06-11','2024-06-12',False),
 ('US May PCE inflation cools','2024-06-27','2024-06-28',True),
 ('US May PCE inflation may cool','2024-06-27','2024-06-28',False),
 ('Poland May industrial output falls','2024-06-19','2024-06-20',True),
 ('Poland May industrial output falls','2024-06-20','2024-06-21',False),
 ('Poland May wages rise','2024-06-19','2024-06-20',True),
 ('Poland May wages rise','2024-06-20','2024-06-21',False),
 ('Poland May retail sales rise','2024-06-23','2024-06-24',True),
 ('Poland May retail sales rise','2024-06-24','2024-06-25',False),
 ('Poland May unemployment rate falls','2024-06-24','2024-06-25',True),
 ('Poland May unemployment rate falls','2024-06-25','2024-06-26',False),
 ('Poland June flash CPI rises','2024-06-27','2024-06-28',True),
 ('NBP keeps interest rates unchanged as stocks could rise','2024-06-04','2024-06-05',True),
 ('NBP expected to keep interest rates unchanged','2024-06-04','2024-06-05',False),
 ('Apple unveiled Apple Intelligence at WWDC, iOS18 will launch later','2024-06-09','2024-06-10',True),
 ('Apple will unveil new software at WWDC','2024-06-09','2024-06-10',False),
 ('Apple announces WWDC date and schedule','2024-06-09','2024-06-10',False),
 ('Apple unveiled Apple Intelligence at WWDC','2024-06-10','2024-06-11',False),
 ('Biden stumbles in presidential debate as Trump could win','2024-06-27','2024-06-28',True),
 ('Biden will clash with Trump in presidential debate','2024-06-27','2024-06-28',False),
 ('CNN will host Biden Trump presidential debate','2024-06-27','2024-06-28',False),
 ('Nvidia stock split completed; shares will rise','2024-06-06','2024-06-07',True),
 ('Nvidia stock split will be completed after market close','2024-06-06','2024-06-07',False),
 ('Nvidia stock split distribution completed','2024-06-09','2024-06-10',False),
 ('Nvidia split-adjusted trading begins','2024-06-09','2024-06-10',True),
 ('Nvidia will begin split-adjusted trading','2024-06-09','2024-06-10',False),
 ('Nvidia split-adjusted trading begins','2024-06-10','2024-06-11',False),
 ('Chipotle split-adjusted trading begins as investors will buy','2024-06-25','2024-06-26',True),
 ('Chipotle stock split distribution completed','2024-06-25','2024-06-26',False),
 ('Chipotle will begin split-adjusted trading','2024-06-25','2024-06-26',False),
 ('Chipotle split-adjusted trading begins','2024-06-26','2024-06-27',False),
 ('Oracle quarterly earnings beat estimates as demand could grow','2024-06-10','2024-06-11',True),
 ('Oracle quarterly earnings expected to beat estimates','2024-06-10','2024-06-11',False),
 ('Oracle shares rise before quarterly earnings','2024-06-10','2024-06-11',False),
 ('Oracle quarterly earnings beat estimates','2024-06-11','2024-06-12',False),
 ('GameStop quarterly results show revenue fell','2024-06-06','2024-06-07',True),
 ('GameStop quarterly results show revenue fell','2024-06-07','2024-06-10',False),
 ('Micron revenue doubles and earnings beat estimates','2024-06-25','2024-06-26',True),
 ('Micron expected to report earnings growth','2024-06-25','2024-06-26',False),
]

CASES += [
 ('Biden and Trump trade insults in presidential debate, investors may worry','2024-06-27','2024-06-28',True),
 ('Biden will clash with Trump in presidential debate, following pressure','2024-06-27','2024-06-28',False),
 ('How to watch WWDC 2024 on iPhone, iPad, Mac & Apple TV - AppleInsider','2024-06-09','2024-06-10',False),
 ('Apple faces pressure to show off AI following splashy events at OpenAI, Google and Microsoft - CNBC','2024-06-09','2024-06-10',False),
 ('Chipotle shareholders approved stock split','2024-06-05','2024-06-06',True),
 ('Chipotle shareholders will approve stock split','2024-06-05','2024-06-06',False),
 ('Nvidia split-adjusted trading will begin on Monday','2024-06-09','2024-06-10',False),
]

def main():
 sp,fp,schedule=load();rows=[]
 for title,published,stamp,expected in CASES:
  found=guard(title,published,stamp,sp,fp,schedule);rows.append({'title':title,'published_date':published,'report_date':stamp,'expected_excluded':expected,'actual_guard':found,'passed':bool(found)==expected})
 errors=[]
 for event in schedule['guards']:
  release=event.get('release_utc')
  if release and dt.datetime.fromisoformat(event['eligible_edition']).replace(tzinfo=dt.timezone.utc)<=dt.datetime.fromisoformat(release):errors.append(event['label'])
 failed=[x for x in rows if not x['passed']]
 result={'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'status':'independent_semantic_regressions_only_pending_complete_source_review','passed':not failed and not errors,'schedule_sha256':a.SHA(ROOT/'audit_work/june_release_schedule.json'),'ready_tool_sha256':a.SHA(ROOT/'tools/ready_feeds.py'),'guard_count':len(schedule['guards']),'regressions':rows,'regression_failures':failed,'eligible_cutoff_math_errors':errors,'scope':'Independent synthetic actual/preview, mixed-clause, staged corporate event and early-Japan UTC-boundary controls. Not original publisher-vintage or report-prose approval.'}
 (ROOT/'audit_work/independent_june_guard_policy_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'passed':result['passed'],'cases':len(rows),'failures':failed,'cutoff_math_errors':errors},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
