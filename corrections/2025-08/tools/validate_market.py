"""Validate August cutoffs, available-observation arithmetic and reconstructed share units."""
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location('cards',ROOT/'tools/build_cards.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
data={j['ticker']:j for p in (ROOT/'data').glob('yf_*.json') for j in [json.loads(p.read_text())]}
tr=json.loads((ROOT/'data/treasury_par.json').read_text())
errors=[];assertions=0
def check(value,message):
 global assertions
 assertions+=1
 if not value:errors.append(message)
DATES=[str(dt.date(2025,8,n)) for n in range(1,32) if dt.date(2025,8,n).weekday()<5]
fetch=json.loads((ROOT/'audit/market_fetch.json').read_text())
check({x['ticker'] for x in fetch}==set(data),'Fetch inventory mismatch')
check(all(x['status']=='ok' for x in fetch),'Unresolved source fetch failure')
check(len(data)==294,'Expected294rawsymbols')
check(len(DATES)==21,'Expected21weekdaydates')
check(all(day<='2025-08-31' for day in tr),'LaterTreasuryrowsretained')
for t,j in data.items():
 check(all(day<='2025-08-31' for day,_ in j['rows']),t+':laterprice')
 check(len(j['rows'])==len({day for day,_ in j['rows']}),t+':duplicateprice')
 check(set(dict(j['rows']))==set(dict(j['as_traded_rows'])),t+':unitrowmismatch')
 # The partial augmentation attempt was corrected before writers were released.
 before=[r for r in j['rows'] if r[0]<'2025-08-01']
 check(len(before)>=21,t+':missing20observationreference')
 check(max((dt.date.fromisoformat(b[0])-dt.date.fromisoformat(a[0])).days for a,b in zip(before[-21:],before[-20:]))<=5,t+':gapinsideAugust1lookback')
for date in DATES:
 c=json.loads((ROOT/'cards'/f'{date}.json').read_text())
 check(c['report_date']==date and c['cutoff_utc']==date+'T00:00:00Z',date+':identity')
 check(len(c['markets'])==292,date+':instrumentcount')
 days=sorted(d for d in tr if d<date);latest=tr[days[-1]];earlier=tr[days[-21]];tc=c['treasury']
 check(tc['prior_close_date']==days[-1],date+':Treasurylatest')
 check(tc['obs20_earlier_date']==days[-21],date+':Treasuryreference')
 check(tc['spread_10y_2y_bps']==round((latest['10 Yr']-latest['2 Yr'])*100),date+':spread')
 for key,col in [('2y','2 Yr'),('10y','10 Yr'),('3m','3 Mo'),('30y','30 Yr')]:
  check(tc['prior_close_pct'][key]==f'{latest[col]:.2f}%',date+':yieldlevel'+key)
  check(tc['chg_20obs_bps'][key]==round((latest[col]-earlier[col])*100),date+':yieldchange'+key)
 check(tc['chg_20obs_bps']['spread']==round((latest['10 Yr']-latest['2 Yr'])*100)-round((earlier['10 Yr']-earlier['2 Yr'])*100),date+':spreadchange')
 for t,x in c['markets'].items():
  raw=data[t];rows=[r for r in raw['rows'] if r[0]<date];levels=dict(raw['as_traded_rows'])
  check(x['session']==rows[-1][0] and x['session']<date,date+' '+t+':latest/cutoff')
  check(x['ref_20s_session']==rows[-21][0] and x['ref_20s_session']<date,date+' '+t+':reference/cutoff')
  for n in [1,5,20]:check(x[f'chg_{n}s_pct']==round((rows[-1][1]/rows[-n-1][1]-1)*100,2),date+' '+t+':return'+str(n))
  if t=='CMCSA':check(x['close'] is None and x['ref_20s_close'] is None,date+':CMCSAwithheld')
  else:
   check(x['close']==m.fmt(levels[rows[-1][0]],t),date+' '+t+':currentunits')
   check(x['ref_20s_close']==m.fmt(levels[rows[-21][0]],t),date+' '+t+':referenceunits')
  unit_diff=abs((levels[rows[-1][0]]/rows[-1][1])/(levels[rows[-21][0]]/rows[-21][1])-1)>1e-6
  check(x['reference_share_units_differ']==unit_diff,date+' '+t+':splitreferencewarning')
  actions=json.loads((ROOT/'audit'/('actions_'+t.replace('^','_').replace('=','_').replace('.','_')+'.json')).read_text())['events']
  for day,value in [rows[-1],rows[-21]]:
   factor=1.
   for e in actions:
    if e['date']>day:factor*=float(e['factor'])
   check(abs(levels[day]-value*factor)<=max(1e-5,abs(levels[day])*1e-7),date+' '+t+':independentsplitfactor')
# Explicit exchange calendar and historical share-unit regressions.
cards={d:json.loads((ROOT/'cards'/f'{d}.json').read_text()) for d in DATES}
check(cards['2025-08-01']['markets']['^GSPC']['session']=='2025-07-31','August1USpriorclose')
check(cards['2025-08-01']['treasury']['prior_close_date']=='2025-07-31','August1Treasurypriorclose')
check(cards['2025-08-04']['markets']['BTC-USD']['session']=='2025-08-03','Sundaycryptoclose')
check(cards['2025-08-12']['markets']['^N225']['session']=='2025-08-08','JapanAugust11holiday')
check(cards['2025-08-18']['markets']['PKO.WA']['session']=='2025-08-14','PolandAugust15holiday')
check(float(cards['2025-08-01']['markets']['NFLX']['close'].replace(',',''))>500,'Netflixfuturesplitunitreconstruction')
check(float(cards['2025-08-01']['markets']['LCID']['close'].replace(',',''))<10,'Lucidpresplitunits')
check(m.curve_move(-10,-10)=='parallel rally (both down equally; spread unchanged)','Parallelrallylabel')
check(m.curve_move(10,10)=='parallel selloff (both up equally; spread unchanged)','Parallelsellofflabel')
result={'passed':not errors,'assertions':assertions,'errors':errors,'cards':21,'instruments_per_card':292,'raw_symbols':len(data),'fetch_failures':sum(x['status']!='ok' for x in fetch),'missing_metric_count':sum(x['chg_20s_pct'] is None for c in cards.values() for x in c['markets'].values()),'information_cutoff':'00:00 UTC per report date','retained_price_last_date':'2025-08-31','future_price_rows_retained':0,'level_suppression':['CMCSA'],'minimum20comparison_observations':21,'sources':['Yahoo Finance frozen daily chart data','Yahoo Finance frozen historical chart data','US Treasury daily par yield curve'],'card_sha256':{d:hashlib.sha256((ROOT/'cards'/f'{d}.json').read_bytes()).hexdigest() for d in DATES}}
(ROOT/'audit/market_validation.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='card_sha256'},indent=2));raise SystemExit(bool(errors))
