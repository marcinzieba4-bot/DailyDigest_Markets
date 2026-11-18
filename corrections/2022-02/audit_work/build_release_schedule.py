"""Build the February 2022 release-timing safety screen (not writer evidence).

Each guard names a scheduled release / known event, its UTC release clock where
known, the first weekday edition whose 00:00 UTC cutoff follows it, and a headline
pattern. A matching outcome headline dated earlier than the release is excluded
from editions before eligibility. Unknown clocks use the next-day edition.
February 2022 clocks: US EST (UTC-5), CET (UTC+1), UK GMT, JST (UTC+9), CST (UTC+8), AEDT (UTC+11).
RSS index stamps are day-granular; US-evening events after 00:00 UTC (the 24 February
invasion, Super Bowl night, the Truth Social launch, 00:30 UTC Australian releases)
therefore receive explicit clocks so a previous-day stamp cannot admit them early.
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
NOT_FOREIGN = r'^(?!.*(?:China|Chinese|Japan|Japanese|Tokyo|Australia|Australian|Poland|Polish|eurozone|euro zone|Germany|German|Canada|Canadian|\bUK\b|British|Britain|India|Turkey|Russia|Russian|Brazil|Mexico))'
RUS = r'(?:Russia|Russian|Putin|Kremlin|Moscow)'
G = []
def g(label, release_utc, kind, pattern, evidence, eligible=None, lookback=7, notes=''):
    rel_date = release_utc[:10]
    clock = len(release_utc) > 10
    eligible = eligible or next_edition(rel_date)
    G.append(dict(label=label, release_utc=(release_utc + ':00+00:00') if clock else None,
                  calendar_release_utc_date=rel_date,
                  timing_precision='verified scheduled local clock converted to UTC' if clock else 'release date known; clock not asserted, next weekday edition used',
                  eligible_edition=eligible, earliest_pub_date=earliest(eligible, lookback), pattern=pattern, kind=kind,
                  evidence=evidence, notes=notes))
BLS = ['https://www.bls.gov/schedule/2022/02_sched_list.htm']
CEN = ['https://www.census.gov/economic-indicators/calendar-listview.html']
BEA = ['https://www.bea.gov/news/schedule']
FED = ['https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm']
ISM = ['https://www.ismworld.org']
# --- United States (08:30 ET = 13:30 UTC; 10:00 ET = 15:00 UTC)
g('US December JOLTS', '2022-02-01T15:00', 'macro', r'^(?=.*(?:\bUS\b|U\.S\.|United States|American|JOLTS))(?=.*(?:JOLTS|job openings|job vacancies))', BLS)
g('US January ISM manufacturing', '2022-02-01T15:00', 'macro', NOT_FOREIGN + r'(?=.*(?:\bISM\b|Institute for Supply Management))(?=.*(?:manufactur|factory|factories))', ISM)
g('US January ADP employment', '2022-02-02T13:15', 'macro', r'^(?=.*(?:\bADP\b))(?=.*(?:jobs|payrolls|employment|hiring|private))', ['https://adpemploymentreport.com'])
g('US Treasury February refunding', '2022-02-02T13:30', 'macro', r'^(?=.*(?:Treasury|Yellen))(?=.*(?:refunding|auction sizes|coupon auctions))', ['https://home.treasury.gov/news/press-releases'], notes='Refunding statement 08:30 ET; pending sizing previews remain eligible.')
g('US January ISM services', '2022-02-03T15:00', 'macro', NOT_FOREIGN + r'(?=.*(?:\bISM\b|Institute for Supply Management))(?=.*(?:services|service sector|non.?manufactur))', ISM)
g('US January payrolls', '2022-02-04T13:30', 'macro', r'^(?=.*(?:\bUS\b|U\.S\.|United States|American|nonfarm|payroll))(?=.*(?:payroll|jobs report|employment report|unemployment rate|job growth|hiring|added \d|jobs in January))(?!.*(?:ADP|private payrolls|private employers))', BLS, notes='ADP private-payroll headlines are a separate 2 February release.')
g('US December trade balance', '2022-02-08T13:30', 'macro', r'^(?=.*' + US + r')(?=.*(?:trade deficit|trade gap|trade balance))', CEN)
g('US January CPI', '2022-02-10T13:30', 'macro', NOT_FOREIGN + r'(?=.*(?:\bCPI\b|consumer prices|consumer inflation|inflation report|inflation data|core inflation|inflation (?:rate|hits|jumps|soars|rises|rose|accelerates)))(?=.*(?:January|Jan\b|7\.5|40.year|four.decade|highest since 1982|1982))', BLS, notes='Requires January or outcome wording; December CPI (12 January) is outside the guard lookback.')
g('US February preliminary UMich sentiment', '2022-02-11T15:00', 'macro', r'^(?=.*(?:University of Michigan|UMich|Michigan))(?=.*(?:sentiment|inflation expectations|consumer))', ['https://www.sca.isr.umich.edu'])
g('US January PPI', '2022-02-15T13:30', 'macro', NOT_FOREIGN + r'(?=.*(?:\bPPI\b|producer prices|producer inflation|wholesale prices|wholesale inflation))', BLS)
g('US January retail sales', '2022-02-16T13:30', 'macro', r'^(?=.*' + US + r'|.*Commerce Department)(?=.*retail sales)(?!.*(?:China|Chinese|Japan|Australia|Poland|Polish|UK|British|eurozone))', CEN)
g('US January import prices', '2022-02-16T13:30', 'macro', r'^(?=.*' + US + r')(?=.*(?:import prices|export prices))', BLS)
g('US January industrial production', '2022-02-16T14:15', 'macro', r'^(?=.*' + US + r'|.*Federal Reserve)(?=.*(?:industrial production|industrial output|factory output|manufacturing output))(?!.*(?:China|Chinese|Japan|Poland|Polish|German|UK))', ['https://www.federalreserve.gov/releases/g17/'])
g('FOMC January meeting minutes', '2022-02-16T19:00', 'staged_event', r'^(?=.*(?:\bFed\b|FOMC|Federal Reserve))(?=.*minutes)', FED)
g('US January housing starts', '2022-02-17T13:30', 'macro', r'^(?=.*' + US + r'|.*homebuilding)(?=.*(?:housing starts|building permits|homebuilding|groundbreaking))', CEN)
g('US January existing home sales', '2022-02-18T15:00', 'macro', r'^(?=.*(?:\bUS\b|U\.S\.|National Association of Realtors|\bNAR\b|existing))(?=.*(?:existing.home sales|home resales|existing home))', ['https://www.nar.realtor'])
g('US February Conference Board confidence', '2022-02-22T15:00', 'macro', r'^(?=.*(?:Conference Board|consumer confidence))(?=.*(?:\bUS\b|U\.S\.|American|Conference Board|February))(?!.*(?:China|Japan|Australia|German|UK|Poland|eurozone))', ['https://www.conference-board.org'])
g('US January new home sales', '2022-02-24T15:00', 'macro', r'^(?=.*' + US + r'|.*new home)(?=.*(?:new home sales|new-home sales|sales of new))', CEN)
g('US fourth-quarter GDP second estimate', '2022-02-24T13:30', 'macro', r'^(?=.*' + US + r'|.*economy grew)(?=.*(?:GDP|gross domestic product|economic growth|economy grew))(?=.*(?:fourth.quarter|Q4|revised|revision|second estimate|7\.0|7%))(?!.*(?:China|Chinese|Japan|Japanese|Poland|Polish|euro|German|UK|British|India|Canada))', BEA, notes='The advance estimate (27 January) is outside the guard lookback.')
g('US January PCE and spending', '2022-02-25T13:30', 'macro', r'^(?=.*(?:\bUS\b|U\.S\.|United States|American|\bPCE\b))(?=.*(?:\bPCE\b|personal consumption|personal income|consumer spending))', BEA)
g('US January durable goods', '2022-02-25T13:30', 'macro', r'^(?=.*' + US + r'|.*durable)(?=.*(?:durable goods|durable-goods|capital goods orders|business equipment orders))', CEN)
g('US February final UMich sentiment', '2022-02-25T15:00', 'macro', r'^(?=.*(?:University of Michigan|UMich|Michigan))(?=.*(?:sentiment|inflation expectations|consumer))(?=.*(?:final|February|Feb\b))', ['https://www.sca.isr.umich.edu'], lookback=1, notes='Lookback limited to avoid duplicating the preliminary-release guard.')
# --- Europe / UK
g('Eurozone January flash CPI', '2022-02-02T10:00', 'macro', r'^(?=.*(?:euro zone|eurozone|euro area|Eurostat|bloc))(?=.*(?:inflation|HICP|consumer prices))(?=.*(?:January|Jan\b|flash|record|5\.1))', ['https://ec.europa.eu/eurostat/news/release-calendar'])
g('BoE February decision', '2022-02-03T12:00', 'policy', r'^(?=.*(?:Bank of England|\bBoE\b|BOE|Bailey))(?=.*(?:rates|rate|policy|decision|hike|hikes|raises|0\.5))', ['https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes'])
g('ECB February decision', '2022-02-03T12:45', 'policy', r'^(?=.*(?:\bECB\b|European Central Bank|Lagarde))(?=.*(?:rates|rate|policy|decision|hold|holds|keeps|hike|hawkish|press conference|rules? out|door))', ['https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html'], notes='Decision 13:45 CET, press conference 14:30 CET.')
g('UK fourth-quarter GDP', '2022-02-11T07:00', 'macro', r'^(?=.*(?:\bUK\b|Britain|British|U\.K\.))(?=.*(?:GDP|economy|economic growth))(?=.*(?:fourth.quarter|Q4|December|2021|shrank|shrinks|contract|Omicron))', ['https://www.ons.gov.uk/releasecalendar'])
g('Eurozone Q4 GDP second estimate', '2022-02-15T10:00', 'macro', r'^(?=.*(?:euro zone|eurozone|euro area|Eurostat))(?=.*(?:GDP|economy|growth))(?=.*(?:fourth.quarter|Q4|second estimate|confirmed))', ['https://ec.europa.eu/eurostat/news/release-calendar'])
g('Germany February ZEW', '2022-02-15T10:00', 'macro', r'^(?=.*(?:\bZEW\b))', ['https://www.zew.de'])
g('UK January CPI', '2022-02-16T07:00', 'macro', r'^(?=.*(?:\bUK\b|Britain|British|U\.K\.))(?=.*(?:inflation|CPI|consumer prices))(?=.*(?:January|Jan\b|5\.5|30.year|highest since 1992|1992))', ['https://www.ons.gov.uk/releasecalendar'])
g('UK January retail sales', '2022-02-18T07:00', 'macro', r'^(?=.*(?:\bUK\b|Britain|British|U\.K\.))(?=.*retail sales)', ['https://www.ons.gov.uk/releasecalendar'])
g('Eurozone February flash PMI', '2022-02-21T09:00', 'macro', r'^(?=.*(?:euro zone|eurozone|euro area|German|Germany|France|French|IHS Markit))(?=.*(?:PMI|business activity|purchasing managers))(?=.*(?:February|Feb\b|flash))', ['https://www.markiteconomics.com/Public/Release/ReleaseDates'])
g('Germany February Ifo', '2022-02-21T09:00', 'macro', r'^(?=.*(?:\bIfo\b))(?=.*(?:German|Germany|business|sentiment|climate|index|morale))', ['https://www.ifo.de/en/survey/ifo-business-climate-germany'])
g('Eurozone January final CPI', '2022-02-23T10:00', 'macro', r'^(?=.*(?:euro zone|eurozone|euro area|Eurostat))(?=.*(?:inflation|HICP|consumer prices))(?=.*(?:final|confirmed|confirms|January))', ['https://ec.europa.eu/eurostat/news/release-calendar'], lookback=4, notes='Short lookback avoids the 2 February flash estimate.')
# --- China (09:30 CST = 01:30 UTC)
g('China January Caixin services PMI', '2022-02-07T01:45', 'macro', r'^(?=.*(?:China|Chinese|Caixin))(?=.*(?:services|service sector|non.manufactur))(?=.*(?:Caixin|private survey))', ['https://www.markiteconomics.com/Public/Release/ReleaseDates'], notes='Delayed by the Lunar New Year holiday.')
g('China January FX reserves', '2022-02-07T08:00', 'macro', r'^(?=.*(?:China|Chinese))(?=.*(?:foreign exchange reserves|forex reserves|FX reserves|gold reserves))', ['http://www.safe.gov.cn/en/'])
g('China January credit', '2022-02-10', 'macro', r'^(?=.*(?:China|Chinese|PBOC|PBoC))(?=.*(?:new loans|bank loans|yuan loans|credit data|social financing|money supply|\bM2\b|lending))(?=.*(?:January|Jan\b|record|surge|jump|beat|rebound))', ['http://www.pbc.gov.cn/en/3688247/index.html'], notes='Credit data clock unscheduled; next-day edition used.')
g('China February MLF', '2022-02-15T01:20', 'policy', r'^(?=.*(?:China|Chinese|PBOC|PBoC|central bank))(?=.*(?:MLF|medium.term lending))', ['http://www.pbc.gov.cn/en/3688247/index.html'])
g('China January CPI PPI', '2022-02-16T01:30', 'macro', r'^(?=.*(?:China|Chinese))(?=.*(?:\bCPI\b|\bPPI\b|consumer prices|producer prices|inflation|factory.gate))(?=.*(?:January|Jan\b|slows|cools|eases|lowest|slowest))', ['https://www.stats.gov.cn/english/'])
g('China January home prices', '2022-02-16T01:30', 'macro', r'^(?=.*(?:China|Chinese))(?=.*(?:home prices|house prices|housing prices|new home))(?=.*(?:January|Jan\b|fall|fell|decline|drop|fifth))', ['https://www.stats.gov.cn/english/'])
g('China February LPR', '2022-02-21T01:15', 'policy', r'^(?=.*(?:China|Chinese|PBOC|PBoC))(?=.*(?:loan prime|\bLPR\b|benchmark lending))', ['http://www.pbc.gov.cn/en/3688247/index.html'])
g('China February official PMI', '2022-02-28T01:30', 'macro', r'^(?=.*(?:China|Chinese|NBS))(?=.*(?:PMI|manufactur|factory|non.manufactur|services activity))(?=.*(?:February|Feb\b))', ['https://www.stats.gov.cn/english/'], eligible='2022-03-01')
g('Putin Xi joint statement', '2022-02-04T08:00', 'staged_event', r'^(?=.*(?:\bXi\b|Putin|China|Russia|Beijing|Moscow))(?=.*(?:joint statement|no limits|no-limits|\blimitless\b|declar\w* (?:a |new )?(?:partnership|friendship)|(?:Xi|Putin) (?:met|meet\w* in Beijing)|met in Beijing|back each other|oppose NATO expansion|against NATO expansion))', ['http://en.kremlin.ru/events/president/news/67828'], notes='Beijing meeting before the Olympic opening; pending-meeting previews remain eligible.')
# --- Japan (08:30 JST = 23:30 UTC previous day; 08:50 JST = 23:50 UTC)
g('Japan December wages and household spending', '2022-02-07T23:30', 'macro', r'^(?=.*(?:Japan|Japanese))(?=.*(?:real wages|wages|household spending))(?=.*(?:December|Dec\b|2021))', ['https://www.stat.go.jp/english/'])
g('BOJ fixed-rate purchase offer', '2022-02-10T04:00', 'policy', r'^(?=.*(?:\bBOJ\b|BoJ|Bank of Japan))(?=.*(?:fixed.rate|unlimited|0\.25%|0\.25 percent))(?=.*(?:offer|offers|buy|buys|purchase|operation|bond))', ['https://www.boj.or.jp/en/announcements/release_2022/index.htm'], notes='Announcement during Tokyo trading on 10 February.')
g('Japan Q4 preliminary GDP', '2022-02-14T23:50', 'macro', r'^(?=.*(?:Japan|Japanese))(?=.*(?:GDP|economy|economic growth|rebound))(?=.*(?:fourth.quarter|Q4|October.December|rebounds|rebounded|grew|annualised|annualized))', ['https://www.esri.cao.go.jp/en/sna/sokuhou/sokuhou_top.html'])
g('Japan January trade', '2022-02-16T23:50', 'macro', r'^(?=.*(?:Japan|Japanese))(?=.*(?:exports|imports|trade (?:deficit|surplus|balance)))(?=.*(?:January|Jan\b))', ['https://www.customs.go.jp/toukei/info/index_e.htm'])
g('Japan January national CPI', '2022-02-17T23:30', 'macro', r'^(?=.*(?:Japan|Japanese))(?=.*(?:CPI|consumer prices|consumer inflation|core inflation))(?=.*(?:January|Jan\b|national))', ['https://www.stat.go.jp/english/'])
g('Japan February flash PMI', '2022-02-21T00:30', 'macro', r'^(?=.*(?:Japan|Japanese|au Jibun))(?=.*(?:PMI|purchasing managers|factory activity))(?=.*(?:February|Feb\b|flash))', ['https://www.markiteconomics.com/Public/Release/ReleaseDates'])
g('Japan February Tokyo CPI', '2022-02-24T23:30', 'macro', r'^(?=.*(?:Tokyo|Japan.s capital|Japan’s capital))(?=.*(?:CPI|inflation|consumer prices))', ['https://www.stat.go.jp/english/'])
g('Japan January industrial production and retail sales', '2022-02-27T23:50', 'macro', r'^(?=.*(?:Japan|Japanese))(?=.*(?:industrial (?:output|production)|factory output|retail sales))(?=.*(?:January|Jan\b))', ['https://www.meti.go.jp/english/statistics/'])
# --- Australia / NZ (11:30 AEDT = 00:30 UTC; 14:30 AEDT = 03:30 UTC)
g('RBA February decision', '2022-02-01T03:30', 'policy', r'^(?=.*(?:RBA|Reserve Bank of Australia|Lowe|Australia.s central bank|Australian central bank))(?=.*(?:rates|rate|policy|decision|bond.buying|bond purchases|QE|quantitative easing|ends?|ended|holds?|patient))', ['https://www.rba.gov.au/schedules-events/calendar.html'])
g('RBA February Statement on Monetary Policy', '2022-02-04T00:30', 'staged_event', r'^(?=.*(?:RBA|Reserve Bank of Australia))(?=.*(?:Statement on Monetary Policy|\bSoMP\b|forecasts? (?:upgrade|raise|lift)|inflation forecast))', ['https://www.rba.gov.au/schedules-events/calendar.html'])
g('Australia December retail sales', '2022-02-04T00:30', 'macro', r'^(?=.*(?:Australia|Australian))(?=.*retail)(?=.*(?:December|Dec\b|fourth.quarter|Q4))', ['https://www.abs.gov.au/release-calendar'])
g('RBA February meeting minutes', '2022-02-15T00:30', 'staged_event', r'^(?=.*(?:RBA|Reserve Bank of Australia))(?=.*minutes)', ['https://www.rba.gov.au/schedules-events/calendar.html'])
g('Australia January labour force', '2022-02-17T00:30', 'macro', r'^(?=.*(?:Australia|Australian))(?=.*(?:jobs|employment|unemployment|labour force|labor force))(?=.*(?:January|Jan\b|Omicron))', ['https://www.abs.gov.au/release-calendar'])
g('Australia Q4 wage price index', '2022-02-23T00:30', 'macro', r'^(?=.*(?:Australia|Australian))(?=.*(?:wage price|wages|wage growth))(?=.*(?:fourth.quarter|Q4|December quarter|annual|2\.3))', ['https://www.abs.gov.au/release-calendar'])
g('RBNZ February decision', '2022-02-23T01:00', 'policy', r'^(?=.*(?:RBNZ|Reserve Bank of New Zealand|New Zealand.s central bank|\bOrr\b))(?=.*(?:rates|rate|OCR|policy|decision|hike|raises))', ['https://www.rbnz.govt.nz/monetary-policy'])
g('Australia January retail sales', '2022-02-28T00:30', 'macro', r'^(?=.*(?:Australia|Australian))(?=.*retail)(?=.*(?:January|Jan\b))', ['https://www.abs.gov.au/release-calendar'], eligible='2022-03-01')
# --- Poland
PLPAT = r'(?:Poland|Polish|Polsk\w*|GUS)'
g('Poland January manufacturing PMI', '2022-02-01T08:00', 'macro', r'^(?=.*(?:Poland|Polish|Polsk\w*|PMI w Polsce|PMI dla Polski|PMI w przemyśle))(?=.*(?:PMI|manufactur|przemysł\w*))(?=.*(?:January|Jan\b|stycz\w*))', ['https://www.markiteconomics.com/Public/Release/ReleaseDates'])
g('Poland February MPC decision', '2022-02-08', 'policy', r'^(?=.*(?:Poland|Polish|NBP|RPP|Glapi\w*|Rada Polityki))(?=.*(?:rates|stóp|stopy|procentow\w*|policy decision|decyzj\w*|hike|podwyż\w*|2\.75|2,75))', ['https://nbp.pl/en/monetary-policy/mpc-meetings-schedule/'], notes='Decision clock not asserted; eligible 9 February.')
g('NBP governor February press conference', '2022-02-09T14:00', 'staged_event', r'^(?=.*(?:Glapi\w*))(?=.*(?:konferencj\w*|press conference|said|says|powiedział|stwierdził|zapowiedział|ocenił|mówi))', ['https://nbp.pl'], notes='Governor press conference the day after the decision.')
g('Poland January flash CPI', '2022-02-15T09:00', 'macro', r'^(?=.*' + PLPAT + r'|.*inflacj\w*)(?=.*(?:consumer price|inflation|CPI|inflacj\w*))(?=.*(?:January|Jan\b|stycz\w*))', ['https://stat.gov.pl/en/release-calendar/'], notes='January flash estimate delayed to mid-February by the annual weight update; conservative clock.')
g('Poland Q4 flash GDP', '2022-02-15T09:00', 'macro', r'^(?=.*' + PLPAT + r')(?=.*(?:GDP|PKB|economy|gospodark\w*))(?=.*(?:fourth.quarter|Q4|IV kw\w*|czwartym kwartale|flash|szybki szacunek|2021))', ['https://stat.gov.pl/en/release-calendar/'])
g('Poland January output wages employment', '2022-02-21T09:00', 'macro', r'^(?=.*' + PLPAT + r')(?=.*(?:industrial (?:production|output)|produkcj\w*|producer prices|\bPPI\b|wages|salaries|wynagrodz\w*|employment|zatrudnieni\w*))(?=.*(?:January|Jan\b|stycz\w*))', ['https://stat.gov.pl/en/release-calendar/'], eligible='2022-02-23', notes='Output, wages and PPI fall on 21-22 February; conservative later eligibility.')
g('Poland January retail sales', '2022-02-23T09:00', 'macro', r'^(?=.*' + PLPAT + r')(?=.*(?:retail sales|sprzedaż\w* detalicz\w*))(?=.*(?:January|Jan\b|stycz\w*))', ['https://stat.gov.pl/en/release-calendar/'])
g('Poland January registered unemployment', '2022-02-24T09:00', 'macro', r'^(?=.*' + PLPAT + r')(?=.*(?:registered unemployment|bezroboci\w*))(?=.*(?:January|Jan\b|stycz\w*))(?=.*(?:GUS|statistics|statistical|urząd))', ['https://stat.gov.pl/en/release-calendar/'], notes='Ministry preliminary estimate is a distinct earlier release.')
# --- Corporate results (clock not asserted; first weekday edition after reporting day, UTC).
# Australian half-year results are released before the ASX open, i.e. the previous UTC day.
# Mercedes-Benz key figures (11 February) and Virgin Galactic (22 February) dates follow two independent dated reports each.
def result(name, day, pat):
    g(name + ' quarterly result', day, 'company_result', r'^(?=.*(?:' + pat + r'))(?=.*(?:earnings|results|quarter|profit|EPS|guidance|outlook|revenue|sales|forecast))', ['company investor-relations release calendar'], lookback=15)
for name, day, pat in [
    ('Alphabet', '2022-02-01', r'Alphabet|Google'), ('AMD', '2022-02-01', r'\bAMD\b|Advanced Micro'), ('PayPal', '2022-02-01', 'PayPal'),
    ('Starbucks', '2022-02-01', 'Starbucks'), ('General Motors', '2022-02-01', r'General Motors|\bGM\b'), ('Exxon Mobil', '2022-02-01', 'Exxon'),
    ('UPS', '2022-02-01', r'\bUPS\b|United Parcel'), ('Electronic Arts', '2022-02-01', r'Electronic Arts|\bEA\b'), ('Gilead', '2022-02-01', 'Gilead'),
    ('Meta Platforms', '2022-02-02', r'\bMeta\b|Facebook|\bFB\b'), ('Qualcomm', '2022-02-02', 'Qualcomm'), ('Spotify', '2022-02-02', 'Spotify'),
    ('AbbVie', '2022-02-02', 'AbbVie'), ('Novo Nordisk', '2022-02-02', r'Novo Nordisk|\bNovo\b'), ('Novartis', '2022-02-02', 'Novartis'),
    ('Sony', '2022-02-02', r'\bSony\b'), ('Infineon', '2022-02-02', 'Infineon'), ('Santander', '2022-02-02', r'Santander'),
    ('Amazon', '2022-02-03', 'Amazon'), ('Snap', '2022-02-03', r'\bSnap\b|Snapchat'), ('Pinterest', '2022-02-03', 'Pinterest'),
    ('Ford', '2022-02-03', r'\bFord\b'), ('Eli Lilly', '2022-02-03', r'Eli Lilly|\bLilly\b'), ('Merck', '2022-02-03', r'\bMerck\b'),
    ('ConocoPhillips', '2022-02-03', 'ConocoPhillips'), ('Honeywell', '2022-02-03', 'Honeywell'), ('Shell', '2022-02-03', r'\bShell\b'),
    ('Activision Blizzard', '2022-02-03', 'Activision'), ('Nintendo', '2022-02-03', 'Nintendo'), ('Roche', '2022-02-03', r'\bRoche\b'),
    ('Bristol Myers Squibb', '2022-02-04', r'Bristol.Myers|\bBMS\b'), ('Sanofi', '2022-02-04', 'Sanofi'), ('Regeneron', '2022-02-04', 'Regeneron'),
    ('Take-Two', '2022-02-07', r'Take.Two'), ('Tyson', '2022-02-07', r'\bTyson\b'),
    ('Pfizer', '2022-02-08', 'Pfizer'), ('Peloton', '2022-02-08', 'Peloton'), ('Chipotle', '2022-02-08', 'Chipotle'), ('Lyft', '2022-02-08', r'\bLyft\b'),
    ('Amgen', '2022-02-08', 'Amgen'), ('BP', '2022-02-08', r'\bBP\b'), ('Enphase', '2022-02-08', 'Enphase'), ('SoftBank', '2022-02-08', 'SoftBank'),
    ('BNP Paribas', '2022-02-08', 'BNP'), ('Hasbro', '2022-02-08', 'Hasbro'), ('Commonwealth Bank', '2022-02-08', r'Commonwealth Bank|\bCBA\b|CommBank'),
    ('Walt Disney', '2022-02-09', 'Disney'), ('Uber', '2022-02-09', r'\bUber\b'), ('CVS Health', '2022-02-09', r'\bCVS\b'), ('Toyota', '2022-02-09', 'Toyota'),
    ('TotalEnergies', '2022-02-09', 'TotalEnergies'), ('Equinor', '2022-02-09', 'Equinor'), ('Yum Brands', '2022-02-09', r'\bYum\b'), ('Mattel', '2022-02-09', 'Mattel'),
    ('Twitter', '2022-02-10', 'Twitter'), ('Coca-Cola', '2022-02-10', r'Coca.Cola|\bCoke\b'), ('PepsiCo', '2022-02-10', 'PepsiCo|Pepsi'),
    ('AstraZeneca', '2022-02-10', 'AstraZeneca'), ('Unilever', '2022-02-10', 'Unilever'), ('Siemens', '2022-02-10', r'\bSiemens\b(?! Energy| Healthineers| Gamesa)'),
    ('Zillow', '2022-02-10', 'Zillow'), ('Affirm', '2022-02-10', r'\bAffirm\b'), ('Cloudflare', '2022-02-10', 'Cloudflare'), ('Expedia', '2022-02-10', 'Expedia'),
    ('Datadog', '2022-02-10', 'Datadog'), ('Tokyo Electron', '2022-02-10', 'Tokyo Electron'), ('Philip Morris', '2022-02-10', 'Philip Morris'),
    ('BHP', '2022-02-14', r'\bBHP\b'), ('CSL', '2022-02-15', r'\bCSL\b'),
    ('Airbnb', '2022-02-15', 'Airbnb'), ('Roblox', '2022-02-15', 'Roblox'), ('Upstart', '2022-02-15', 'Upstart'), ('Marriott', '2022-02-15', 'Marriott'),
    ('Devon Energy', '2022-02-15', r'\bDevon\b'), ('Wesfarmers', '2022-02-16', 'Wesfarmers'),
    ('Nvidia', '2022-02-16', r'Nvidia|\bNVDA\b'), ('Shopify', '2022-02-16', 'Shopify'), ('Cisco', '2022-02-16', r'\bCisco\b'), ('DoorDash', '2022-02-16', 'DoorDash'),
    ('Kraft Heinz', '2022-02-16', 'Kraft'), ('Analog Devices', '2022-02-16', 'Analog Devices'), ('Fortescue', '2022-02-15', 'Fortescue'), ('Applied Materials', '2022-02-16', 'Applied Materials'),
    ('Walmart', '2022-02-17', 'Walmart'), ('Palantir', '2022-02-17', 'Palantir'), ('Roku', '2022-02-17', r'\bRoku\b'), ('DraftKings', '2022-02-17', 'DraftKings'),
    ('Nestle', '2022-02-17', r'Nestl[eé]'), ('Airbus', '2022-02-17', 'Airbus'), ('Kering', '2022-02-17', 'Kering'), ('Dropbox', '2022-02-17', 'Dropbox'),
    ('Deere', '2022-02-18', r'\bDeere\b|John Deere'), ('Renault', '2022-02-18', 'Renault'), ('Hermes', '2022-02-18', r'Herm[eè]s'),
    ('Home Depot', '2022-02-22', 'Home Depot'), ('Macy\'s', '2022-02-22', r'Macy'), ('Medtronic', '2022-02-22', 'Medtronic'), ('Palo Alto Networks', '2022-02-22', 'Palo Alto'),
    ('Stellantis', '2022-02-22', 'Stellantis'), ('HSBC', '2022-02-22', r'\bHSBC\b'), ('Toll Brothers', '2022-02-22', 'Toll Brothers'), ('Woolworths', '2022-02-22', 'Woolworths'),
    ('Lowe\'s', '2022-02-23', r'\bLowe\'?s\b|\bLowe’s\b'), ('TJX', '2022-02-23', r'\bTJX\b|TJ Maxx'), ('Lucid', '2022-02-23', r'\bLucid\b'), ('eBay', '2022-02-23', r'\beBay\b'),
    ('Booking', '2022-02-23', r'Booking Holdings|Booking\.com'), ('Teladoc', '2022-02-23', 'Teladoc'), ('Rio Tinto', '2022-02-23', 'Rio Tinto'), ('Puma', '2022-02-23', r'\bPuma\b'),
    ('Alibaba', '2022-02-24', 'Alibaba'), ('Moderna', '2022-02-24', 'Moderna'), ('Block', '2022-02-24', r'Block Inc|\bBlock\b.{0,20}(?:Square|Cash App|Dorsey)|Square|\bSQ\b'),
    ('Coinbase', '2022-02-24', 'Coinbase'), ('Dell', '2022-02-24', r'\bDell\b'), ('Zscaler', '2022-02-24', 'Zscaler'), ('Etsy', '2022-02-24', r'\bEtsy\b'),
    ('Beyond Meat', '2022-02-24', 'Beyond Meat'), ('Intuit', '2022-02-24', 'Intuit'), ('Monster Beverage', '2022-02-24', r'Monster Beverage'), ('Newmont', '2022-02-24', 'Newmont'),
    ('Wayfair', '2022-02-24', 'Wayfair'), ('Mercedes-Benz', '2022-02-11', r'Mercedes'), ('Virgin Galactic', '2022-02-22', 'Virgin Galactic'), ('Occidental', '2022-02-24', r'Occidental'),
    ('Li Auto', '2022-02-25', r'Li Auto'), ('Allianz', '2022-02-25', 'Allianz'), ('Foot Locker', '2022-02-25', 'Foot Locker'),
    ('Berkshire Hathaway', '2022-02-26', r'Berkshire|Buffett'),
    ('Zoom', '2022-02-28', r'Zoom Video|\bZoom\b(?=.{0,30}(?:shares|stock|earnings|results))|\bZM\b'), ('Novavax', '2022-02-28', 'Novavax')]:
    result(name, day, pat)
for g_ in G:
    if g_['label'] in {'Zoom quarterly result', 'Novavax quarterly result'}: g_['eligible_edition'] = '2022-03-01'; g_['earliest_pub_date'] = earliest('2022-03-01', 15)
# --- Company operations / staged corporate events
g('Alphabet 20-for-1 split announcement', '2022-02-01T21:00', 'company_operation', r'^(?=.*(?:Alphabet|Google))(?=.*(?:stock split|20.for.1|20:1|20-to-1|split))(?=.*(?:announc\w*|unveil\w*|declar\w*|approv\w*|after|surge\w*|jump\w*|soar\w*|rall\w*))', ['https://abc.xyz/investor/'], notes='Announced with fourth-quarter results after the 1 February close.')
g('Amazon Prime price increase', '2022-02-03T21:00', 'macro', r'^(?=.*(?:Amazon|Prime))(?=.*Prime)(?=.*(?:\$139|139 dollars|price (?:hike|increase|rise)|raises? (?:the )?(?:annual )?(?:price|fee|cost)|raising (?:the )?(?:price|fee|cost)|hikes? (?:the )?(?:price|fee|cost)|more expensive))', ['https://ir.aboutamazon.com'])
g('Nvidia Arm deal termination', '2022-02-08T06:00', 'macro', r'^(?=.*(?:Nvidia|SoftBank|\bArm\b))(?=.*\bArm\b)(?=.*(?:terminat\w*|scrap\w*|abandon\w*|calls? off|called off|ditch\w*|collaps\w*|\bends?\b|\bended\b|walks? away|walked away|\bdrops?\b|\bdropped\b|\bfails?\b|\bfailed\b|\bdead\b|\bIPO\b|Haas|Segars))', ['https://nvidianews.nvidia.com/news/nvidia-and-softbank-group-announce-termination-of-nvidias-acquisition-of-arm-limited'], notes='Announced with SoftBank results in Tokyo on 8 February.')
g('Peloton CEO change', '2022-02-08', 'macro', r'^(?=.*Peloton)(?=.*(?:Foley|McCarthy|\bCEO\b|chief executive))(?=.*(?:steps? down|stepped down|replac\w*|ousts?|ousted|out as|exit\w*|names?|named|new CEO|job cuts|cuts? 2,800|2,800|layoffs?))', ['https://investor.onepeloton.com'], notes='Announced with results on 8 February; earlier activist and bid reports are distinct.')
g('Wormhole bridge exploit', '2022-02-02T19:00', 'macro', r'^(?=.*Wormhole)(?=.*(?:hack\w*|exploit\w*|stolen|steal\w*|drain\w*|attack\w*|\$32\d|32\d million|bounty))', ['https://wormholecrypto.medium.com'])
g('Bitfinex hack laundering arrests', '2022-02-08T15:00', 'macro', r'^(?=.*(?:Bitfinex|Lichtenstein|Razzlekhan|Heather Morgan))(?=.*(?:arrest\w*|seiz\w*|\$3\.6|3\.6 billion|charged|launder\w*|recover\w*))', ['https://www.justice.gov/opa/pr/two-arrested-alleged-conspiracy-launder-45-billion-stolen-cryptocurrency'])
g('OPEC+ February meeting decision', '2022-02-02T13:00', 'macro', r'^(?=.*(?:OPEC))(?=.*(?:agree\w*|stick\w*|sticks|stuck|raises?|boost\w*|increase\w*|400,000|400k|rubber.stamp\w*|approv\w*|maintain\w*|keeps?|kept))', ['https://www.opec.org'], lookback=6)
g('Intel investor meeting', '2022-02-17T14:00', 'macro', r'^(?=.*Intel)(?=.*(?:investor (?:day|meeting)|Gelsinger|analyst day))(?=.*(?:unveil\w*|outlined|outlines|laid out|lays out|targets?|forecast\w*|projects?|says|said|sees|plans|roadmap|shares (?:fall|fell|drop|slide|sink)))', ['https://www.intc.com'])
g('Super Bowl LVI game and broadcast', '2022-02-14T03:30', 'macro', r'^(?=.*(?:Super Bowl|Rams|Bengals|halftime|QR code))(?=.*(?:Coinbase|QR code|crash\w*|\bwins?\b|\bwon\b|\bbeat\b|\bbeats\b|champions?|\bMVP\b|recap|review|best (?:and worst )?ads|worst ads|ads ranked|ranking|Ad Meter|ratings|viewers|viewership|most.watched|halftime show (?:was|review|recap)|Kupp|Stafford|Burrow|Donald))', ['https://www.nfl.com/super-bowl/'], notes='Kickoff 23:30 UTC 13 February; game and advertising outcomes fall after the 14 February 00:00 UTC cutoff.')
g('Truth Social app launch', '2022-02-21T05:00', 'macro', r'^(?=.*(?:Truth Social|Trump.{0,20}social media app|Trump.{0,20}app))(?=.*(?:launch\w*|\blive\b|went live|goes live|debut\w*|App Store|\btops?\b|topped|No\. ?1|number one|downloads?|waitlist|wait list|glitch\w*|rollout|rolled out|available))', ['https://apps.apple.com/us/app/truth-social/id1586018825'], notes='App appeared on the App Store late 20 February ET, after the 21 February 00:00 UTC cutoff; dated pending-launch previews remain eligible.')
g('Canada Emergencies Act invocation', '2022-02-14T21:00', 'macro', r'^(?=.*(?:Trudeau|Canada|Canadian|Ottawa))(?=.*(?:Emergencies Act|emergency powers|emergency measures))(?=.*(?:invok\w*|declar\w*|\buses?\b|\bused\b|enact\w*|triggers?|triggered))', ['https://pm.gc.ca/en/news'])
# --- Russia / Ukraine sequence (release outcomes cannot predate the event)
g('Russia partial troop pullback claims', '2022-02-15T08:00', 'macro', r'^(?=.*' + RUS + r')(?=.*(?:troops?|forces|units|soldiers|tanks))(?=.*(?:\breturn\w*|withdraw\w*|pull(?:s|ing|ed)? back|pullback|pull-back|leav\w* Crimea|de-escalat\w*|back to (?:base|barracks)))', ['http://en.kremlin.ru'], notes='Defence-ministry announcement Moscow morning 15 February; earlier forward claims stay eligible.')
g('Duma appeal on breakaway recognition', '2022-02-15T12:00', 'macro', r'^(?=.*(?:Duma|lawmakers|parliament|MPs|deputies))(?=.*(?:recogni\w*))(?=.*(?:\bvot\w*|\bbacks?\b|\bbacked\b|\basks?\b|\basked\b|appeal\w*|approv\w*|passes|passed|urges?|urged))(?=.*(?:Donetsk|Luhansk|Lugansk|separatist|breakaway|Donbas|DPR|LPR))', ['http://duma.gov.ru'])
g('Putin recognises breakaway regions', '2022-02-21T18:30', 'macro', r'^(?=.*(?:Putin|Kremlin|Russia|Russian|Moscow))(?=.*(?:recogni[sz]es|recogni[sz]ed|recogni[sz]ing|signs? decree|signed decrees?|formally recogni\w*|independence of))(?=.*(?:Donetsk|Luhansk|Lugansk|separatist|breakaway|Donbas|DPR|LPR|rebel))', ['http://en.kremlin.ru/events/president/news/67829'], notes='Televised address and decrees evening Moscow time 21 February.')
g('Putin orders troops into breakaway regions', '2022-02-21T21:00', 'macro', r'^(?=.*(?:Putin|Russia|Russian|Kremlin))(?=.*(?:orders?|ordered|sends?|\bsent\b|deploy\w*|moves?|moving|dispatch\w*|roll\w* into|enter\w*))(?=.*(?:troops|forces|peacekeep\w*|tanks|military))(?=.*(?:Donbas|Donetsk|Luhansk|Lugansk|separatist|breakaway|rebel|eastern Ukraine))', ['http://en.kremlin.ru'])
g('US order on breakaway regions', '2022-02-21T23:30', 'macro', r'^(?=.*(?:Biden|White House|\bUS\b|U\.S\.|Washington))(?=.*(?:executive order|\bbans?\b|prohibit\w*|sanction\w*))(?=.*(?:Donetsk|Luhansk|Lugansk|breakaway|separatist|DNR|LNR|DPR|LPR))', ['https://www.whitehouse.gov/briefing-room/'])
g('Germany halts Nord Stream 2 certification', '2022-02-22T12:30', 'macro', r'^(?=.*Nord Stream)(?=.*(?:halt\w*|suspend\w*|\bstops?\b|stopped|freez\w*|froze|shelv\w*|block\w*|pull\w* the plug|pulls? plug|puts? on hold|put on hold|\bdead\b|scrap\w*))(?=.*(?:Germany|German|Scholz|Berlin))', ['https://www.bundesregierung.de'], notes='Scholz announcement midday CET 22 February; conditional threats remain eligible.')
g('Western sanctions first tranche', '2022-02-22T19:00', 'macro', r'^(?=.*sanction\w*)(?=.*(?:Russia|Russian|Moscow|Kremlin|oligarchs?|sovereign debt|\bVEB\b|Promsvyazbank|elites?|banks?))(?=.*(?:announc\w*|impos\w*|unveil\w*|\bslaps?\b|\bhits?\b|first tranche|\btranche\b|rolls? out|rolled out|levels?|levied|agrees?|agreed|adopts?|adopted|approves?|approved))', ['https://www.whitehouse.gov/briefing-room/', 'https://www.gov.uk/government/news'], notes='UK and US first tranches 22 February; preparatory or threatened sanctions remain eligible.')
g('Russian invasion of Ukraine begins', '2022-02-24T03:00', 'macro', r'^(?=.*(?:Russia|Russian|Putin|Kremlin|Moscow|Ukraine|Ukrainian|Kyiv|Kiev))(?=.*(?:\binvades\b|\binvaded\b|has invaded|invasion (?:begins|began|has begun|is underway|underway|starts|started)|launch(?:es|ed) (?:a |an )?(?:full.scale |military |ground |all.out |massive )?(?:invasion|attack|assault|offensive|operation|war|strikes)|attack(?:s|ed) (?:on )?Ukraine|special military operation|declares? war|explosions? (?:in|across|heard in|rock\w*) (?:Kyiv|Kiev|Kharkiv|Odesa|Odessa|Mariupol|the capital|Ukraine)|blasts? (?:in|heard in|rock\w*) (?:Kyiv|Kiev|Kharkiv|Odesa|Odessa|Mariupol)|missile strikes? (?:on|across|hit)|air ?strikes? (?:on|across|hit)|troops (?:cross\w*|enter\w*|pour\w*|roll\w*|storm\w*)|tanks (?:cross\w*|enter\w*|roll\w*)|bombard\w*|Chernobyl|martial law|Kyiv (?:under attack|attacked|is attacked)|under attack|Moscow (?:exchange|bourse|stock exchange) (?:halts?|suspends?|halted|suspended)|halts? trading on (?:the )?Moscow|amid invasion|after invasion|after Russia invades|Russia.s invasion|Russian invasion (?:of Ukraine )?(?:sends|sparks|rattles|hits|triggers|roils|sinks|lifts|drives|pushes)))', ['http://en.kremlin.ru/events/president/news/67843'], notes='Televised address about 05:50 Moscow (02:50 UTC) 24 February, strikes immediately after; day-granular US-dated 23 February stamps must not admit it to the 24 February edition.')
g('Brent above 100 dollars', '2022-02-24T03:00', 'macro', r'^(?=.*(?:Brent|oil|crude))(?=.*(?:\$100|100 dollars|100 a barrel|\$100.a.barrel|\$100/bbl|triple digits|three digits))(?=.*(?:\btops?\b|topped|\bhits?\b|breaks?|broke|breach\w*|surg\w* (?:past|above|over|beyond)|soar\w* (?:past|above|over)|cross\w*|\babove\b|\bover\b|tops? \$100|spikes? (?:past|above|over)|jumps? (?:past|above|over)|first time since 2014))', ['https://www.theice.com/products/219/Brent-Crude-Futures'], notes='Brent first traded above $100 in Asian hours after the invasion began.')
g('US sanctions after invasion', '2022-02-24T18:30', 'macro', r'^(?=.*sanction\w*|.*export controls?)(?=.*(?:Sberbank|\bVTB\b|export controls?|semiconductor|technology exports|full blocking|severe|sweeping|toughest|harshest|crippling))(?=.*(?:announc\w*|impos\w*|unveil\w*|\bslaps?\b|\bhits?\b|levels?|levied|rolls? out|rolled out|adopt\w*|approv\w*|agree\w*))', ['https://www.whitehouse.gov/briefing-room/'], notes='Biden announcement afternoon ET 24 February.')
g('EU leaders agree second sanctions package', '2022-02-25T01:00', 'macro', r'^(?=.*(?:\bEU\b|European Union|EU leaders|Brussels|von der Leyen|Michel))(?=.*sanction\w*)(?=.*(?:agree\w*|approv\w*|adopt\w*|impos\w*|endors\w*|back\w*|massive|sweeping))', ['https://www.consilium.europa.eu/en/meetings/european-council/2022/02/24/'], lookback=4, notes='Summit conclusions early 25 February UTC; short lookback leaves the 23 February first package eligible.')
g('SWIFT exclusion and central bank sanctions', '2022-02-26T21:00', 'macro', r'^(?=.*(?:SWIFT|central bank|Bank of Russia|reserves))(?=.*(?:Russia|Russian|banks|Moscow))(?=.*(?:\bcut(?:s)? off\b|\bremov(?:es|ed|ing)\b|\bexclud(?:es|ed|ing)\b|\bban(?:s|ned)\b|\bkick(?:s|ed)? out\b|\bexpel(?:s|led)\b|\bdisconnect(?:s|ed)\b|agree(?:s|d)? to (?:cut|remove|exclude|ban|disconnect)|\bfreez(?:es|ing)\b|\bfroze\b|\bfrozen\b|immobili\w*|paralys\w*|paralyz\w*))', ['https://www.whitehouse.gov/briefing-room/statements-releases/2022/02/26/joint-statement-on-further-restrictive-economic-measures/'], notes='Joint statement evening CET 26 February.')
g('Russian central bank emergency hike', '2022-02-28T04:30', 'policy', r'^(?=.*(?:Bank of Russia|Russian central bank|Russia.s central bank|Russia’s central bank|\bCBR\b|Nabiullina))(?=.*(?:20%|20 percent|hikes?|raises?|doubles?|more than doubles|emergency))', ['https://www.cbr.ru/eng/press/pr/'], eligible='2022-03-01', lookback=4, notes='Announced Moscow morning 28 February after the cutoff; the 11 February hike is outside this lookback.')
g('Ruble collapse after SWIFT measures', '2022-02-28T00:00', 'macro', r'^(?=.*(?:ruble|rouble))(?=.*(?:plung\w*|crash\w*|collaps\w*|record low|tumbl\w*|30%|nosedive\w*|sinks?|sank|freefall|free fall|11\d|10\d per dollar))', ['https://www.moex.com'], eligible='2022-03-01', lookback=3, notes='Offshore and Moscow trading after the weekend SWIFT measures; earlier 22-24 February ruble lows remain eligible.')
g('Bank of Russia February decision', '2022-02-11T10:30', 'policy', r'^(?=.*(?:Bank of Russia|Russian central bank|Russia.s central bank|Russia’s central bank|\bCBR\b|Nabiullina))(?=.*(?:rates?|hikes?|raises?|9\.5|decision))', ['https://www.cbr.ru/eng/press/pr/'])
G.sort(key=lambda x: (x['eligible_edition'], x['label']))
out = {'month': '2022-02', 'status': 'pre-authoring safety screen', 'scope': 'Safety screen only; compact historical release clocks, not writer factual evidence.', 'guards': G}
(ROOT / 'audit_work' / 'feb2022_release_schedule.json').write_text(json.dumps(out, indent=1, ensure_ascii=False))
print(len(G), 'guards')
