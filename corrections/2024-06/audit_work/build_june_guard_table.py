"""June-only scheduled-release safety table; no factual briefing content."""
import datetime as dt,json,re
from pathlib import Path
R=Path(__file__).resolve().parent.parent
rows=[]
def add(label,when,pattern,kind='macro',start_days=7,ref='june_calendar_web_initial.json',precision='scheduled release time',notes=''):
 release=dt.datetime.fromisoformat(when.replace('Z','+00:00'));eligible=release.date()+dt.timedelta(days=1)
 while eligible.weekday()>4:eligible+=dt.timedelta(days=1)
 rows.append(dict(label=label,release_utc=release.isoformat() if precision=='scheduled release time' else None,calendar_release_utc_date=release.date().isoformat(),timing_precision=precision,eligible_edition=eligible.isoformat(),earliest_pub_date=(release.date()-dt.timedelta(days=start_days)).isoformat(),pattern=pattern if pattern.startswith('^') else '^'+pattern,kind=kind,evidence=['audit_work/'+ref],notes=notes))
US=r'(?=.*(?:\bUS\b|U\.S\.|American|United States))'
JP=r'(?=.*(?:Japan|Japanese|\bBOJ\b))'
CN=r'(?=.*(?:China|Chinese|Caixin|PBOC))'
AU=r'(?=.*(?:Australia|Australian|\bRBA\b))'
EU=r'(?=.*(?:eurozone|euro zone|euro area))'
UK=r'(?=.*(?:\bUK\b|British|Britain))'
PL=r'(?=.*(?:Poland|Polish|Polsk\w*|\bGUS\b))'
add('Japan May final manufacturing PMI','2024-06-03T00:30:00Z',JP+r'(?=.*(?:manufactur|factory|PMI))(?=.*(?:May|final|PMI))')
add('China May Caixin manufacturing PMI','2024-06-03T01:45:00Z',CN+r'(?=.*(?:manufactur|factory|PMI))(?=.*(?:Caixin|private survey))')
add('Poland May manufacturing PMI','2024-06-03T07:00:00Z',PL+r'(?=.*(?:PMI|manufactur|przemysł\w*))',precision='conservative UTC-day bound; exact minute unasserted')
add('US May ISM manufacturing','2024-06-03T14:00:00Z',r'(?=.*(?:\bISM\b|Institute for Supply Management))(?=.*manufactur)')
add('US April JOLTS','2024-06-04T14:00:00Z',r'(?=.*(?:\bUS\b|U\.S\.|JOLTS|American))(?=.*(?:JOLTS|job openings|job vacancies))',ref='june_calendar_web_releases.json')
add('Japan April wages clock unverified','2024-06-05T00:00:00Z',JP+r'(?=.*(?:wages|real pay|labor earnings|labour earnings))',precision='conservative omission: historical pre-midnight clock awaiting independent evidence',notes='Early Japan release may precede local-date UTC midnight. Do not infer all local morning data is after cutoff.')
add('Japan May final services PMI','2024-06-05T00:30:00Z',JP+r'(?=.*(?:services|service sector))(?=.*(?:PMI|May))')
add('Australia Q1 GDP','2024-06-05T01:30:00Z',AU+r'(?=.*(?:GDP|gross domestic product|economic growth))')
add('China May Caixin services PMI','2024-06-05T01:45:00Z',CN+r'(?=.*(?:services|service sector))(?=.*(?:Caixin|private survey))')
add('US May ADP employment','2024-06-05T12:15:00Z',r'(?=.*\bADP\b)(?=.*(?:payroll|private.sector|employment|job growth))')
add('Bank of Canada June decision','2024-06-05T13:45:00Z',r'(?=.*(?:Bank of Canada|Canadian central bank))(?=.*(?:rates?|policy|decision))','policy',ref='june_calendar_web_releases.json')
add('Poland June RPP decision','2024-06-05T16:00:00Z',r'(?=.*(?:\bNBP\b|\bRPP\b|Glapi\w*|Polish central bank|Poland.*interest rates|Rada Polityki Pieniężnej))(?=.*(?:\brates?\b|stopy|stóp|stopach|decyzj\w*|polityk\w* pieniężn\w*))','policy',precision='conservative UTC-day bound; exact minute unasserted')
add('US May ISM services','2024-06-05T14:00:00Z',r'(?=.*(?:\bISM\b|Institute for Supply Management))(?=.*(?:services|non.manufacturing))')
add('ECB June decision','2024-06-06T12:15:00Z',r'(?=.*(?:\bECB\b|European Central Bank|Lagarde))(?=.*(?:rates?|policy|decision|cuts?|holds?|keeps?|leaves?))','policy')
add('US April trade','2024-06-06T12:30:00Z',US+r'(?=.*(?:trade deficit|trade balance|trade data))')
add('Japan April household spending early local','2024-06-06T23:30:00Z',JP+r'(?=.*(?:household spending|household expenditure))',notes='Westpac June calendar states Jun7 09:30 AEST, equivalent to Jun6 23:30UTC; Jun7 edition may use released actual.')
add('China May trade','2024-06-07T03:00:00Z',CN+r'(?=.*(?:exports|imports|trade surplus|trade data))(?=.*(?:May|trade data))',precision='conservative UTC-day bound; exact minute unasserted')
add('US May employment report','2024-06-07T12:30:00Z',r'(?=.*(?:\bUS\b|U\.S\.|American|payroll|nonfarm|non-farm))(?=.*(?:jobs report|payroll|nonfarm|non-farm|employment report|unemployment rate))',ref='june_calendar_web_releases.json')
add('Japan Q1 GDP revision clock unverified','2024-06-10T00:00:00Z',JP+r'(?=.*(?:GDP|gross domestic product|economic growth))',precision='conservative omission: historical pre-midnight clock awaiting independent evidence')
add('UK April employment','2024-06-11T06:00:00Z',UK+r'(?=.*(?:wages|earnings|unemployment|jobs report|employment))')
add('China May CPI PPI','2024-06-12T01:30:00Z',CN+r'(?=.*(?:\bCPI\b|\bPPI\b|consumer prices|producer prices|consumer inflation|producer inflation|May.*inflation|inflation.*May))')
add('UK April monthly GDP','2024-06-12T06:00:00Z',UK+r'(?=.*(?:GDP|economic growth|gross domestic product|monthly output))')
add('US May CPI','2024-06-12T12:30:00Z',US+r'(?=.*(?:\bCPI\b|consumer prices|inflation))(?=.*(?:May|CPI|consumer price))',ref='june_calendar_web_releases.json')
add('FOMC June decision and projections','2024-06-12T18:00:00Z',r'(?=.*(?:\bFed\b|FOMC|Federal Reserve|Powell))(?=.*(?:rates?|policy (?:decision|meeting)|decision|dot.plot|projections|rate.cuts?))','policy')
add('Australia May employment','2024-06-13T01:30:00Z',AU+r'(?=.*(?:jobs|employment|unemployment|labour|labor))(?=.*(?:May|jobs report|jobs data|unemployment|employment data|employment report))')
add('US May PPI','2024-06-13T12:30:00Z',US+r'(?=.*(?:\bPPI\b|producer prices|producer inflation))',ref='june_calendar_web_releases.json')
add('BOJ June decision','2024-06-14T03:23:00Z',r'(?=.*(?:\bBOJ\b|Bank of Japan|Ueda))(?=.*(?:rates?|policy (?:decision|meeting)|decision|bond.buying|bond purchases|taper|hikes?|raises?|cuts?|keeps?|holds?))','policy',ref='june_calendar_web_policy.json',notes='BOJ own search extraction reports statement Jun14 12:23 Japan-local; converts03:23UTC. Jun14 cutoff precedes outcome.')
add('US June preliminary Michigan sentiment','2024-06-14T14:00:00Z',r'(?=.*(?:\bUS\b|U\.S\.|Michigan|American))(?=.*(?:consumer sentiment|Michigan))(?=.*(?:June|preliminary|Michigan))')
add('China May lending and money supply','2024-06-14T08:00:00Z',CN+r'(?=.*(?:new loans|yuan loans|bank loans|\bM2\b|money supply|total social financing|credit data))',precision='conservative UTC-day bound; exact minute unasserted',notes='Variable-time release requires independent June date confirmation.')
add('China May activity and property','2024-06-17T02:00:00Z',CN+r'(?=.*(?:retail sales|industrial output|industrial production|fixed.asset|property investment|home prices|house prices))')
add('China June MLF decision','2024-06-17T01:20:00Z',CN+r'(?=.*(?:\bMLF\b|medium.term lending|medium.term policy))','policy',precision='conservative UTC-day bound; exact minute unasserted')
add('RBA June decision','2024-06-18T04:30:00Z',r'(?=.*(?:\bRBA\b|Reserve Bank of Australia|Australian central bank))(?=.*(?:rates?|policy|decision|cash rate))','policy',ref='june_calendar_web_policy.json')
add('Germany June ZEW','2024-06-18T09:00:00Z',r'(?=.*(?:Germany|German|ZEW))(?=.*\bZEW\b)',precision='conservative UTC-day bound; exact minute unasserted')
add('US May retail sales','2024-06-18T12:30:00Z',US+r'(?=.*retail sales)')
add('US May industrial production','2024-06-18T13:15:00Z',US+r'(?=.*(?:industrial output|industrial production|factory output))')
add('BOJ April meeting minutes clock unverified','2024-06-19T00:00:00Z',r'(?=.*(?:\bBOJ\b|Bank of Japan))(?=.*minutes)',precision='conservative omission: historical pre-midnight clock awaiting independent evidence')
add('UK May CPI','2024-06-19T06:00:00Z',UK+r'(?=.*(?:inflation|\bCPI\b|consumer prices))(?=.*(?:May|CPI|inflation))')
add('China June LPR','2024-06-20T01:15:00Z',CN+r'(?=.*(?:loan prime|\bLPR\b|benchmark lending))','policy',precision='conservative UTC-day bound; exact minute unasserted')
add('Bank of England June decision','2024-06-20T11:00:00Z',r'(?=.*(?:Bank of England|\bBOE\b|British central bank))(?=.*(?:rates?|policy|decision|cuts?|holds?|keeps?|unchanged))','policy',ref='june_calendar_web_policy.json')
add('US May housing starts','2024-06-20T12:30:00Z',US+r'(?=.*(?:housing starts|building permits))')
add('Japan May national CPI early local','2024-06-20T23:30:00Z',r'^(?!.*Tokyo)'+JP+r'(?=.*(?:inflation|\bCPI\b|consumer prices))(?=.*(?:May|national|nationwide|core))',notes='Westpac June21 09:30 AEST convertsJun20 23:30UTC; no blanket report-date block.')
add('Japan June flash PMI','2024-06-21T00:30:00Z',JP+r'(?=.*(?:\bPMI\b|purchasing managers|business activity))(?=.*(?:June|flash|preliminary))',precision='conservative UTC-day bound; exact minute unasserted')
add('UK May retail sales','2024-06-21T06:00:00Z',UK+r'(?=.*retail sales)')
add('Europe US June flash PMIs','2024-06-21T13:45:00Z',r'(?=.*(?:eurozone|euro zone|Germany|German|France|French|\bUS\b|U\.S\.))(?=.*(?:\bPMI\b|purchasing managers|business activity))(?=.*(?:June|flash|preliminary))',precision='all relevant regional releases after this UTC midnight; exact minute unasserted')
add('US May existing home sales','2024-06-21T14:00:00Z',US+r'(?=.*existing home sales)')
add('BOJ June summary of opinions early local','2024-06-23T23:50:00Z',r'(?=.*(?:\bBOJ\b|Bank of Japan))(?=.*summary of opinions)',ref='june_calendar_web_policy.json',notes='BOJ own snippet lists June24 08:50 Japan-local, convertsJun23 23:50UTC.')
add('Germany June Ifo','2024-06-24T08:00:00Z',r'(?=.*(?:Germany|German|Ifo))(?=.*\bIfo\b)')
add('US June consumer confidence','2024-06-25T14:00:00Z',US+r'(?=.*(?:consumer confidence|Conference Board))',precision='conservative UTC-day bound; exact minute unasserted')
add('Australia May monthly CPI','2024-06-26T01:30:00Z',AU+r'(?=.*(?:inflation|\bCPI\b|consumer prices))(?=.*(?:May|monthly))',ref='june_calendar_web_releases.json')
add('US May new home sales','2024-06-26T14:00:00Z',US+r'(?=.*new home sales)',ref='june_calendar_web_releases.json',precision='conservative UTC-day bound; exact minute unasserted')
add('US Q1 GDP third estimate','2024-06-27T12:30:00Z',US+r'(?=.*(?:GDP|gross domestic product|economic growth))(?=.*(?:Q1|first.quarter|January.March|third.estimate|revis))',ref='june_calendar_web_releases.json')
add('US May durable goods','2024-06-27T12:30:00Z',US+r'(?=.*durable goods)',ref='june_calendar_web_releases.json',precision='conservative UTC-day bound; exact minute unasserted')
add('Japan May retail sales clock unverified','2024-06-27T00:00:00Z',JP+r'(?=.*retail sales)',ref='june_calendar_web_releases.json',precision='conservative omission: historical pre-midnight clock awaiting independent evidence')
add('Japan June Tokyo CPI clock unverified','2024-06-28T00:00:00Z',r'(?=.*Tokyo)(?=.*(?:inflation|\bCPI\b|consumer prices))',ref='june_calendar_web_releases.json',precision='conservative omission: historical pre-midnight clock awaiting independent evidence')
add('Japan May industrial output clock unverified','2024-06-28T00:00:00Z',JP+r'(?=.*(?:industrial output|industrial production|factory output))',ref='june_calendar_web_releases.json',precision='conservative omission: historical pre-midnight clock awaiting independent evidence')
add('US May PCE','2024-06-28T12:30:00Z',r'(?=.*(?:\bUS\b|U\.S\.|American|\bFed\b|\bPCE\b))(?=.*(?:\bPCE\b|personal consumption expenditures|preferred.*inflation|inflation.*preferred))',ref='june_calendar_web_releases.json')
add('China June official PMI pending','2024-06-30T01:30:00Z',CN+r'(?=.*(?:manufactur|factory|\bPMI\b))(?=.*(?:June|official|NBS))',ref='june_calendar_web_releases.json',precision='conservative UTC-day bound; exact minute unasserted')
add('US presidential debate completed event','2024-06-28T01:00:00Z',r'(?=.*(?:Trump|Biden|presidential))(?=.*debate)','staged_event',ref='june_event_schedule_evidence.json',notes='A completed debate is unavailableJun28midnight; plans/previews remain eligible. Evidence pending independent review.')
add('Apple WWDC keynote disclosures','2024-06-10T17:00:00Z',r'(?=.*(?:Apple|AAPL|WWDC))(?=.*(?:WWDC|developer conference|Apple Intelligence|iOS 18|Siri|OpenAI|ChatGPT))','staged_event',ref='june_event_schedule_evidence.json',notes='Earlier announcements of conference schedule/plans differ from completed keynote disclosures. Evidence pending independent review.')
add('Nvidia split distribution completed','2024-06-07T20:00:00Z',r'(?=.*(?:Nvidia|NVDA))(?=.*split)','split_distribution',ref='june_event_schedule_evidence.json',notes='Announcement and scheduled split are eligible earlier; completed distribution requires actual stage. Evidence pending independent review.')
add('Nvidia split adjusted trading began','2024-06-10T13:30:00Z',r'(?=.*(?:Nvidia|NVDA))(?=.*split)','split_trading',ref='june_event_schedule_evidence.json',notes='Jun10cutoff precedes regular-session split-adjusted trading. Evidence pending independent review.')
add('Chipotle split distribution completed','2024-06-25T20:00:00Z',r'(?=.*(?:Chipotle|CMG))(?=.*split)','split_distribution',ref='june_event_schedule_evidence.json',notes='Scheduled split and shareholder vote differ from distribution. Evidence pending independent review.')
add('Chipotle split adjusted trading began','2024-06-26T13:30:00Z',r'(?=.*(?:Chipotle|CMG))(?=.*split)','split_trading',ref='june_event_schedule_evidence.json',notes='Jun26cutoff precedes regular-session split-adjusted trading. Evidence pending independent review.')
company=[('GitLab June3','2024-06-03',r'GitLab'),('HPE CrowdStrike','2024-06-04',r'Hewlett Packard Enterprise|\bHPE\b|CrowdStrike'),('Lululemon DollarTree Campbell','2024-06-05',r'Lululemon|Dollar Tree|Campbell Soup|Five Below|Smartsheet'),('Nio DocuSign','2024-06-06',r'\bNio\b|DocuSign'),('GameStop surprise June7 result','2024-06-07',r'GameStop|\bGME\b'),('Oracle June11','2024-06-11',r'Oracle|\bORCL\b'),('Broadcom June12','2024-06-12',r'Broadcom|\bAVGO\b'),('Adobe RH June13','2024-06-13',r'Adobe|\bADBE\b|\bRH\b'),('Lennar June17','2024-06-17',r'Lennar'),('KB Home June18','2024-06-18',r'KB Home'),('Accenture Kroger Darden June20','2024-06-20',r'Accenture|Kroger|Darden|Jabil'),('CarMax June21','2024-06-21',r'CarMax'),('Carnival FedEx June25','2024-06-25',r'Carnival|FedEx'),('Micron GeneralMills Paychex June26','2024-06-26',r'Micron|General Mills|Paychex|Levi Strauss'),('Nike Walgreens McCormick H&M June27','2024-06-27',r'Nike|Walgreens|McCormick|H&M|Hennes.Mauritz')]
for label,day,names in company:
 add(label+' quarterly outcome',day+'T16:00:00Z',r'(?=.*(?<!\w)(?:'+names+r')(?!\w))(?=.*\b(?:earnings|results|revenue|sales|profits?|EPS|guidance|forecasts?|bookings)\b)','company_result',14,ref='june_company_calendar_evidence.json',precision='conservative UTC-day bound; exact minute unasserted',notes='Dated historical issuer schedule/result evidence pending independent review; no precise announcement minute asserted.')
# June-only independently researched clock refinements. These rows identify
# evidence precision, and never assert that a mutable article vintage is certified.
refinements={
 'Japan April wages clock unverified':('2024-06-04T23:30:00+00:00','Japan April wages early local','provenance_calendar_final_clock_check.json','Dated MHLW release Jun5 plus contemporaneous Monex 08:30JST calendar; timing corroboration, not original article certification.'),
 'Japan Q1 GDP revision clock unverified':('2024-06-09T23:50:00+00:00','Japan Q1 GDP revision early local','provenance_calendar_japan_clocks.json','Historical ESRI/eStat release Jun10 08:50JST, beforeJun10 UTC cutoff.'),
 'BOJ April meeting minutes clock unverified':('2024-06-18T23:50:00+00:00','BOJ April meeting minutes early local','provenance_calendar_japan_schedule_search.json','BOJ historical release schedule Jun19 08:50JST; minutes are distinct from Jun14 decision.'),
 'Japan June Tokyo CPI clock unverified':('2024-06-27T23:30:00+00:00','Japan June Tokyo CPI early local','provenance_calendar_japan_date_clock.json','HistoricalJun28date plus official08:30JST CPI rule; publication clock corroborated by dated calendar.'),
 'Japan May industrial output clock unverified':('2024-06-27T23:50:00+00:00','Japan May industrial output early local','provenance_calendar_japan_clocks.json','Historical METI Jun28 08:50JST, beforeJun28cutoff.'),
}
for row in rows:
 if row['label'] in refinements:
  clock,label,ref,note=refinements[row['label']];release=dt.datetime.fromisoformat(clock)
  row.update(label=label,release_utc=clock,calendar_release_utc_date=release.date().isoformat(),eligible_edition=(release.date()+dt.timedelta(days=1)).isoformat(),earliest_pub_date=(release.date()-dt.timedelta(days=7)).isoformat(),timing_precision='historical date and exact clock, evidence types stated in notes',evidence=['audit_work/'+ref],notes=note)
 if row['kind'] in {'staged_event','split_distribution','split_trading'}:row['evidence']=['audit_work/june_event_schedule_evidence.json'];row['notes']=row['notes'].replace('Evidence pending independent review.','Primary issuer/broadcaster schedule retained; independent implementation review still required.')
 if row['kind']=='company_result':row['notes']='Dated historical issuer/SEC release retained in June company calendar evidence; conservative next-cutoff eligibility. Exact announcement minute unasserted.'
for row in rows:
 if row['kind']=='split_distribution':row.update(release_utc=None,timing_precision='scheduled after-close distribution stage; exact execution minute unasserted',notes=row['notes']+' No claim of execution exactly20:00UTC.')
add('Chipotle shareholder split approval','2024-06-06T16:00:00Z',r'(?=.*(?:Chipotle|CMG))(?=.*(?:shareholder|annual meeting))(?=.*(?:approv|authoriz|vote))','staged_event',ref='june_event_schedule_evidence.json',precision='dated primary UTC-day bound; exact historical vote minute unasserted',notes='June6 shareholder authorization is distinct from June25 distribution and June26 trading.')
add('Japan May unemployment early local','2024-06-27T23:30:00Z',JP+r'(?=.*(?:unemployment|jobless|job.to.applicant|jobs.to.applicants))',ref='provenance_calendar_historic_exact.json',notes='Historical eStat2024-06-28 08:30JST metadata; actual available beforeJun28 UTC cutoff.')
for label,day,pattern in [
 ('Poland May wages and enterprise employment','20',r'(?=.*(?:Poland|Polish|Polsk\w*|GUS|wynagrodz\w*|zatrudnien\w*))(?=.*(?:wages|wage growth|wynagrodz\w*|zatrudnien\w*))'),
 ('Poland May industry and producer prices','20',r'(?=.*(?:Poland|Polish|Polsk\w*|GUS|produkcj\w*.*przemysł\w*|ceny produkcji))(?=.*(?:industrial production|industrial output|producer prices|produkcj\w*.*przemysł\w*|ceny produkcji))'),
 ('Poland May retail sales','24',r'(?=.*(?:Poland|Polish|Polsk\w*|GUS|sprzedaż.*detalicz))(?=.*(?:retail sales|sprzedaż.*detalicz))'),
 ('Poland May unemployment','25',r'(?=.*(?:Poland|Polish|Polsk\w*|GUS|bezroboci\w*))(?=.*(?:unemployment|bezroboci\w*))'),
 ('Poland June flash CPI','28',r'(?=.*(?:Poland|Polish|Polsk\w*|inflacja))(?=.*(?:inflation|CPI|inflacj\w*))(?=.*(?:June|czerw\w*|flash|wstępn\w*))')]:
 add(label,'2024-06-'+day+'T12:00:00Z',pattern,ref='provenance_calendar_gus_exact_dates.json',precision='dated primary UTC-day bound; exact historical minute unasserted')
# Nearest pending releases after the last June edition also remain pending.
add('China June Caixin manufacturing pending July1','2024-07-01T01:45:00Z',CN+r'(?=.*(?:manufactur|factory|PMI))(?=.*(?:Caixin|private survey))',ref='june_pending_calendar_evidence.json')
add('Poland June PMI pending July1','2024-07-01T07:00:00Z',PL+r'(?=.*(?:PMI|manufactur|przemysł\w*))',ref='june_pending_calendar_evidence.json',precision='dated calendar day-only bound; exact minute unasserted')
add('US June ISM manufacturing pending July1','2024-07-01T14:00:00Z',r'(?=.*(?:\bISM\b|Institute for Supply Management))(?=.*manufactur)',ref='june_pending_calendar_evidence.json')
add('Eurozone June flash inflation pending July2','2024-07-02T09:00:00Z',EU+r'(?=.*(?:inflation|CPI|HICP|consumer prices))(?=.*(?:June|flash|preliminary))',ref='june_pending_calendar_evidence.json',precision='dated calendar day-only bound; exact minute unasserted')
add('US May JOLTS pending July2','2024-07-02T14:00:00Z',r'(?=.*(?:\bUS\b|U\.S\.|JOLTS|American))(?=.*(?:JOLTS|job openings|job vacancies))',ref='june_pending_calendar_evidence.json')
add('FOMC June meeting minutes pending July3','2024-07-03T18:00:00Z',r'(?=.*(?:\bFed\b|FOMC|Federal Reserve))(?=.*minutes)',ref='june_pending_calendar_evidence.json')
add('US June employment report pending July5','2024-07-05T12:30:00Z',r'(?=.*(?:\bUS\b|U\.S\.|American|payroll|nonfarm|non-farm))(?=.*(?:jobs report|payroll|nonfarm|non-farm|employment report|unemployment rate))',ref='june_pending_calendar_evidence.json')
for row in rows:
 if row['label']=='Poland May wages and enterprise employment':row['pattern']=r'^(?!.*(?:minimum wage|minimaln\w*.*(?:wynagrodz\w*|płac\w*)|(?:wynagrodz\w*|płac\w*).*minimaln\w*))'+row['pattern'].removeprefix('^')
 if row['label']=='ECB June decision':row['pattern']=r'^(?!.*bank interest rate statistics)'+row['pattern'].removeprefix('^')
payload={'month':'2024-06','status':'draft_requires_independent_schedule_and_guard_review','scope':'Safety screen only, never author factual evidence. No original publisher vintage certified. Unknown early-local clocks conservatively omitted pending evidence.','guards':rows,'review_required':['Primary early-local Japan clocks','Poland GUS/RPP June release dates','Company actual result calendar including surprise GameStop release','WWDC/debate/split stage chronology','Observed staged-headline screen and preview/actual regressions']}
(R/'audit_work/june_release_schedule.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
print(len(rows),'June draft guards')
