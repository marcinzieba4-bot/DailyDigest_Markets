"""Build the July schedule guard table, without acquiring outcome-based searches."""
import datetime as dt,json,re
from pathlib import Path
R=Path(__file__).resolve().parent.parent
rows=[]
def bound_tokens(pattern):
 for token in ['Fed','FOMC','rates?','policy','decision','cuts?','lowers?','holds?','keeps?','leaves?','hikes?','raises?','wins?','win','resign','majority','victory','US','UK','CPI','PPI','PMI','ISM','ADP','JOLTS','GDP','PCE','EPS','Q2','BOJ','BOE','ECB','RBA','RBNZ','NBP','RPP','LPR','MLF','PBOC','M2']:
  pattern=re.sub(r'(?<![A-Za-z0-9_])'+re.escape(token)+r'(?![A-Za-z0-9_])',lambda m:r'(?<!\w)'+m.group()+r'(?!\w)',pattern)
 return pattern
def add(label,when,pattern,kind='macro',start_days=7,notes=''):
 release=dt.datetime.fromisoformat(when.replace('Z','+00:00'));eligible=release.date()+dt.timedelta(days=1)
 while eligible.weekday()>4:eligible+=dt.timedelta(days=1)
 day_only=(kind=='company_result' or 'Conservative' in notes or 'after July31 midnight' in notes or 'All relevant regional release times' in notes)
 pattern=bound_tokens(pattern)
 if not pattern.startswith('^'):pattern='^'+pattern
 rows.append(dict(label=label,release_utc=None if day_only else release.isoformat(),calendar_release_utc_date=release.date().isoformat(),timing_precision='UTC-day classification only; exact minute unasserted' if day_only else 'scheduled release time',eligible_edition=eligible.isoformat(),earliest_pub_date=(release.date()-dt.timedelta(days=start_days)).isoformat(),pattern=pattern,kind=kind,notes=notes))
add('Japan Q2 Tankan early local','2024-06-30T23:50:00Z',r'(?=.*(?:Japan|Japanese|BOJ|Tankan))(?=.*Tankan)',notes='July1 08:50 JST is before the July1 UTC cutoff; eligible from first edition.')
add('Japan June final manufacturing PMI','2024-07-01T00:30:00Z',r'(?=.*(?:Japan|Japanese))(?=.*(?:manufactur|factory|PMI))(?=.*(?:June|final|PMI))')
add('China June Caixin manufacturing','2024-07-01T01:45:00Z',r'(?=.*(?:China|Chinese|Caixin))(?=.*(?:manufactur|factory|PMI))(?=.*(?:Caixin|private survey))')
add('Poland June manufacturing PMI','2024-07-01T07:00:00Z',r'(?=.*(?:Poland|Polish|Polsk\w*))(?=.*(?:PMI|manufacturing|przemysł\w*))(?=.*(?:June|czerw\w*|PMI))')
add('US June ISM manufacturing','2024-07-01T14:00:00Z',r'(?=.*(?:ISM|Institute for Supply Management))(?=.*manufactur)')
add('Eurozone June CPI flash','2024-07-02T09:00:00Z',r'(?=.*(?:eurozone|euro zone|euro area))(?=.*(?:inflation|CPI|HICP|consumer prices))(?=.*(?:June|flash|preliminary))')
add('RBA June meeting minutes','2024-07-02T01:30:00Z',r'(?=.*(?:RBA|Reserve Bank of Australia))(?=.*minutes)')
add('US May JOLTS release','2024-07-02T14:00:00Z',r'(?=.*(?:US|U\.S\.|JOLTS|American))(?=.*(?:JOLTS|job openings|job vacancies))')
add('Tesla Q2 vehicle deliveries','2024-07-02T13:00:00Z',r'(?=.*(?:Tesla|TSLA))(?=.*(?:deliveries|delivers|delivered))','company_operation',notes='Conservative next-cutoff eligibility; exact pre-open minute does not affect July3 inclusion.')
add('US June ADP employment','2024-07-03T12:15:00Z',r'(?=.*ADP)(?=.*(?:payrolls?|private.sector (?:jobs|employment|hiring)|\bemployment\b|employment report|job (?:growth|gain|loss)))')
add('Japan June final services PMI','2024-07-03T00:30:00Z',r'(?=.*(?:Japan|Japanese))(?=.*(?:service|business activity))(?=.*(?:PMI|June))')
add('China June Caixin services PMI','2024-07-03T01:45:00Z',r'(?=.*(?:China|Chinese|Caixin))(?=.*(?:services|service sector))(?=.*(?:Caixin|private survey))')
add('US June ISM services','2024-07-03T14:00:00Z',r'(?=.*(?:ISM|Institute for Supply Management))(?=.*(?:services|non.manufacturing))')
add('FOMC June meeting minutes','2024-07-03T18:00:00Z',r'(?=.*(?:Fed|FOMC|Federal Reserve))(?=.*minutes)')
add('Poland July RPP decision','2024-07-03T16:00:00Z',r'(?=.*(?:NBP|RPP|Glapi\w*|Polish central bank|Poland.*interest rates|Rada Polityki Pieniężnej))(?=.*(?:\brates?\b|stopy|stóp|stopach|decyzj\w*|polityk\w* pieniężn\w*))','policy',notes='Conservative within-UTC-day bound, exact announcement minute not asserted.')
add('UK settled election result and PM appointment','2024-07-05T09:00:00Z',r'(?=.*(?:Labour|Starmer|Sunak|(?:Britain|British|UK).*(?:election|prime minister|Downing Street)))(?=.*(?:landslide|majority|victory|prime minister|resign|Downing Street|wins?|defeat|conced|sworn in|named|takes office))','uk_settled_result',notes='Conservative UTC-day bound only. July4 exit poll after21UTC is eligible as a projection for July5; settled Friday result/PM appointment is not automatically available at midnight.')
add('US June employment report','2024-07-05T12:30:00Z',r'(?=.*(?:US|U\.S\.|American|payroll|nonfarm|non-farm))(?=.*(?:jobs report|payroll|nonfarm|non-farm|employment report|unemployment rate))')
add('Japan May household spending early local','2024-07-04T23:30:00Z',r'(?=.*(?:Japan|Japanese))(?=.*(?:household spending|household expenditure))',notes='July5 08:30 JST is before July5 UTC midnight.')
add('France parliamentary second-round result','2024-07-07T18:00:00Z',r'(?=.*(?:France|French))(?=.*(?:runoff|run-off|second.round|July 7|7 July|hung parliament|left.wing alliance|leftist alliance))(?=.*(?:election|vote|poll|parliament|victory|wins?|leads?|majority))','politics',notes='Sunday projections published after18UTC may be eligible Monday; first-round June30 outcomes must remain distinguishable.')
add('Japan May wages early local','2024-07-07T23:30:00Z',r'(?=.*(?:Japan|Japanese))(?=.*(?:wages|real pay|labor earnings|labour earnings))',notes='July8 local morning precedes UTC cutoff.')
add('China June CPI PPI','2024-07-10T01:30:00Z',r'(?=.*(?:China|Chinese))(?=.*(?:CPI|PPI|consumer prices|producer prices|consumer inflation|producer inflation|June.*inflation|inflation.*June))')
add('RBNZ July decision','2024-07-10T02:00:00Z',r'(?=.*(?:RBNZ|Reserve Bank of New Zealand|New Zealand central bank))(?=.*(?:rates?|policy|decision|cash rate))','policy')
add('US June CPI','2024-07-11T12:30:00Z',r'(?=.*(?:US|U\.S\.|American?))(?=.*(?:CPI|consumer prices|inflation))(?=.*(?:June|CPI|consumer price))')
add('US June PPI','2024-07-12T12:30:00Z',r'(?=.*(?:US|U\.S\.|American?))(?=.*(?:PPI|producer prices|producer inflation))')
add('China June trade','2024-07-12T03:00:00Z',r'(?=.*(?:China|Chinese))(?=.*(?:exports|imports|trade surplus|trade data))(?=.*(?:June|trade data))',notes='Conservative UTC-day boundary; intra-day minute not used for eligibility.')
add('China June lending and money supply','2024-07-12T08:00:00Z',r'(?=.*(?:China|Chinese|PBOC))(?=.*(?:new loans|yuan loans|bank loans|M2|money supply|total social financing|credit data))',notes='Conservative UTC-day boundary for variable-time release.')
add('Trump Pennsylvania shooting event','2024-07-13T22:11:00Z',r'(?=.*Trump)(?=.*(?:shooting|shot|assassination|gunman|rally attack|ear injury))','politics')
add('China Q2 GDP June activity','2024-07-15T02:00:00Z',r'(?=.*(?:China|Chinese))(?=.*(?:GDP|gross domestic product|retail sales|industrial output|industrial production|fixed.asset|property investment|home prices|house prices))')
add('Republican VP selection and formal nomination','2024-07-15T18:00:00Z',r'(?=.*(?:Trump|Vance|Republican))(?=.*(?:running mate|vice.presiden|VP pick|VP selection|nomination|nominates|nominated))','politics',notes='Does not guard generic earlier campaign reporting; completed selection/formal nomination only.')
add('US June retail sales','2024-07-16T12:30:00Z',r'(?=.*(?:US|U\.S\.|America))(?=.*retail sales)')
add('UK June CPI','2024-07-17T06:00:00Z',r'(?=.*(?:UK|British|Britain))(?=.*(?:inflation|CPI|consumer prices))(?=.*(?:June|CPI|inflation))')
add('US June housing starts','2024-07-17T12:30:00Z',r'(?=.*(?:US|U\.S\.|America))(?=.*(?:housing starts|building permits))')
add('US June industrial output','2024-07-17T13:15:00Z',r'(?=.*(?:US|U\.S\.|America))(?=.*(?:industrial output|industrial production|factory output))')
add('ECB July decision','2024-07-18T12:15:00Z',r'(?=.*(?:ECB|European Central Bank|Lagarde))(?=.*(?:rates?|policy|decision|cuts?|holds?|keeps?|leaves?))','policy')
add('Australia June jobs','2024-07-18T01:30:00Z',r'(?=.*(?:Australia|Australian))(?=.*(?:June|unemployment|jobs (?:report|data|growth|gain)|employment (?:report|data|growth|gain)|labour market|labor market))(?=.*(?:jobs|employment|unemployment|labour|labor))')
add('Japan June national CPI early local','2024-07-18T23:30:00Z',r'^(?!.*Tokyo)(?=.*(?:Japan|Japanese))(?=.*(?:inflation|CPI|consumer prices))(?=.*(?:June|national|nationwide|core))',notes='July19 08:30 JST precedes July19 UTC cutoff.')
add('Global July19 IT outage','2024-07-19T04:00:00Z',r'(?=.*(?:CrowdStrike|Microsoft|Windows|global|worldwide))(?=.*(?:outage|blue screen|BSOD|IT disruption|computer crash))','event',notes='Conservative early UTC-day incident bound; July19 midnight precedes the event.')
add('Biden presidential campaign withdrawal','2024-07-21T17:46:00Z',r'(?=.*Biden)(?=.*(?:withdraw|drop\w* out|drops? out|ends? (?:his )?(?:campaign|reelection|re-election)|quits? (?:the )?race|steps? aside|stands? down|not seek))','biden_withdrawal')
add('China July LPR and short-term policy decision','2024-07-22T01:15:00Z',r'(?=.*(?:China|Chinese|PBOC))(?=.*(?:loan prime|LPR|benchmark lending|reverse repo|short.term (?:rate|borrowing)|seven.day|7.day))','policy')
add('US June existing home sales','2024-07-23T14:00:00Z',r'(?=.*(?:US|U\.S\.|America))(?=.*existing home sales)')
add('July flash PMI Japan','2024-07-24T00:30:00Z',r'(?=.*(?:Japan|Japanese))(?=.*(?:PMI|purchasing managers|business activity))(?=.*(?:July|flash|preliminary))')
add('July flash PMI Europe US','2024-07-24T14:00:00Z',r'(?=.*(?:eurozone|euro zone|Germany|German|France|French|US|U\.S\.))(?=.*(?:PMI|purchasing managers|business activity))(?=.*(?:July|flash|preliminary))',notes='All relevant regional release times fall after the July24 UTC cutoff.')
add('US June new home sales','2024-07-24T14:00:00Z',r'(?=.*(?:US|U\.S\.|America))(?=.*new home sales)')
add('Bank of Canada July decision','2024-07-24T13:45:00Z',r'(?=.*(?:Bank of Canada|Canadian central bank))(?=.*(?:rates?|policy|decision))','policy')
add('China July MLF decision','2024-07-25T01:20:00Z',r'(?=.*(?:China|Chinese|PBOC))(?=.*(?:MLF|medium.term lending|medium.term policy|medium.term (?:interest )?rate))','policy')
add('US Q2 GDP advance','2024-07-25T12:30:00Z',r'(?=.*(?:US|U\.S\.|America))(?=.*(?:GDP|gross domestic product|economic growth))(?=.*(?:Q2|second.quarter|April.June|advance|GDP))')
add('US June durable goods','2024-07-25T12:30:00Z',r'(?=.*(?:US|U\.S\.|America))(?=.*durable goods)')
add('Japan July Tokyo CPI early local','2024-07-25T23:30:00Z',r'(?=.*Tokyo)(?=.*(?:inflation|CPI|consumer prices))(?=.*(?:July|Tokyo))',notes='July26 08:30 JST precedes July26 UTC cutoff.')
add('US June PCE','2024-07-26T12:30:00Z',r'(?=.*(?:US|U\.S\.|American?|Fed|PCE))(?=.*(?:PCE|personal consumption expenditures|preferred.*inflation|inflation.*preferred))')
add('Eurozone Q2 GDP flash','2024-07-30T09:00:00Z',r'(?=.*(?:eurozone|euro zone|euro area))(?=.*(?:GDP|gross domestic product|economic growth))(?=.*(?:Q2|second.quarter|April.June|flash|preliminary))')
add('Germany July CPI flash','2024-07-30T12:00:00Z',r'(?=.*(?:Germany|German))(?=.*(?:inflation|CPI|consumer prices))(?=.*(?:July|flash|preliminary))')
add('China July official PMI','2024-07-31T01:30:00Z',r'(?=.*(?:China|Chinese))(?=.*(?:manufactur|factory|PMI))(?=.*(?:July|official|NBS))')
add('Australia June quarter CPI','2024-07-31T01:30:00Z',r'(?=.*(?:Australia|Australian))(?=.*(?:inflation|CPI|consumer prices))(?=.*(?:June|quarter|Q2|CPI))')
add('Australia June retail sales','2024-07-31T01:30:00Z',r'(?=.*(?:Australia|Australian))(?=.*retail sales)(?=.*June)')
add('BOJ July decision','2024-07-31T03:00:00Z',r'(?=.*(?:BOJ|Bank of Japan|Ueda))(?=.*(?:rates?|policy (?:decision|meeting)|decision|bond buying|bond.buying|hikes?|raises?|cuts?))','policy',notes='Actual announcement is after July31 midnight regardless exact meeting end minute.')
add('FOMC July decision','2024-07-31T18:00:00Z',r'(?=.*(?:Fed|FOMC|Federal Reserve|Powell))(?=.*(?:rates?|policy (?:decision|meeting)|decision|September cut|September easing))','policy')
add('Eurozone July CPI flash','2024-07-31T09:00:00Z',r'(?=.*(?:eurozone|euro zone|euro area))(?=.*(?:inflation|CPI|HICP|consumer prices))(?=.*(?:July|flash|preliminary))')
add('Poland July CPI flash','2024-07-31T08:00:00Z',r'(?=.*(?:Poland|Polish|Polsk\w*|inflacja))(?=.*(?:CPI|inflation|inflacj\w*))(?=.*(?:July|lipc\w*|flash|wstępn\w*))')
# Nearest post-July releases also stay pending in late-July editions when an
# RSS index date predates their actual availability; these are schedule guards.
add('China July Caixin manufacturing pending beyond July','2024-08-01T01:45:00Z',r'(?=.*(?:China|Chinese|Caixin))(?=.*(?:manufactur|factory|PMI))(?=.*(?:Caixin|private survey))')
add('Poland July manufacturing PMI pending beyond July','2024-08-01T07:00:00Z',r'(?=.*(?:Poland|Polish|Polsk\w*))(?=.*(?:PMI|manufacturing|przemysł\w*))(?=.*(?:July|lipc\w*|PMI))')
add('US July ISM manufacturing pending beyond July','2024-08-01T14:00:00Z',r'(?=.*(?:ISM|Institute for Supply Management))(?=.*manufactur)')
add('Bank of England August decision pending beyond July','2024-08-01T11:00:00Z',r'(?=.*(?:Bank of England|BOE|British central bank))(?=.*(?:rates?|policy|cuts?|lowers?|decision))','policy')
add('US July employment report pending beyond July','2024-08-02T12:30:00Z',r'(?=.*(?:US|U\.S\.|American|payroll|nonfarm|non-farm))(?=.*(?:jobs report|payroll|nonfarm|non-farm|employment report|unemployment rate))')
add('TSMC June monthly revenue and Q2 aggregate','2024-07-10T06:00:00Z',r'(?=.*(?:TSMC|Taiwan Semiconductor))(?=.*(?:revenue|sales))','company_operation',notes='Conservative UTC-day bound for monthly revenue disclosure, separate from full July18 earnings.')
add('TSMC Q2 profit and full-year outlook','2024-07-18T06:00:00Z',r'(?=.*(?:TSMC|Taiwan Semiconductor))(?=.*(?:earnings|profit|EPS|guidance|full.year.*(?:forecast|outlook)|raises?.*(?:forecast|outlook)))','company_result',start_days=14)
add('Poland June enterprise wages and employment','2024-07-18T12:00:00Z',r'(?=.*(?:Poland|Polish|Polsk\w*|GUS|wynagrodz\w*))(?=.*(?:wages|wage growth|wynagrodz\w*|zatrudnien\w*))',notes='Conservative UTC-day bound; independent historical GUS July18 calendar lists the June release; exact2024 minute unasserted.')
add('Poland June industry and producer prices','2024-07-18T12:00:00Z',r'(?=.*(?:Poland|Polish|Polsk\w*|GUS|produkcj\w*.*przemysł\w*))(?=.*(?:industrial production|industrial output|producer prices|produkcj\w*.*przemysł\w*|ceny produkcji))',notes='Conservative UTC-day bound from historical GUS release calendar, exact minute unasserted.')
add('Poland June retail sales','2024-07-22T12:00:00Z',r'(?=.*(?:Poland|Polish|Polsk\w*|GUS|sprzedaż.*detalicz))(?=.*(?:retail sales|sprzedaż.*detalicz))',notes='Conservative UTC-day bound from historical GUS July22 release calendar, exact minute unasserted.')
add('Poland June unemployment','2024-07-23T12:00:00Z',r'(?=.*(?:Poland|Polish|Polsk\w*|GUS|bezroboci\w*))(?=.*(?:unemployment|bezroboci\w*))',notes='Conservative UTC-day bound from historical GUS July23 release calendar, exact minute unasserted.')
add('SK hynix Q2 early-local earnings','2024-07-24T23:59:59Z',r'(?=.*(?:SK hynix|SK Hynix))(?=.*(?:earnings|results|revenue|sales|profits?|EPS|guidance|forecasts?))','company_result',start_days=14,notes='Conservative before-midnight UTC bound: dated company invitation says July25 press release before09:00 Seoul. Exact minute unasserted; eligible July25.')
add('Samsung Electronics Q2 full result clock uncertain','2024-07-31T23:59:59Z',r'^(?!.*Samsung Biologics)(?=.*Samsung)(?=.*(?:earnings|results|revenue|sales|profits?|EPS|guidance|forecasts?))','company_result',start_days=14,notes='Conservative omission until Aug1: full-results local date is July31 but original pre00UTC publication clock is not certified. Do not assert that every Korean morning release follows00UTC.')
company_groups=[
 ('Constellation Brands','2024-07-03',r'Constellation Brands|STZ'),
 ('Helen of Troy','2024-07-09',r'Helen of Troy|HELE'),
 ('Delta PepsiCo Conagra','2024-07-11',r'Delta Air Lines|Delta Airlines|PepsiCo|Conagra'),
 ('JPMorgan Citi Wells BNY','2024-07-12',r'JPMorgan|JPM|Citigroup|Citi|Wells Fargo|BNY|Bank of New York'),
 ('Goldman BlackRock','2024-07-15',r'Goldman Sachs|BlackRock'),
 ('BofA Morgan Stanley UnitedHealth Schwab PNC','2024-07-16',r'Bank of America|BofA|Morgan Stanley|UnitedHealth|Charles Schwab|Schwab|PNC'),
 ('ASML Johnson Johnson United Airlines','2024-07-17',r'ASML|Johnson & Johnson|Johnson and Johnson|J&J|United Airlines'),
 ('Netflix TSMC Blackstone Abbott Novartis','2024-07-18',r'Netflix|Blackstone|Abbott|Novartis|Intuitive Surgical|D.R. Horton|D R Horton'),
 ('American Express Halliburton SLB Travelers','2024-07-19',r'American Express|Halliburton|SLB|Schlumberger|Travelers'),
 ('Verizon SAP NXP','2024-07-22',r'Verizon|SAP|NXP'),
 ('Tesla Alphabet GM UPS Visa TI Enphase','2024-07-23',r'Tesla|TSLA|Alphabet|Google|GOOGL|General Motors|GM|(?-i:UPS)|United Parcel|Visa|Texas Instruments|Enphase|Coca.Cola|GE Aerospace|Lockheed Martin|Spotify|Freeport|Comcast'),
 ('Ford Chipotle IBM ServiceNow GEV Edwards','2024-07-24',r'Ford|Chipotle|IBM|ServiceNow|GE Vernova|Edwards Lifesciences|AT&T|NextEra|Deutsche Bank|Santander|KLA'),
 ('Dexcom Deckers Unilever Nestle Honeywell RTX','2024-07-25',r'Dexcom|Deckers|Unilever|Nestle|Nestlé|Honeywell|RTX|Raytheon|AbbVie|Northrop|Southwest Airlines|American Airlines|L3Harris|Skechers|AstraZeneca|Sanofi|Roche|STMicroelectronics|Renault'),
 ('Bristol Myers 3M Colgate Charter','2024-07-26',r'Bristol.Myers|Bristol Myers|(?<![.$0-9])3M|Colgate|Charter Communications|Centene'),
 ('McDonalds ON Philips','2024-07-29',r'McDonald|ON Semiconductor|onsemi|Philips'),
 ('Microsoft AMD Starbucks Pinterest Pfizer Merck P&G','2024-07-30',r'Microsoft|MSFT|AMD|Advanced Micro Devices|Starbucks|SBUX|Pinterest|Pfizer|Merck|Procter|P&G|PayPal|SoFi|JetBlue|BP|Diageo|Arista|First Solar'),
 ('Apple Amazon Intel pending beyond July','2024-08-01',r'Apple|AAPL|Amazon|AMZN|Intel|INTC'),
 ('Meta Qualcomm Arm Boeing Mastercard','2024-07-31',r'Meta|Facebook|Qualcomm|Arm Holdings|Boeing|Mastercard|Humana|Marriott|ADP|T-Mobile|DuPont|Garmin|Carvana|eBay|Allstate|Western Digital|Albemarle'),
]
result_pattern=r'(?=.*\b(?:earnings|results|revenue|sales|profits?|EPS|guidance|forecasts?|bookings)\b)'
for label,date,names in company_groups:add(label+' quarterly outcome',date+'T16:00:00Z',r'(?=.*(?<!\w)(?:'+names+r')(?!\w))'+result_pattern,'company_result',start_days=14,notes='Same-day outcomes are after00UTC; exact intraday/pre-open/after-close minute does not change next-cutoff eligibility.')
add('UK election exit poll projection','2024-07-04T21:00:00Z',r'(?=.*(?:Britain|British|UK|Labour|Starmer|Sunak))(?=.*exit.poll)','exit_poll',notes='A projection is itself a release outcome; no projection before July4 21UTC is admitted as actual.')
REVIEW_DISPOSITIONS=[{'area': 'GUS release dates', 'reviewer': '/root/writer_late', 'status': 'resolved with dated historical calendar/publication evidence; July18 wages/industry, July22 retail, July23 unemployment use next-cutoff eligibility', 'evidence': ['audit_work/release_guard_refs/official_timing_excerpts.json', 'https://stat.gov.pl/kalendarium/18-07-2024.html'], 'limit': 'Exact2024 intraday clock is not asserted; current2026 banner times were rejected as historical proof.'}, {'area': 'Poland RPP clock', 'reviewer': '/root/writer_early (source engineering owner)', 'status': 'conservative owner disposition: keep a July3 UTC-day outcome guard and first eligible edition July4', 'evidence': ['audit_work/july_release_schedule.json', 'audit_work/july_guard_regressions.json'], 'limit': 'No retained primary exact-minute proof; release_utc is null. This is a conservative cutoff bound, not a root review or a certified publisher first-publication clock.'}, {'area': 'Politics projection versus settled result', 'reviewer': '/root/writer_late and /root/recover_context; bounded retained scan by /root/writer_early', 'status': 'fixed-scope mixed-clause negatives and observed retained-headline status scan completed', 'evidence': ['audit_work/release_guard_refs/independent_guard_cases.json', 'audit_work/release_guard_refs/focused_staged_headline_scan.json', 'audit_work/unscheduled_eth_safety_candidates.json'], 'limit': 'UK exit poll remains a projection; Friday appointment and settled result are separately guarded. Original publisher versions are not universally certified.'}, {'area': 'Mixed clauses and earlier company releases', 'reviewer': '/root/writer_late and /root/recover_context; source-owner positive controls', 'status': 'independent fixed-scope actual/preview checks completed; TSMC preliminary/full release split and three observed previews with seven-day news ages implemented', 'evidence': ['audit_work/release_guard_refs/official_timing_excerpts.json', 'audit_work/release_guard_refs/focused_staged_headline_scan.json', 'audit_work/july_guard_regressions.json'], 'limit': 'Finite headline screen; every authored concrete claim still requires own-date timing and meaning review. No root-reviewed status is claimed.'}]
path=R/'audit_work/july_release_schedule.json';path.write_text(json.dumps(dict(version='july-2024-release-schedule-v1',scope='Guard schedule only; not a narrative factual source. Finite conservative screen does not resolve publisher canonical vintages.',guards=rows,pending_root_review=[],review_dispositions=REVIEW_DISPOSITIONS),indent=2,ensure_ascii=False)+'\n');print(len(rows),'July schedule guards saved')
