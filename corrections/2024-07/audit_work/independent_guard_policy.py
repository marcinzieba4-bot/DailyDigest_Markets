"""Independent application of declarative July guard data and inspected regex policy; no owner functions invoked."""
from pathlib import Path
import ast,importlib.util,json,re,datetime as dt,hashlib
ROOT=Path('/workspace/work/july2024')
s=importlib.util.spec_from_file_location('independent_replay',ROOT/'audit_work/review_sources.py');a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
OBSERVED_PREVIEWS={
 'Microsoft (MSFT) Analysis: Volatile Trading Day Signals Resistance, Await Earnings for Clarity - StockInvest.us',
 "The 'great rotation' faces its biggest test yet: earnings from Microsoft, Meta, Apple and Amazon - CNBC",
 'Microsoft’s earnings report will offer a new gauge for AI demand and cloud investments - GeekWire',
}
def load():
 tree=ast.parse((ROOT/'tools/ready_feeds.py').read_text());declared=next(n.value for n in tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='OBSERVED_COMPANY_PREVIEWS'for t in n.targets));assert isinstance(declared,ast.Call)and isinstance(declared.func,ast.Name)and declared.func.id=='frozenset'and set(a.literal(declared.args[0],{}))==OBSERVED_PREVIEWS,'Only the three independently inspected exact preview controls are allowed';return a.patterns(ROOT/'tools/ready_feeds.py'),a.semantic_patterns(),a.READ(ROOT/'audit_work/july_release_schedule.json')
def guard(title,published,stamp,sp,fp,schedule):
 if title in OBSERVED_PREVIEWS:return None
 normal=sp['NEUTRALISE'].sub('',title)
 for meta in schedule['guards']:
  label,eligible,start,pattern=(meta[k]for k in ['label','eligible_edition','earliest_pub_date','pattern'])
  if not(stamp<eligible and start<=published<stamp and re.search(pattern,title,re.I)):continue
  kind=meta['kind']
  if kind=='uk_settled_result':
   future_masked=re.sub(r'\b(?:will|could|may|might|would)\s+(?:be|become)\s+(?:named|sworn in|appointed|prime minister)\b','',title,flags=re.I)
   if sp['SETTLED_UK'].search(future_masked):return label
   if stamp>='2024-07-05'and re.search(r'exit.poll|projection|projected',title,re.I)and not re.search(r'official|confirmed|appointed|becomes? prime minister|resigns?',title,re.I):continue
  if kind=='biden_withdrawal':
   if re.search(r'\b(?:not|won.t|will not)\s+(?:drop out|withdraw|quit)|stay(?:ing|s)? in (?:the )?race',title,re.I):continue
   demand=re.search(r'\b(?:urges?|calls?|pressures?|asks?|wants?|demands?)\b.*Biden.*(?:withdraw|drop|quit|stand|step)',title,re.I);declared=re.search(r'Biden\s+(?:(?:has|just|now)\s+)?(?:withdraws|withdrew|withdrawn|drops out|dropped out|quits|ends|steps aside|stands down|announces|announced)|Biden.{0,30}(?:says|said).{0,20}(?:will not seek|won.t seek)|Biden\s+(?:will not seek|won.t seek)',title,re.I)
   if demand and not declared:continue
   if declared:return label
  if kind=='exit_poll':
   if re.search(r'what to expect|ahead of|will (?:be |show|predict)|due|expected to|to be released',title,re.I)and not re.search(r'exit.poll (?:shows?|predicts?|projects?|forecasts?)',title,re.I):continue
   return label
  if kind=='event':
   question=re.match(r'^\s*(?:Could|Would|Can|Might|May)\b[^?;.!]+\?',title,re.I)
   if question and not sp['COMPLETED'].search(title[question.end():]):continue
   if re.search(r'risk of|could cause|may cause|would cause|potential outage|stress test|simulation',title,re.I)and not re.search(r'outage (?:hits?|hit|causes?|caused)|crashes|crashed',title,re.I):continue
   return label
  residual=normal
  for name in ['FORWARD_ACTION','MODAL_SUBJECT_ACTION','PENDING_POLICY_ACTION','PENDING_FINANCIAL_CLAUSE','FUTURE_RATE_NOUN']:residual=sp[name].sub('',residual)
  direct=residual!=normal
  if re.match(r'^\s*(?:what\s+)?if\b',normal,re.I):residual=residual.replace(re.split(r'[?;.!]',normal,maxsplit=1)[0],'',1);direct=True
  calendar=bool(re.search(r'announc\w*.*(?:webcast|conference call|date|schedule)|sets? (?:the )?date|date for .*results',normal,re.I))
  preview=bool(direct or calendar or sp['EXPLICIT_PREVIEW'].search(normal)or fp['PREVIEW'].search(normal)or sp['ADDITIONAL_FORWARD'].search(normal)or re.search(r'Outlook for|optimism about|before (?:Q[1-4] |quarterly )?(?:earnings|results)|nears? (?:the )?earnings|earnings to (?:reflect|show|test|reveal|shed)|here.s what you need to know|meeting started|(?:earnings|profits?|revenue|sales) (?:seen|expected|forecast) [a-z]+',normal,re.I))
  if label.startswith('China Q2 GDP')and re.search(r'Penfolds|\bMay\b',title,re.I):continue
  if label.startswith('US Q2 GDP')and re.search(r'largest economies|GDP \(PPP\)',title,re.I):continue
  if label.startswith('US June retail sales')and re.search(r'^Porsche reports',title,re.I):continue
  if kind in{'company_result','company_operation'}:
   if re.search(r'McDonald',label,re.I)and re.search(r'Westlife|franchisee|India (?:operator|franchise)',title,re.I):continue
   if re.search(r'Tesla Alphabet',label)and re.search(r'EV Sales|electric.vehicle sales',title,re.I)and not re.search(r'earnings|profits?|EPS|guidance|revenue',title,re.I):continue
   actual=sp['MARKET_CLAUSE'].sub('',residual)
   if sp['FINANCIAL_COMPLETION_HINT'].search(actual)or sp['FINANCIAL_OUTCOME'].search(actual):return label
   if re.search(r'court|lawsuit|appeal|tax',title,re.I)and not re.search(r'earnings|results|profits?|EPS|quarter',title,re.I):continue
   if preview:continue
   return label
  if kind=='policy':
   if sp['POLICY_OUTCOME'].search(residual):return label
   if preview or sp['FORWARD'].search(normal):continue
   return label
  if sp['COMPLETED'].search(sp['MARKET_CLAUSE'].sub('',residual)):return label
  if preview or sp['FORWARD'].search(normal):continue
  return label
 return None
CASES=[
 ('China June Caixin manufacturing PMI expands','2024-06-30','2024-07-01',True),
 ('China June Caixin manufacturing PMI expected to rise','2024-06-30','2024-07-01',False),
 ('US June ISM manufacturing contracts as payrolls could rise','2024-06-30','2024-07-01',True),
 ('US June ISM manufacturing expected to contract','2024-06-30','2024-07-01',False),
 ('US June ISM manufacturing contracts','2024-07-01','2024-07-02',False),
 ('US June payrolls rise, could boost equities','2024-07-04','2024-07-05',True),
 ('US June payrolls expected to rise','2024-07-04','2024-07-05',False),
 ('US June payrolls rise','2024-07-05','2024-07-08',False),
 ('US June consumer prices rise less than expected','2024-07-10','2024-07-11',True),
 ('US June CPI expected to rise less than forecast','2024-07-10','2024-07-11',False),
 ('Japan June consumer prices rose more than expected','2024-07-18','2024-07-19',False),
 ('Japan June consumer prices rose more than expected','2024-07-17','2024-07-18',True),
 ('Tokyo July consumer prices rise','2024-07-25','2024-07-26',False),
 ('Tokyo July consumer prices rise','2024-07-24','2024-07-25',True),
 ('Samsung quarterly preliminary profit jumps','2024-07-04','2024-07-05',False),
 ('UK exit poll projects Labour landslide election win','2024-07-04','2024-07-05',False),
 ('Labour wins UK election and Starmer becomes prime minister','2024-07-04','2024-07-05',True),
 ('Labour wins UK election and Starmer becomes prime minister','2024-07-05','2024-07-08',False),
 ('Global IT outage hits CrowdStrike and Windows systems','2024-07-18','2024-07-19',True),
 ('Could a global IT outage hit CrowdStrike and Windows systems?','2024-07-18','2024-07-19',False),
 ('Global IT outage hits CrowdStrike and Windows systems','2024-07-19','2024-07-22',False),
 ('Biden withdraws from presidential race as Trump could win','2024-07-20','2024-07-22',False),
 ('Biden withdraws from presidential race','2024-07-19','2024-07-22',False),
 ('Biden withdraws from presidential race','2024-07-18','2024-07-19',True),
 ('Biden could withdraw from presidential race','2024-07-18','2024-07-19',False),
 ('Democrats urge Biden to withdraw from presidential race','2024-07-18','2024-07-19',False),
 ('Microsoft quarterly earnings beat estimates','2024-07-29','2024-07-30',True),
 ('Microsoft expected to beat quarterly earnings estimates','2024-07-29','2024-07-30',False),
 ('Microsoft shares rise before earnings','2024-07-29','2024-07-30',False),
 ('TSMC quarterly profit jumps, analysts expect more growth','2024-07-17','2024-07-18',True),
 ('FOMC holds rates at July decision as stocks could rise','2024-07-30','2024-07-31',True),
 ('FOMC expected to hold rates at July decision','2024-07-30','2024-07-31',False),
 ('China July official manufacturing PMI contracts','2024-07-30','2024-07-31',True),
 ('Meta quarterly profits rise','2024-07-30','2024-07-31',True),
]
CASES += [
 ('UK exit poll projects Labour victory; Starmer named prime minister','2024-07-04','2024-07-05',True),
 ('UK exit poll projects Labour victory; Sunak concedes defeat','2024-07-04','2024-07-05',True),
 ('Meta earnings top estimates','2024-07-30','2024-07-31',True),
 ('Meta profit soars as revenue doubles','2024-07-30','2024-07-31',True),
 ('Microsoft Q4 earnings: Azure growth disappoints','2024-07-29','2024-07-30',True),
 ('ASML Q2 earnings top forecasts','2024-07-16','2024-07-17',True),
 ('SK Hynix Q2 quarterly profit beats estimates','2024-07-24','2024-07-25',False),
 ('SK Hynix Q2 quarterly profit beats estimates','2024-07-23','2024-07-24',True),
 ('Poland June industrial output rises','2024-07-17','2024-07-18',True),
 ('Poland June industrial output rises','2024-07-18','2024-07-19',False),
 ('Poland June wages rise','2024-07-17','2024-07-18',True),
 ('Poland June retail sales fall','2024-07-21','2024-07-22',True),
 ('Poland June retail sales fall','2024-07-22','2024-07-23',False),
 ('Poland June unemployment rate falls','2024-07-22','2024-07-23',True),
 ('Poland June unemployment rate falls','2024-07-23','2024-07-24',False),
]
CASES += [
 ('TSMC June monthly revenue soars','2024-07-10','2024-07-11',False),
 ('TSMC June monthly revenue soars','2024-07-09','2024-07-10',True),
 ('TSMC Q2 aggregate revenue rises','2024-07-10','2024-07-11',False),
 ('TSMC Q2 profit rises and raises full-year outlook','2024-07-17','2024-07-18',True),
 ('Australian June CPI rises','2024-07-10','2024-07-11',False),
 ('US shopping trends disappoint retailers','2024-07-10','2024-07-11',False),
 ('Affordable electric cars gain market share','2024-07-23','2024-07-24',False),
 ('Samsung Biologics profit doubles','2024-07-30','2024-07-31',False),
 ('Could global IT outage hit Windows systems? Global IT outage hits CrowdStrike','2024-07-18','2024-07-19',True),
 ('UK exit poll projects Labour victory; Starmer could be named prime minister','2024-07-04','2024-07-05',False),
 ('Can the Fed cut rates at its July decision?','2024-07-30','2024-07-31',False),
 ('Fed cuts rates at July decision, could boost stocks','2024-07-30','2024-07-31',True),
 ('Meta shares surge ahead of quarterly earnings','2024-07-30','2024-07-31',False),
 ('Microsoft announces date for quarterly earnings webcast','2024-07-29','2024-07-30',False),
 ('Tesla shares rise before Q2 earnings','2024-07-22','2024-07-23',False),
]
def main():
 sp,fp,schedule=load();rows=[];fail=[]
 for title,pub,stamp,expected in CASES:
  label=guard(title,pub,stamp,sp,fp,schedule);row={'title':title,'published_date':pub,'report_date':stamp,'expected_excluded':expected,'observed_guard':label,'passed':bool(label)==expected};rows.append(row)
  if not row['passed']:fail.append(row)
 errors=[]
 for event in schedule['guards']:
  if not isinstance(event.get('release_utc'),str):continue
  release=dt.datetime.fromisoformat(event['release_utc']);eligible=dt.datetime.fromisoformat(event['eligible_edition']).replace(tzinfo=dt.timezone.utc)
  if eligible<=release:errors.append(event['label']+': eligible cutoff not strictly after scheduled release')
 result={'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'status':'guard_policy_regressions_only_not_source_acceptance','passed':not fail and not errors,'schedule_sha256':hashlib.sha256((ROOT/'audit_work/july_release_schedule.json').read_bytes()).hexdigest(),'ready_tool_sha256':hashlib.sha256((ROOT/'tools/ready_feeds.py').read_bytes()).hexdigest(),'guard_count':len(schedule['guards']),'regressions':rows,'regression_failures':fail,'eligible_cutoff_math_errors':errors,'scope':'Independent application of declarative timing/regex policy to synthetic actual/preview/mixed-clause and early-local cases; no original publisher-vintage or prose approval.'};(ROOT/'audit_work/independent_july_guard_policy_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'passed':result['passed'],'cases':len(rows),'failures':fail,'cutoff_math_errors':errors},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
