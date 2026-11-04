"""Conservative independent own-date headline advisories; never original article-vintage certification.
This scanner does not import owner screening code or alter any source feed.
"""
from pathlib import Path
import json,gzip,hashlib,re,datetime as dt,sys
R=Path('/workspace/work/sep2024/repo/corrections/2024-09');UTC=dt.timezone.utc
S=R/('work/source_candidates/feeds' if '--stage-only' in sys.argv else 'feeds')
D=[dt.date(2024,9,n) for n in range(1,31) if dt.date(2024,9,n).weekday()<5]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(gzip.decompress(p.read_bytes()))
def rule(label,timestamp,pattern):return (label,dt.datetime.fromisoformat(timestamp).replace(tzinfo=UTC),re.compile('^'+pattern,re.I))
# Actual release clocks, not nominal report labels. Selected risks only.
EVENTS=[
 rule('China August Caixin manufacturing PMI','2024-09-02T01:45',r'(?=.*(?:China|Chinese|Caixin))(?=.*(?:Caixin|private))(?=.*manufactur)(?=.*(?:PMI|purchasing managers|activity))(?=.*(?:August|Aug\b))'),
 rule('China August Caixin services PMI','2024-09-04T01:45',r'(?=.*(?:China|Chinese|Caixin))(?=.*(?:Caixin|private))(?=.*services)(?=.*(?:PMI|purchasing managers|activity))(?=.*(?:August|Aug\b))'),
 rule('US August ISM manufacturing','2024-09-03T14:00',r'(?=.*(?:ISM|Institute for Supply Management))(?=.*manufactur)(?=.*(?:August|Aug\b))'),
 rule('US July JOLTS','2024-09-04T14:00',r'(?=.*(?:JOLTS|job openings))(?=.*July)'),
 rule('US August ADP employment','2024-09-05T12:15',r'(?=.*ADP)(?=.*(?:August|Aug\b|private payroll|private employment))'),
 rule('US August ISM services','2024-09-05T14:00',r'(?=.*(?:ISM|Institute for Supply Management))(?=.*services)(?=.*(?:August|Aug\b))'),
 rule('US August employment','2024-09-06T12:30',r'(?=.*(?:\bUS\b|U\.S\.|\bAmerica\b|nonfarm|payroll))(?=.*(?:employment|unemployment|jobs|nonfarm|payroll))(?=.*(?:August|Aug\b))'),
 rule('US August CPI','2024-09-11T12:30',r'(?=.*(?:\bUS\b|U\.S\.|\bAmerica\b))(?=.*(?:CPI|consumer price|inflation))(?=.*(?:August|Aug\b))'),
 rule('US August PPI','2024-09-12T12:30',r'(?=.*(?:\bUS\b|U\.S\.|\bAmerica\b))(?=.*(?:PPI|producer price|wholesale price))(?=.*(?:August|Aug\b))'),
 rule('US August retail sales','2024-09-17T12:30',r'(?=.*(?:\bUS\b|U\.S\.|\bAmerica\b))(?=.*retail sales)(?=.*(?:August|Aug\b))'),
 rule('Federal Reserve September decision','2024-09-18T18:00',r'(?=.*(?:Fed|FOMC|Federal Reserve))(?=.*(?:rate|policy))(?=.*(?:September|Sept\b|basis.point|half.point|50.basis|25.basis))'),
 rule('US August PCE','2024-09-27T12:30',r'(?=.*(?:PCE|personal consumption expenditure|Fed.s (?:preferred|favou?rite) inflation))(?=.*(?:August|Aug\b))'),
 rule('ECB September decision','2024-09-12T12:15',r'(?=.*(?:ECB|European Central Bank))(?=.*(?:rates?|policy|deposit))(?=.*(?:September|Sept\b|25 basis|25.basis|quarter.point))'),
 rule('Bank of England September decision','2024-09-19T11:00',r'(?=.*(?:BOE|Bank of England))(?=.*(?:rates?|policy))(?=.*(?:September|Sept\b|unchanged|holds?|keeps?|leaves?))'),
 rule('Bank of Japan September decision','2024-09-20T03:00',r'(?=.*(?:BOJ|Bank of Japan|Ueda))(?=.*(?:rates?|policy))(?=.*(?:September|Sept\b|unchanged|holds?|keeps?|leaves?))'),
 rule('RBA September decision','2024-09-24T04:30',r'(?=.*(?:RBA|Reserve Bank of Australia))(?=.*(?:rates?|policy))(?=.*(?:September|Sept\b|unchanged|holds?|keeps?|leaves?))'),
 rule('NBP September decision','2024-09-04T12:00',r'(?=.*(?:NBP|RPP|Polish central bank|Poland central bank))(?=.*(?:rate|stopy|stopach|bez zmian))(?=.*(?:September|Sept\b|wrze|unchanged|holds?|keeps?|leaves?|utrzym))'),
 rule('Bank of Canada September decision','2024-09-04T13:45',r'(?=.*(?:Bank of Canada|BOC|Canada.s central bank))(?=.*(?:rate|policy))(?=.*(?:September|Sept\b|cuts?|lower|25.basis|quarter.point))'),
 rule('China August CPI/PPI','2024-09-09T01:30',r'(?=.*(?:China|Chinese))(?=.*(?:CPI|PPI|consumer price|producer price|inflation|deflation))(?=.*(?:August|Aug\b))'),
 rule('China August trade','2024-09-10T03:00',r'(?=.*(?:China|Chinese))(?=.*(?:exports|imports|trade surplus|trade data))(?=.*(?:August|Aug\b))'),
 rule('China August credit (conservative day bound)','2024-09-13T00:00',r'(?=.*(?:China|Chinese|PBOC))(?=.*(?:new loans|bank lending|credit data|total social financing|money supply|M2))(?=.*(?:August|Aug\b))'),
 rule('China August activity','2024-09-14T02:00',r'(?=.*(?:China|Chinese))(?=.*(?:industrial output|industrial production|retail sales|fixed.asset|property investment|home prices))(?=.*(?:August|Aug\b))'),
 rule('China September LPR','2024-09-20T01:00',r'(?=.*(?:China|Chinese|PBOC))(?=.*(?:loan prime|LPR|benchmark lending))(?=.*(?:September|Sept\b|unchanged|holds?|keeps?|leaves?))'),
 rule('China September stimulus package','2024-09-24T01:00',r'(?=.*(?:China|Chinese|PBOC|Pan Gongsheng))(?=.*(?:stimulus|reserve.requirement|RRR|mortgage rate|support package|support measures))(?=.*(?:announc|unveil|rolls? out|cuts?|slashes?|eases?))'),
 rule('China September Politburo package','2024-09-26T05:00',r'(?=.*(?:China|Chinese|Politburo|Xi Jinping))(?=.*(?:Politburo|top leaders|leadership|Xi Jinping))(?=.*(?:housing|property|fiscal|stimulus|economy|economic))(?=.*(?:pledges?|vows?|promises?|announc|unveil|steps? up|intensif))'),
 rule('US Trump-Harris September presidential debate','2024-09-11T01:00',r'(?=.*(?:Trump|Harris))(?=.*debate)(?=.*(?:wins?|won|defeat|clash|spar|face.off|faced.off|reactions?|takeaways|fact.check|performance))'),
 rule('Japan August national CPI','2024-09-19T23:30',r'(?=.*(?:Japan|Japanese))(?=.*(?:CPI|consumer prices|inflation))(?=.*(?:August|Aug\b))'),
 rule('Japan September Tokyo CPI','2024-09-26T23:30',r'(?=.*Tokyo)(?=.*(?:CPI|consumer prices|inflation))(?=.*(?:September|Sept\b))'),
 rule('Japan August industrial production / retail sales','2024-09-29T23:50',r'(?=.*(?:Japan|Japanese))(?=.*(?:industrial production|industrial output|factory output|retail sales))(?=.*(?:August|Aug\b))'),
 rule('China September official manufacturing PMI','2024-09-30T01:30',r'(?=.*(?:China|Chinese))(?=.*(?:PMI|manufacturing activity|factory activity|purchasing managers))(?=.*(?:September|Sept\b))'),
 rule('China September Caixin manufacturing PMI','2024-09-30T01:45',r'(?=.*(?:China|Chinese|Caixin))(?=.*(?:Caixin|private survey))(?=.*manufactur)(?=.*(?:September|Sept\b))'),
]
for name,day in [('Broadcom','05'),('Oracle','09'),('Adobe','12'),('FedEx','19'),('Micron','25'),('Costco','26'),('Accenture','26'),('H&M','26')]:
 EVENTS.append(rule(name+' September quarterly actuals','2024-09-'+day+'T00:00',r'(?=.*'+re.escape(name)+r')(?=.*(?:earnings|results|quarter|revenue|sales|profit|EPS|guidance))'))
EVENTS.append(rule('Nike October quarterly actuals','2024-10-01T20:00',r'(?=.*Nike)(?=.*(?:earnings|results|quarter|revenue|sales|profit|EPS|guidance))'))
FORWARD=re.compile(r'\b(?:(?:will|could|would|may|might|should)\s+(?:(?:also|still|soon|now|again|further)\s+)?|(?:expected|forecast|likely|seen|set|poised|due)\s+to\s+|plans?\s+to\s+|to\s+)(?:win|cut|hold|keep|report|beat|miss|top|rise|fall|jump|surge|slump|raise|lower|announce|unveil|approve|expand|decline|accelerate|slow|increase|decrease|drop|release|publish|decide|leave|boost)\b',re.I)
OUTCOME=re.compile(r'\b(?:announced|unveiled|approved|won|elected|reported|surged|accelerated|slowed|beats?|miss(?:es|ed)?|tops?|topped|rises?|rose|falls?|fell|jumps?|jumped|slumps?|slumped|raises?|raised|cuts?|lower(?:s|ed)?|holds?|held|keeps?|kept|expands?|expanded|declines?|declined|accelerates|slows|increases?|increased|decreases?|decreased|drops?|dropped|leaves?|left|pledges?|vows?|promises?|signs?|signed|boosts?|releases?|released|publishes|published)\b',re.I)
PREVIEW=re.compile(r'\b(?:preview|ahead of|what to expect|expected|forecast|estimates?|consensus|likely|seen|poised|due|will|could|would|may|might|to (?:report|release|announce|cut|hold|keep|raise|lower|decide|meet)|poll|survey|economists say|on course|signals?|backs?|hint|potential|this week|next week|calendar)\b',re.I)
NEUTRAL=re.compile(r'\b(?:better|worse|more|less|higher|lower|stronger|weaker|faster|slower|above|below|in line)\s+than\s+(?:expected|forecast|estimates?|predicted|anticipated)\b|\bas\s+(?:expected|forecast|anticipated)\b',re.I)
ROLLING=re.compile(r'\b(?:live\s*[:|]|as it happened|live updates|live blog|live price|live chart|live earnings|live coverage|live trading|watch live|stock market today|markets today)|\bprice today\b.*\b(?:chart|market data)\b',re.I)
def completed(t):
 t=NEUTRAL.sub('',t);res=FORWARD.sub('',t)
 if OUTCOME.search(res):return True
 if PREVIEW.search(t):return False
 # Numeric release text without an explicit preview can describe an actual.
 return bool(re.search(r'\d(?:[\d.,]*\s*%|[\d.,]*\s*(?:million|billion|trillion|K|bps|basis points))',res,re.I))
by_date={};counts={};advisories={}
for d in D:
 stamp=d.isoformat();p=S/(stamp+'.json.gz');feed=load(p);cutoff=dt.datetime.combine(d,dt.time(),UTC);ex=[];adv=[]
 for x in feed['items']:
  title=x['title'];headline=title.rsplit(' - ',1)[0];pub=dt.datetime.fromisoformat(x['published_at']);reasons=[]
  if ROLLING.search(headline):reasons.append('Rolling/live headline cannot establish a fixed own-date claim.')
  for label,release,pat in EVENTS:
   if pat.search(title) and completed(title) and release-dt.timedelta(days=7)<=pub<release and cutoff<=release:
    reasons.append('Possible '+label+' actual before its actual release; RSS pubDate does not admit the outcome. Omit completed-event claim.')
  if stamp=='2024-09-30':
   if re.search(r'(?=.*(?:Ishiba))(?=.*(?:Nikkei|Japanese stocks|Japan stocks|Japan.s stocks))(?=.*(?:falls?|fell|drops?|dropped|plunges?|plunged|slumps?|slumped|tumbles?|tumbled|slides?|slid|selloff|sell-off))',title,re.I) and not re.search(r'futures|derivative',title,re.I):
    reasons.append('Japan completed cash-session fall following Ishiba victory would require Monday September30 trading, after this cutoff. Friday Tokyo cash close preceded the leadership outcome; futures require explicit own-headline support.')
   if pub.date()==dt.date(2024,9,29) and re.search(r'(?=.*(?:Monday|Sept(?:ember)?\.?\s*30|Sep\.?\s*30|September 30))(?=.*(?:stocks?|markets?|Nikkei|Hang Seng|CSI|Shanghai|ASX|shares))(?=.*(?:rise|rises|rose|jump|jumps|jumped|surge|surges|surged|fall|falls|fell|slump|slumps|slumped|plunge|plunges|plunged|rally|rallies|rallied|close|closed))',title,re.I) and completed(title):
    reasons.append('Possible completed Monday September30 session outcome carried by a Sunday nominal timestamp; no Monday session was completed by00UTC.')
  if re.search(r'ECB staff macroeconomic projections.*September 2024',title,re.I) and cutoff<=dt.datetime(2024,9,12,12,15,tzinfo=UTC):
   reasons.append('The September2024 ECB staff projection package was released with the September12 decision, after this cutoff. NominalSeptember6 indexing does not admit the new package.')
  if re.search(r'Presidential Election.*November 2024 Edition',title,re.I):
   reasons.append('November2024 edition label conflicts with this September evidence vintage; this appears updated or misdated. Omit the story.')
  if x['src'] in ('MacroMicro','TradingView'):
   reasons.append('Dynamic chart/indicator page does not establish a fixed original historical publication vintage. Omit concrete data claims unless an eligible dated headline independently establishes them.')
  if x['cat']=='monthly' and pub<cutoff-dt.timedelta(days=7) and re.search(r'Paragon REIT|PMI Discount Offer|retail property sale|Man Group appoints|United Texas Bank|BBVA.*Sabadell|CBA, ANZ, NAB|banks pre.empt|Japan parliament asks',title,re.I):
   reasons.append('Selected company/promotional/event headline is fresh-news meaning, over7days old. Broad macro-query category cannot extend it to35days.')
  if reasons:ex.append({k:x[k] for k in ('id','title','src','published_at')}|{'reasons':sorted(set(reasons))})
  # Separate nonblocking caution: post-release edition but impossible pre-release nominal publication.
  for label,release,pat in EVENTS:
   if cutoff>release and pub<release and release-pub<dt.timedelta(days=5) and pat.search(title) and completed(title):
    adv.append({k:x[k] for k in ('id','title','src','published_at')}|{'reason':'Nominal RSS time precedes possible '+label+' actual. Release is now past but original article vintage remains uncertified; use alternative eligible evidence or own-date claim review.'});break
 if stamp=='2024-09-30':
  for x in feed['items']:
   if re.search(r'Ishiba',x['title'],re.I) and re.search(r'wins?|won|victory|elected|leader|prime minister',x['title'],re.I):
    adv.append({k:x[k] for k in ('id','title','src','published_at')}|{'reason':'The Friday Tokyo cash close can predate the leadership outcome. This headline does not establish a completed Monday September30 cash-market response; distinguish explicitly supported futures from cash moves.'})
 by_date[stamp]={'feed_sha256':sha(p),'exclusions':ex,'advisories':adv};counts[stamp]=len(ex)
out={'status':'conservative_selected_headline_exclusions','scope':'Independent selected own-date timing/live-page checks. This does not exhaust semantic errors and does not certify original article publication dates. Selected release clocks are used only to reject impossible pre-release actuals; an accepted timestamp never proves a claim.','by_date':by_date,'counts':counts,'finite_rule_count':len(EVENTS),'limits':['No canonical publisher/body lookup was performed.','Patterns can be conservative around comparisons and prior-period results. Authors must review the exact claim against their own date only.','Dates after release do not establish source vintage. Advisories identify selected nominal-time anomalies for further own-date review.']}
q=Path(__file__).parent/('staged_semantic_exclusions.json' if '--stage-only' in sys.argv else 'semantic_exclusions.json');q.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(counts))
