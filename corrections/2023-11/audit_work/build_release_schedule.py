"""Build the November 2023 release-timing safety screen (not writer evidence).

Each guard names a scheduled release / known event, its UTC release clock where
known, the first weekday edition whose 00:00 UTC cutoff follows it, and a headline
pattern. A matching outcome headline dated earlier than the release is excluded
from editions before eligibility. Unknown clocks use the next-day edition.
"""
import json, datetime as dt
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
D = lambda s: dt.date.fromisoformat(s)
def next_edition(day):
    d = D(day) + dt.timedelta(days=1)
    while d.weekday() > 4: d += dt.timedelta(days=1)
    return d.isoformat()
def earliest(eligible, days):
    return (D(eligible) - dt.timedelta(days=days)).isoformat()
US = r'(?:\bUS\b|U\.S\.|United States|American|America\'s|America’s)'
NOT_FOREIGN = r'^(?!.*(?:China|Chinese|Japan|Japanese|Tokyo|Australia|Australian|Poland|Polish|eurozone|euro zone|Germany|German|Canada|Canadian|\bUK\b|British|Britain|India|Turkey|Argentin))'
G = []
def g(label, release_utc, kind, pattern, evidence, eligible=None, lookback=7, notes=''):
    rel_date = release_utc[:10]
    clock = len(release_utc) > 10
    eligible = eligible or (next_edition(rel_date) if clock else next_edition(rel_date))
    G.append(dict(label=label, release_utc=(release_utc + ':00+00:00') if clock else None,
                  calendar_release_utc_date=rel_date,
                  timing_precision='verified scheduled local clock converted to UTC' if clock else 'release date known; clock not asserted, next weekday edition used',
                  eligible_edition=eligible, earliest_pub_date=earliest(eligible, lookback), pattern=pattern, kind=kind,
                  evidence=evidence, notes=notes))
BLS = ['https://www.bls.gov/schedule/2023/11_sched_list.htm']
CEN = ['https://www.census.gov/economic-indicators/calendar-listview.html']
BEA = ['https://www.bea.gov/news/schedule']
FED = ['https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm']
# --- United States
g('US October ADP employment', '2023-11-01T12:15', 'macro', r'^(?=.*(?:\bADP\b))(?=.*(?:jobs|payrolls|employment|hiring|private))', ['https://adpemploymentreport.com'])
g('US Treasury November refunding', '2023-11-01T12:30', 'macro', r'^(?=.*(?:Treasury|Yellen))(?=.*(?:refunding|auction sizes|coupon auctions|long-dated debt sales))', ['https://home.treasury.gov/news/press-releases'], notes='Refunding statement 08:30 ET; pending sizing previews remain eligible.')
g('US September JOLTS', '2023-11-01T14:00', 'macro', r'^(?=.*(?:\bUS\b|U\.S\.|United States|American|JOLTS))(?=.*(?:JOLTS|job openings|job vacancies))', BLS)
g('US October ISM manufacturing', '2023-11-01T14:00', 'macro', NOT_FOREIGN + r'(?=.*(?:\bISM\b|Institute for Supply Management))(?=.*(?:manufactur|factory|factories))', ['https://www.ismworld.org'])
g('FOMC November decision', '2023-11-01T18:00', 'policy', r'^(?=.*(?:\bFed\b|FOMC|Federal Reserve|Powell))(?=.*(?:rates|rate|policy|decision|hold|pause))', FED)
g('US October payrolls', '2023-11-03T12:30', 'macro', r'^(?=.*(?:\bUS\b|U\.S\.|United States|American|nonfarm|payroll))(?=.*(?:payroll|jobs report|employment report|unemployment rate|job growth|hiring slow))', BLS, notes='Preview language remains pending; unrelated country employment not guarded.')
g('US October ISM services', '2023-11-03T14:00', 'macro', NOT_FOREIGN + r'(?=.*(?:\bISM\b|Institute for Supply Management))(?=.*(?:services|service sector|non.?manufactur))', ['https://www.ismworld.org'])
g('US September trade balance', '2023-11-07T13:30', 'macro', r'^(?=.*' + US + r')(?=.*(?:trade deficit|trade gap|trade balance))', CEN)
g('US November preliminary UMich sentiment', '2023-11-10T15:00', 'macro', r'^(?=.*(?:University of Michigan|UMich|Michigan))(?=.*(?:sentiment|inflation expectations|consumer))', ['https://www.sca.isr.umich.edu'])
g('US October CPI', '2023-11-14T13:30', 'macro', NOT_FOREIGN + r'(?=.*(?:\bCPI\b|consumer prices|consumer inflation|inflation report|inflation data|core inflation))(?=.*(?:October|Oct\b|cool|eases|slows|unchanged|flat|rises|rose|surprise|softer|lower))', BLS, notes='Requires October or outcome wording to avoid guarding generic pending inflation commentary.')
g('US October PPI', '2023-11-15T13:30', 'macro', NOT_FOREIGN + r'(?=.*(?:\bPPI\b|producer prices|producer inflation|wholesale prices))', BLS)
g('US October retail sales', '2023-11-15T13:30', 'macro', r'^(?=.*' + US + r'|.*Commerce Department)(?=.*retail sales)(?!.*(?:China|Chinese|Japan|Australia|Poland|Polish|UK|British|eurozone))', CEN)
g('US October import prices', '2023-11-16T13:30', 'macro', r'^(?=.*' + US + r')(?=.*(?:import prices|export prices))', BLS)
g('US October industrial production', '2023-11-16T14:15', 'macro', r'^(?=.*' + US + r'|.*Federal Reserve)(?=.*(?:industrial production|industrial output|factory output|manufacturing output))(?!.*(?:China|Chinese|Japan|Poland|Polish|German|UK))', ['https://www.federalreserve.gov/releases/g17/'])
g('US October housing starts', '2023-11-17T13:30', 'macro', r'^(?=.*' + US + r'|.*homebuilding)(?=.*(?:housing starts|building permits|homebuilding|groundbreaking))', CEN)
g('US October existing home sales', '2023-11-21T15:00', 'macro', r'^(?=.*(?:\bUS\b|U\.S\.|National Association of Realtors|\bNAR\b|existing))(?=.*(?:existing.home sales|home resales|existing home))', ['https://www.nar.realtor'])
g('FOMC October/November meeting minutes', '2023-11-21T19:00', 'staged_event', r'^(?=.*(?:\bFed\b|FOMC|Federal Reserve))(?=.*minutes)', FED)
g('US October durable goods', '2023-11-22T13:30', 'macro', r'^(?=.*' + US + r'|.*durable)(?=.*(?:durable goods|durable-goods|capital goods orders|business equipment orders))', CEN)
g('US November final UMich sentiment', '2023-11-22T15:00', 'macro', r'^(?=.*(?:University of Michigan|UMich|Michigan))(?=.*(?:sentiment|inflation expectations|consumer))(?=.*(?:final|November|Nov\b))', ['https://www.sca.isr.umich.edu'], eligible='2023-11-23', lookback=1, notes='Lookback limited to avoid duplicating the preliminary-release guard.')
g('US October new home sales', '2023-11-27T15:00', 'macro', r'^(?=.*' + US + r'|.*new home)(?=.*(?:new home sales|new-home sales|sales of new))', CEN)
g('US November Conference Board confidence', '2023-11-28T15:00', 'macro', r'^(?=.*(?:Conference Board|consumer confidence))(?=.*(?:\bUS\b|U\.S\.|American|Conference Board|November))(?!.*(?:China|Japan|Australia|German|UK|Poland|eurozone))', ['https://www.conference-board.org'])
g('US third-quarter GDP second estimate', '2023-11-29T13:30', 'macro', r'^(?=.*' + US + r'|.*economy grew)(?=.*(?:GDP|gross domestic product|economic growth|economy grew))(?=.*(?:third.quarter|Q3|revised|revision|second estimate|5\.2))(?!.*(?:China|Chinese|Japan|Japanese|Poland|Polish|euro|German|UK|British|India|Canada))', BEA)
g('Fed November Beige Book', '2023-11-29T19:00', 'staged_event', r'^(?=.*(?:Beige Book))', FED)
g('US October PCE and spending', '2023-11-30T13:30', 'macro', r'^(?=.*(?:\bUS\b|U\.S\.|United States|American|\bPCE\b))(?=.*(?:\bPCE\b|personal consumption|personal income|consumer spending))', BEA)
g('Moody\'s US sovereign outlook change', '2023-11-10T22:00', 'macro', r'^(?=.*Moody)(?=.*(?:\bUS\b|U\.S\.|United States|America|Treasury|sovereign))(?=.*(?:outlook|negative|downgrad|cuts?|lowers?|revis))', ['https://ratings.moodys.com'], notes='Announcement after US close Friday; eligible Monday 2023-11-13.')
g('US stopgap funding passage', '2023-11-14T23:00', 'macro', r'^(?=.*(?:stopgap|continuing resolution|funding bill|spending bill|shutdown))(?=.*(?:House|Senate|Congress|Biden|lawmakers))(?=.*(?:passes|passed|approves|approved|averts|averted|clears|cleared|signs|signed|avoids|avoided))', ['https://clerk.house.gov/Votes'], notes='House vote evening ET 14 Nov; Senate late 15 Nov ET; pending vote language remains eligible.')
# --- Europe / UK
g('BoE November decision', '2023-11-02T12:00', 'policy', r'^(?=.*(?:Bank of England|\bBoE\b|BOE|Bailey))(?=.*(?:rates|rate|policy|decision|hold|keeps))', ['https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes'])
g('UK third-quarter GDP', '2023-11-10T07:00', 'macro', r'^(?=.*(?:\bUK\b|Britain|British|U\.K\.))(?=.*(?:GDP|economy|economic growth|recession))(?=.*(?:third.quarter|Q3|September|stagnat|flatlin|avoid|zero growth))', ['https://www.ons.gov.uk/releasecalendar'])
g('Eurozone Q3 GDP second flash', '2023-11-14T10:00', 'macro', r'^(?=.*(?:euro zone|eurozone|euro area|Eurostat))(?=.*(?:GDP|economy|contract|growth))(?=.*(?:third.quarter|Q3|second estimate|confirmed|flash))', ['https://ec.europa.eu/eurostat/news/release-calendar'])
g('Germany November ZEW', '2023-11-14T10:00', 'macro', r'^(?=.*(?:\bZEW\b))', ['https://www.zew.de'])
g('UK October CPI', '2023-11-15T07:00', 'macro', r'^(?=.*(?:\bUK\b|Britain|British|U\.K\.))(?=.*(?:inflation|CPI|consumer prices))(?=.*(?:October|Oct\b|falls|fell|slows|eases|cools|drops|lowest|4\.6|halv))', ['https://www.ons.gov.uk/releasecalendar'])
g('UK Autumn Statement', '2023-11-22T12:30', 'staged_event', r'^(?=.*(?:Autumn Statement|Hunt))(?=.*(?:tax|national insurance|budget|statement|cuts?|unveil|announce))', ['https://www.gov.uk/government/topical-events/autumn-statement-2023'])
g('Eurozone November flash PMI', '2023-11-23T09:00', 'macro', r'^(?=.*(?:euro zone|eurozone|euro area|German|Germany|France|French|HCOB))(?=.*(?:PMI|business activity|purchasing managers))(?=.*(?:November|Nov\b|flash))', ['https://www.pmi.spglobal.com/Public/Release/ReleaseDates'])
g('Germany November Ifo', '2023-11-24T09:00', 'macro', r'^(?=.*(?:\bIfo\b))(?=.*(?:German|Germany|business|sentiment|climate|index|morale))', ['https://www.ifo.de/en/survey/ifo-business-climate-germany'])
g('Germany November flash CPI', '2023-11-29T13:00', 'macro', r'^(?=.*(?:German|Germany))(?=.*(?:inflation|CPI|consumer prices))(?=.*(?:November|Nov\b))', ['https://www.destatis.de/EN/Service/Release-Calendar/'])
g('Eurozone November flash CPI', '2023-11-30T10:00', 'macro', r'^(?=.*(?:euro zone|eurozone|euro area|Eurostat|bloc))(?=.*(?:inflation|HICP|consumer prices))(?=.*(?:November|Nov\b|flash))', ['https://ec.europa.eu/eurostat/news/release-calendar'])
# --- China
g('China October Caixin manufacturing PMI', '2023-11-01T01:45', 'macro', r'^(?=.*(?:China|Chinese|Caixin))(?=.*(?:manufactur|factory))(?=.*(?:Caixin|private survey))', ['https://www.pmi.spglobal.com/Public/Release/ReleaseDates'])
g('China October Caixin services PMI', '2023-11-03T01:45', 'macro', r'^(?=.*(?:China|Chinese|Caixin))(?=.*(?:services|service sector|non.manufactur))(?=.*(?:Caixin|private survey))', ['https://www.pmi.spglobal.com/Public/Release/ReleaseDates'])
g('China October trade', '2023-11-07T03:00', 'macro', r'^(?=.*(?:China|Chinese))(?=.*(?:exports|imports|trade surplus|trade data|shipments))(?=.*(?:October|Oct\b|unexpectedly|contract|shrink|rebound|beat|miss))', ['http://english.customs.gov.cn'])
g('China October CPI PPI', '2023-11-09T01:30', 'macro', r'^(?=.*(?:China|Chinese))(?=.*(?:\bCPI\b|\bPPI\b|consumer prices|producer prices|inflation|deflation))(?=.*(?:October|Oct\b|deflation|slips|falls|fell|returns))', ['https://www.stats.gov.cn/english/'])
g('China October credit', '2023-11-13', 'macro', r'^(?=.*(?:China|Chinese|PBOC|PBoC))(?=.*(?:new loans|bank loans|yuan loans|credit data|social financing|money supply|\bM2\b|lending))(?=.*(?:October|Oct\b|slump|plunge|fall|fell|drop|rise|beat|miss))', ['http://www.pbc.gov.cn/en/3688247/index.html'], notes='Credit data clock unscheduled; next weekday edition after release date used.')
g('China November MLF', '2023-11-15T01:20', 'policy', r'^(?=.*(?:China|Chinese|PBOC|PBoC|central bank))(?=.*(?:MLF|medium.term lending))', ['http://www.pbc.gov.cn/en/3688247/index.html'])
g('China October activity data', '2023-11-15T02:00', 'macro', r'^(?=.*(?:China|Chinese))(?=.*(?:industrial (?:output|production)|retail sales|fixed.asset|property investment|property sales|urban unemployment|jobless rate))(?=.*(?:October|Oct\b|beat|miss|slow|accelerat|quicken|tops|faster))', ['https://www.stats.gov.cn/english/'])
g('China October home prices', '2023-11-16T01:30', 'macro', r'^(?=.*(?:China|Chinese))(?=.*(?:home prices|house prices|housing prices|new home))(?=.*(?:October|Oct\b|fastest|steepest|fall|fell|decline|drop))', ['https://www.stats.gov.cn/english/'])
g('China November LPR', '2023-11-20T01:15', 'policy', r'^(?=.*(?:China|Chinese|PBOC|PBoC))(?=.*(?:loan prime|\bLPR\b|benchmark lending))', ['http://www.pbc.gov.cn/en/3688247/index.html'])
g('China October industrial profits', '2023-11-27T01:30', 'macro', r'^(?=.*(?:China|Chinese))(?=.*industrial profits)', ['https://www.stats.gov.cn/english/'])
g('China November official PMI', '2023-11-30T01:30', 'macro', r'^(?=.*(?:China|Chinese|NBS))(?=.*(?:PMI|manufactur|factory|non.manufactur|services activity))(?=.*(?:November|Nov\b))', ['https://www.stats.gov.cn/english/'])
g('Biden Xi meeting', '2023-11-15T19:00', 'staged_event', r'^(?=.*(?:Biden))(?=.*(?:\bXi\b))(?=.*(?:\bmet\b|agreed|agree to|agreement|handshake|dictator|military (?:talks|communication|ties)|fentanyl|after (?:meeting|summit|talks)|takeaways|outcome|resum))', ['https://www.whitehouse.gov/briefing-room/'], notes='Woodside meeting afternoon PT 15 Nov; previews remain eligible.')
# --- Japan
g('Japan government stimulus package approval', '2023-11-02T08:00', 'macro', r'^(?=.*(?:Japan|Japanese|Kishida))(?=.*(?:stimulus|economic package|economic measures|relief package|tax cut))(?=.*(?:approve|approved|adopt|adopted|unveil|unveiled|compiles?|compiled|announces?|announced))', ['https://japan.kantei.go.jp'])
g('Japan September wages and household spending', '2023-11-06T23:30', 'macro', r'^(?=.*(?:Japan|Japanese))(?=.*(?:real wages|wages|household spending))(?=.*(?:September|Sept|Sep\b|18th|fall|fell|drop|decline))', ['https://www.stat.go.jp/english/'])
g('Japan Q3 preliminary GDP', '2023-11-14T23:50', 'macro', r'^(?=.*(?:Japan|Japanese))(?=.*(?:GDP|economy|economic growth|contract|shrink))(?=.*(?:third.quarter|Q3|July.September|shrinks|shrank|contracts|contracted|annualised|annualized))', ['https://www.esri.cao.go.jp/en/sna/sokuhou/sokuhou_top.html'])
g('Japan October trade', '2023-11-15T23:50', 'macro', r'^(?=.*(?:Japan|Japanese))(?=.*(?:exports|imports|trade (?:deficit|surplus|balance)))(?=.*(?:October|Oct\b))', ['https://www.customs.go.jp/toukei/info/index_e.htm'])
g('Japan October national CPI', '2023-11-23T23:30', 'macro', r'^(?=.*(?:Japan|Japanese))(?=.*(?:CPI|consumer prices|consumer inflation|core inflation))(?=.*(?:October|Oct\b|national))', ['https://www.stat.go.jp/english/'])
g('Japan November Tokyo CPI', '2023-11-23T23:30', 'macro', r'^(?=.*(?:Tokyo|Japan.s capital|Japan’s capital))(?=.*(?:CPI|inflation|consumer prices))', ['https://www.stat.go.jp/english/'])
g('Japan November flash PMI', '2023-11-24T00:30', 'macro', r'^(?=.*(?:Japan|Japanese|au Jibun))(?=.*(?:PMI|purchasing managers|factory activity))(?=.*(?:November|Nov\b|flash))', ['https://www.pmi.spglobal.com/Public/Release/ReleaseDates'])
g('Japan October industrial production and retail sales', '2023-11-29T23:50', 'macro', r'^(?=.*(?:Japan|Japanese))(?=.*(?:industrial (?:output|production)|factory output|retail sales))(?=.*(?:October|Oct\b))', ['https://www.meti.go.jp/english/statistics/'])
# --- Australia / NZ
g('Australia September trade', '2023-11-02T00:30', 'macro', r'^(?=.*(?:Australia|Australian))(?=.*(?:trade (?:surplus|balance|data)|exports|imports))(?=.*(?:September|Sept|Sep\b))', ['https://www.abs.gov.au/release-calendar'])
g('RBA November decision', '2023-11-07T03:30', 'policy', r'^(?=.*(?:RBA|Reserve Bank of Australia|Bullock|Australia.s central bank|Australian central bank))(?=.*(?:rates|rate|policy|decision|hike|hikes|raises|lifts))', ['https://www.rba.gov.au/schedules-events/calendar.html'])
g('RBA November Statement on Monetary Policy', '2023-11-10T00:30', 'staged_event', r'^(?=.*(?:RBA|Reserve Bank of Australia))(?=.*(?:Statement on Monetary Policy|\bSoMP\b|forecasts? (?:upgrade|raise|lift)|inflation forecast))', ['https://www.rba.gov.au/schedules-events/calendar.html'])
g('Australia October labour force', '2023-11-16T00:30', 'macro', r'^(?=.*(?:Australia|Australian))(?=.*(?:jobs|employment|unemployment|labour force|labor force))(?=.*(?:October|Oct\b))', ['https://www.abs.gov.au/release-calendar'])
g('RBA November meeting minutes', '2023-11-21T00:30', 'staged_event', r'^(?=.*(?:RBA|Reserve Bank of Australia))(?=.*minutes)', ['https://www.rba.gov.au/schedules-events/calendar.html'])
g('Australia October retail sales', '2023-11-28T00:30', 'macro', r'^(?=.*(?:Australia|Australian))(?=.*retail)(?=.*(?:October|Oct\b))', ['https://www.abs.gov.au/release-calendar'])
g('Australia October monthly CPI', '2023-11-29T00:30', 'macro', r'^(?=.*(?:Australia|Australian))(?=.*(?:inflation|CPI|consumer prices))(?=.*(?:October|Oct\b|monthly))', ['https://www.abs.gov.au/release-calendar'])
g('RBNZ November decision', '2023-11-29T01:00', 'policy', r'^(?=.*(?:RBNZ|Reserve Bank of New Zealand|New Zealand.s central bank|\bOrr\b))(?=.*(?:rates|rate|OCR|policy|decision|hold|hike))', ['https://www.rbnz.govt.nz/monetary-policy'])
# --- Poland
g('Poland October manufacturing PMI', '2023-11-02T08:00', 'macro', r'^(?=.*(?:Poland|Polish|Polsk\w*|PMI w Polsce|PMI dla Polski))(?=.*(?:PMI|manufactur|przemysł\w*))(?=.*(?:October|Oct\b|październik\w*))', ['https://www.pmi.spglobal.com/Public/Release/ReleaseDates'])
g('Poland November MPC decision', '2023-11-08', 'policy', r'^(?=.*(?:Poland|Polish|NBP|RPP|Glapi\w*|Rada Polityki))(?=.*(?:rates|stóp|stopy|procentow\w*|policy decision|decyzj\w*))', ['https://nbp.pl/en/monetary-policy/mpc-meetings-schedule/'], notes='Decision clock not asserted; eligible 9 November.')
g('NBP governor November press conference', '2023-11-09T14:00', 'staged_event', r'^(?=.*(?:Glapi\w*))(?=.*(?:konferencj\w*|press conference|said|says|powiedział|stwierdził|zapowiedział|ocenił))', ['https://nbp.pl'], notes='Governor press conference the day after the decision.')
g('Poland Q3 flash GDP', '2023-11-14T09:00', 'macro', r'^(?=.*(?:Poland|Polish|Polsk\w*|GUS))(?=.*(?:GDP|PKB|economy|gospodark\w*))(?=.*(?:third.quarter|Q3|III kw\w*|trzecim kwartale|flash|szybki szacunek))', ['https://stat.gov.pl/en/release-calendar/'])
g('Poland October final CPI', '2023-11-15T09:00', 'macro', r'^(?=.*(?:Poland|Polish|Polsk\w*|GUS))(?=.*(?:consumer price|inflation|CPI|inflacj\w*))(?=.*(?:October|Oct\b|październik\w*))(?=.*(?:final|confirmed|confirms|potwierdz\w*|ostateczn\w*|6\.6))', ['https://stat.gov.pl/en/release-calendar/'])
g('Poland October output wages employment', '2023-11-20T09:00', 'macro', r'^(?=.*(?:Poland|Polish|Polsk\w*|GUS))(?=.*(?:industrial (?:production|output)|produkcj\w*|producer prices|\bPPI\b|wages|salaries|wynagrodz\w*|employment|zatrudnieni\w*))(?=.*(?:October|Oct\b|październik\w*))', ['https://stat.gov.pl/en/release-calendar/'])
g('Poland October retail sales', '2023-11-22T09:00', 'macro', r'^(?=.*(?:Poland|Polish|Polsk\w*|GUS))(?=.*(?:retail sales|sprzedaż\w* detalicz\w*))(?=.*(?:October|Oct\b|październik\w*))', ['https://stat.gov.pl/en/release-calendar/'])
g('Poland October registered unemployment', '2023-11-24T09:00', 'macro', r'^(?=.*(?:Poland|Polish|Polsk\w*|GUS))(?=.*(?:registered unemployment|bezroboci\w*))(?=.*(?:October|Oct\b|październik\w*))', ['https://stat.gov.pl/en/release-calendar/'])
g('Poland November flash CPI', '2023-11-30T09:00', 'macro', r'^(?=.*(?:Poland|Polish|Polsk\w*|GUS))(?=.*(?:consumer price|inflation|CPI|inflacj\w*))(?=.*(?:November|Nov\b|listopad\w*))', ['https://stat.gov.pl/en/release-calendar/'])
g('Duda designates Morawiecki', '2023-11-06T19:00', 'staged_event', r'^(?=.*(?:Duda|prezydent|president))(?=.*(?:Morawiecki|premier))(?=.*(?:misj\w*|mission|task|tasks|nominat\w*|desygn\w*|powierz\w*|asks|picks|chooses|first chance|first shot))', ['https://www.prezydent.pl'], notes='Presidential address evening CET 6 Nov; previews remain eligible.')
g('Sejm first sitting and Marshal election', '2023-11-13T13:00', 'staged_event', r'^(?=.*(?:Sejm|Hołownia|Holownia|marszał\w*))(?=.*(?:elected|wybran\w*|first sitting|pierwsze posiedzeni\w*|inauguracyjn\w*|sworn|ślubowa\w*))(?!.*(?:Johnson|House|Congress))', ['https://www.sejm.gov.pl'])
g('Morawiecki cabinet sworn in', '2023-11-27T10:00', 'staged_event', r'^(?=.*(?:Morawiecki|rząd|government|cabinet))(?=.*(?:sworn|zaprzysi\w*|appoint\w*|powoła\w*|new cabinet|nowy rząd|nowego rządu))(?=.*(?:Duda|prezydent|president|Morawiecki))', ['https://www.prezydent.pl'])
# --- Corporate results (clock not asserted; first weekday edition after reporting day)
def result(name, day, pat):
    g(name + ' quarterly result', day, 'company_result', r'^(?=.*(?:' + pat + r'))(?=.*(?:earnings|results|quarter|profit|EPS|guidance|outlook|revenue|sales|forecast))', ['company investor-relations release calendar'], lookback=15)
for name, day, pat in [
    ('Qualcomm', '2023-11-01', 'Qualcomm'), ('PayPal', '2023-11-01', 'PayPal'), ('CVS Health', '2023-11-01', r'\bCVS\b'),
    ('DoorDash', '2023-11-01', 'DoorDash'), ('Toyota', '2023-11-01', 'Toyota'),
    ('Apple', '2023-11-02', r'Apple\b|\bAAPL\b'), ('Starbucks', '2023-11-02', 'Starbucks'), ('Eli Lilly', '2023-11-02', r'Eli Lilly|\bLilly\b'),
    ('Novo Nordisk', '2023-11-02', 'Novo Nordisk|Novo\b'), ('Moderna', '2023-11-02', 'Moderna'), ('Shopify', '2023-11-02', 'Shopify'),
    ('Coinbase', '2023-11-02', 'Coinbase'), ('Airbnb', '2023-11-02', 'Airbnb'), ('Block', '2023-11-02', r'Block Inc|\bBlock\b.{0,20}(?:Square|Cash App)|Square'),
    ('ConocoPhillips', '2023-11-02', 'ConocoPhillips'), ('Cloudflare', '2023-11-02', 'Cloudflare'), ('DraftKings', '2023-11-02', 'DraftKings'),
    ('Uber', '2023-11-07', r'\bUber\b'), ('Robinhood', '2023-11-07', 'Robinhood'), ('Rivian', '2023-11-07', 'Rivian'), ('Lucid', '2023-11-07', r'\bLucid\b'),
    ('Datadog', '2023-11-07', 'Datadog'), ('PKO Bank Polski', '2023-11-07', r'PKO BP|PKO Bank|PKO Banku'),
    ('Arm Holdings', '2023-11-08', r'\bArm\b.{0,25}(?:Holdings|chip|shares|stock)|Arm Holdings'), ('Walt Disney', '2023-11-08', 'Disney'),
    ('Warner Bros Discovery', '2023-11-08', 'Warner Bros'), ('SoftBank', '2023-11-09', 'SoftBank'), ('Plug Power', '2023-11-09', 'Plug Power'),
    ('Home Depot', '2023-11-14', 'Home Depot'), ('Target', '2023-11-15', r'\bTarget(?:\'s|’s)?\s+(?:Corp|stock|shares|earnings|results|quarterly|third.quarter|Q3|profit|sales|comparable|beats?|miss)|retailer Target|\bTGT\b'), ('Tencent', '2023-11-15', 'Tencent'),
    ('JD.com', '2023-11-15', r'JD\.com|\bJD\b'), ('Cisco', '2023-11-15', r'\bCisco\b'), ('Palo Alto Networks', '2023-11-15', 'Palo Alto'),
    ('Walmart', '2023-11-16', 'Walmart'), ('Alibaba', '2023-11-16', 'Alibaba'), ('Applied Materials', '2023-11-16', 'Applied Materials'),
    ('KGHM', '2023-11-16', 'KGHM'), ('Zoom', '2023-11-20', r'Zoom Video|\bZoom\b(?=.{0,30}(?:shares|stock|earnings|results))|\bZM\b'),
    ('Nvidia', '2023-11-21', r'Nvidia|\bNVDA\b'), ('Lowe\'s', '2023-11-21', r'\bLowe\'?s\b|\bLowe’s\b'), ('Best Buy', '2023-11-21', 'Best Buy'),
    ('Baidu', '2023-11-21', 'Baidu'), ('Deere', '2023-11-22', r'\bDeere\b|John Deere'), ('PDD Holdings', '2023-11-28', r'\bPDD\b|Pinduoduo|Temu'),
    ('CrowdStrike', '2023-11-28', 'CrowdStrike'), ('Salesforce', '2023-11-29', 'Salesforce'), ('Snowflake', '2023-11-29', 'Snowflake'),
    ('CD Projekt', '2023-11-29', r'CD Projekt|CDR\b'), ('Dell', '2023-11-30', r'\bDell\b'), ('Marvell', '2023-11-30', 'Marvell')]:
    result(name, day, pat)
# --- Staged / known events (outcome headlines cannot predate the event)
g('Bankman-Fried trial verdict', '2023-11-02T23:30', 'staged_event', r'^(?=.*(?:Bankman.Fried|\bSBF\b))(?=.*(?:guilty|convicted|verdict|jury))', ['https://www.justice.gov/usao-sdny'])
g('WeWork bankruptcy filing', '2023-11-07T03:00', 'macro', r'^(?=.*WeWork)(?=.*(?:files|filed|filing|bankruptcy|Chapter 11))', ['https://www.kccllc.net/wework'], notes='Filing late 6 Nov ET; plan-to-file reports remain eligible.')
g('Republican third presidential debate', '2023-11-09T01:00', 'staged_event', r'^(?=.*(?:Republican|GOP))(?=.*debate)', ['https://gop.com'])
g('OpenAI board removes Altman', '2023-11-17T20:30', 'macro', r'^(?=.*(?:Altman|OpenAI))(?=.*(?:fired|fires|ousted|ousts|out as|removed|removes|pushed out|exit|departure|steps down|leadership transition|board))(?=.*(?:Altman|CEO|chief executive))', ['https://openai.com/blog/openai-announces-leadership-transition'])
g('Altman joins Microsoft', '2023-11-20T08:00', 'macro', r'^(?=.*(?:Altman|Brockman))(?=.*Microsoft)(?=.*(?:join|joins|joined|hire|hires|hired|to lead|new AI|research team))', ['https://blogs.microsoft.com'])
g('Altman reinstated at OpenAI', '2023-11-22T06:00', 'macro', r'^(?=.*(?:Altman))(?=.*(?:return|returns|returned|reinstated|back as|back at|comeback|agreement in principle|new board))', ['https://openai.com/blog'])
g('Argentina presidential runoff result', '2023-11-19T23:30', 'staged_event', r'^(?=.*(?:Argentin|Milei|Massa))(?=.*(?:\bwins\b|\bwon\b|elected|victory|president.elect|concede|landslide|defeats?|beats?))', ['https://www.argentina.gob.ar/dine'])
g('Israel Hamas truce agreement', '2023-11-21T23:00', 'macro', r'^(?=.*(?:Israel|Israeli|Hamas|Gaza))(?=.*(?:truce|ceasefire|cease-fire|pause|hostage deal|hostages deal))(?=.*(?:agree|agreed|agreement|approves|approved|deal reached|strike deal|strikes deal|announce))', ['https://www.gov.il/en'], notes='Cabinet approval late 21 Nov UTC; negotiation reports remain eligible if pending.')
g('Gaza truce begins and hostages freed', '2023-11-24T05:00', 'macro', r'^(?=.*(?:Israel|Israeli|Hamas|Gaza|hostages?))(?=.*(?:truce|ceasefire|pause|hostages?))(?=.*(?:begins|began|takes effect|took effect|holds|freed|released|first group|exchange))', ['https://www.gov.il/en'], lookback=2, notes='Short lookback avoids earlier October hostage releases.')
g('OPEC+ meeting postponement', '2023-11-22T13:00', 'macro', r'^(?=.*(?:OPEC))(?=.*(?:postpone|postpones|postponed|delay|delays|delayed|pushed back))', ['https://www.opec.org'])
g('Binance DOJ plea agreement', '2023-11-21T19:00', 'macro', r'^(?=.*(?:Binance|Changpeng Zhao|\bCZ\b))(?=.*(?:pleads?|pleaded|guilty|steps down|resigns?|\$4\.3|4\.3 billion|admits))', ['https://www.justice.gov/opa'], notes='Settlement-talk reports remain eligible; guilty plea/step-down wording guarded.')
G.sort(key=lambda x: (x['eligible_edition'], x['label']))
out = {'month': '2023-11', 'status': 'pre-authoring safety screen', 'scope': 'Safety screen only; compact historical release clocks, not writer factual evidence.', 'guards': G}
(ROOT / 'audit_work' / 'nov2023_release_schedule.json').write_text(json.dumps(out, indent=1, ensure_ascii=False))
print(len(G), 'guards')
