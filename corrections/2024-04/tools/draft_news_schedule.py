"""Draft verified non-US/non-JP release safety guards; no report facts."""
import datetime as dt,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
rows=[]
def add(label,date,pattern,url,kind='macro',time=None,notes='',lookback=7):
 d=dt.date.fromisoformat(date);eligible=d+dt.timedelta(days=1)
 while eligible.weekday()>4:eligible+=dt.timedelta(days=1)
 rows.append(dict(label=label,release_utc=date+'T'+time+':00+00:00'if time else None,calendar_release_utc_date=date,timing_precision='verified exact historical clock'if time else'conservative UTC-day bound; exact minute unasserted',eligible_edition=eligible.isoformat(),earliest_pub_date=(d-dt.timedelta(days=lookback)).isoformat(),pattern=pattern,kind=kind,evidence=[url],notes=notes))
NBS='https://www.stats.gov.cn/english/PressRelease/ReleaseCalendar/202401/t20240104_1946223.html'
FX='https://forex.z.com/hk/en/forex_trading/economic_calendar/202404.html'
GUS='https://stat.gov.pl/en/release-calendar/04-2024.html'
add('China March Caixin manufacturing PMI','2024-04-01',r'^(?=.*(?:China|Chinese|Caixin))(?=.*(?:manufactur|factory))(?=.*(?:Caixin|private survey))',FX,time='01:45')
add('China March Caixin services PMI','2024-04-03',r'^(?=.*(?:China|Chinese|Caixin))(?=.*(?:services|service sector|non.manufactur))(?=.*(?:Caixin|private survey))',FX,time='01:45')
add('China March CPI PPI','2024-04-11',r'^(?=.*(?:China|Chinese|Caixin))(?=.*(?:\bCPI\b|\bPPI\b|consumer prices|producer prices|inflation|deflation))(?=.*(?:March|Mar\b|2024))',NBS,time='01:30')
add('China March trade','2024-04-12',r'^(?=.*(?:China|Chinese))(?=.*(?:exports|imports|trade surplus|trade data))(?=.*(?:March|Mar\b|2024))','https://www.kaohooninternational.com/economics/538563')
add('China March credit','2024-04-12',r'^(?=.*(?:China|Chinese|PBOC|PBoC))(?=.*(?:new loans|bank loans|yuan loans|credit data|social financing|money supply|M2))(?=.*(?:March|Mar\b|first.quarter|Q1|2024))','https://english.www.gov.cn/archive/statistics/202404/12/content_WS66192b0bc6d0868f4e8e5fc0.html')
add('China March activity and Q1 GDP','2024-04-16',r'^(?=.*(?:China|Chinese))(?=.*(?:\bGDP\b|industrial (?:output|production)|retail sales|fixed.asset|property investment|property sales|unemployment))(?=.*(?:March|Mar\b|first.quarter|Q1|2024))',NBS,time='02:00')
add('China March home prices','2024-04-16',r'^(?=.*(?:China|Chinese))(?=.*(?:home prices|house prices|housing prices))(?=.*(?:March|Mar\b))',NBS,time='01:30')
add('China April MLF decision','2024-04-15',r'^(?=.*(?:China|Chinese|PBOC|PBoC))(?=.*(?:MLF|medium.term lending))',FX,kind='policy')
add('China April LPR decision','2024-04-22',r'^(?=.*(?:China|Chinese|PBOC|PBoC))(?=.*(?:loan prime|LPR))',FX,kind='policy')
add('China March industrial profits','2024-04-27',r'^(?=.*(?:China|Chinese))(?=.*industrial profits)(?=.*(?:March|Mar\b|first.quarter|Q1))',NBS,time='01:30')
add('China April official PMI','2024-04-30',r'^(?=.*(?:China|Chinese|NBS))(?=.*(?:PMI|manufactur|factory|non.manufactur|services activity))(?=.*(?:April|Apr\b))',NBS,time='01:30')
add('RBA March meeting minutes','2024-04-02',r'^(?=.*(?:RBA|Reserve Bank of Australia))(?=.*minutes)','https://www.rba.gov.au/monetary-policy/rba-board-minutes/2024/2024-03-19.html',kind='staged_event',time='00:30')
add('Australia February trade','2024-04-05',r'^(?=.*(?:Australia|Australian))(?=.*(?:trade (?:surplus|balance|data)|exports|imports))(?=.*(?:February|Feb\b))',FX,time='00:30')
add('Australia March labour force','2024-04-18',r'^(?=.*(?:Australia|Australian))(?=.*(?:jobs|employment|unemployment|labour force|labor force))(?=.*(?:March|Mar\b))','https://www.abs.gov.au/statistics/labour/employment-and-unemployment/labour-force-australia/mar-2024',time='01:30')
add('Australia Q1 March inflation','2024-04-24',r'^(?=.*(?:Australia|Australian))(?=.*(?:inflation|CPI|consumer prices))(?=.*(?:March|Mar\b|first.quarter|Q1))','https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/mar-quarter-2024',time='01:30')
add('Australia March retail sales','2024-04-30',r'^(?=.*(?:Australia|Australian))(?=.*retail)(?=.*(?:March|Mar\b))','https://www.abs.gov.au/media-centre/media-releases/consumers-cautious-retail-sales-fall-04',time='01:30')
add('Poland March manufacturing PMI','2024-04-02',r'^(?=.*(?:Poland|Polish|Polsk\w*))(?=.*(?:PMI|manufactur|przemysł\w*))(?=.*(?:March|Mar\b|marc\w*))','https://www.fxstreet.com/analysis/pmis-in-manufacturing-inched-up-in-march-202404020744')
add('Poland April MPC decision','2024-04-04',r'^(?=.*(?:Poland|Polish|NBP|RPP|Glapi\w*|Rada Polityki))(?=.*(?:rates|stóp|stopy|procentow\w*|policy decision))','https://nbp.pl/wp-content/uploads/2024/05/Minutes-RPP-kwiecien-2024-ANG.pdf',kind='policy',notes='Later-published minutes used for meeting identity/date only; no minutes-content facts are author evidence.')
add('Poland March final CPI','2024-04-15',r'^(?=.*(?:Poland|Polish|Polsk\w*|GUS))(?=.*(?:consumer price|inflation|CPI|inflacj\w*))(?=.*(?:March|Mar\b|marc\w*))(?=.*(?:final|confirmed|confirms|potwierdz\w*|ostatecz\w*|GUS))',GUS,lookback=7)
add('Poland March output wages employment','2024-04-22',r'^(?=.*(?:Poland|Polish|Polsk\w*|GUS))(?=.*(?:industrial (?:production|output)|produkcj\w*|producer prices|PPI|wages|salaries|wynagrodz\w*|employment|zatrudn\w*))(?=.*(?:March|Mar\b|marc\w*))',GUS)
add('Poland March retail sales','2024-04-23',r'^(?=.*(?:Poland|Polish|Polsk\w*|GUS))(?=.*(?:retail sales|sprzedaż\w* detalicz\w*))(?=.*(?:March|Mar\b|marc\w*))','https://stat.gov.pl/files/gfx/portalinformacyjny/en/defaultaktualnosci/3285/11/103/1/retail_sales_index__march_2024.pdf')
add('Poland March GUS unemployment','2024-04-24',r'^(?=.*(?:Poland|Polish|Polsk\w*|GUS))(?=.*(?:registered unemployment|bezroboci\w*))(?=.*(?:March|Mar\b|marc\w*))(?=.*(?:GUS|statistics|statistical|urząd))',GUS,notes='Ministry preliminary estimate is a distinct earlier release; this guard targets GUS confirmation only.')
add('Poland April flash CPI','2024-04-30',r'^(?=.*(?:Poland|Polish|Polsk\w*|GUS))(?=.*(?:consumer price|inflation|CPI|inflacj\w*))(?=.*(?:April|Apr\b|kwiet\w*))',GUS)
(ROOT/'audit_work/april_release_schedule_news_part.json').write_text(json.dumps({'month':'2024-04','status':'draft_requires_independent_schedule_and_guard_review','scope':'Safety screen only, never report factual evidence; original publisher vintages not certified.','guards':rows},ensure_ascii=False,indent=2))
for n,key in [('april_named_source_exclusions.json','exclusions'),('april_observed_semantic_dispositions.json','dispositions')]:
 p=ROOT/'audit_work'/n
 if not p.exists():p.write_text(json.dumps({key:[],'status':'draft_requires_own-date_semantic_review'},indent=2))
print('draft guards',len(rows))
