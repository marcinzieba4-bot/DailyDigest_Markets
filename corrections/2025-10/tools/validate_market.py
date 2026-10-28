"""Validate per-date cutoff selection, return arithmetic and historical quote units."""
import datetime as dt
import importlib.util
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('cards', ROOT / 'tools/build_cards.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
data = {j['ticker']:j for p in (ROOT/'data').glob('yf_*.json') for j in [json.loads(p.read_text())]}
tr = json.loads((ROOT/'data/treasury_par.json').read_text())
errors=[]; assertions=0

def check(value,message):
 global assertions
 assertions+=1
 if not value: errors.append(message)

check(len(data)==294, 'Expected complete 294-symbol raw universe')
fetch=json.loads((ROOT/'audit/market_fetch.json').read_text())
check(all(x['status']=='ok' for x in fetch), 'Some market fetches failed')
for t,j in data.items():
 check(all(day<='2025-10-31' for day,_ in j['rows']),t+': retained future price')
 check(len(j['rows'])==len(set(day for day,_ in j['rows'])),t+': duplicate session')
 check(set(dict(j['rows']))==set(dict(j['as_traded_rows'])),t+': unmatched as-traded session')
for day in range(1,32):
 d=dt.date(2025,10,day)
 if d.weekday()>4:continue
 j=json.loads((ROOT/'cards'/f'{d}.json').read_text()); date=str(d)
 check(len(j['markets'])==292,date+': wrong card instrument count')
 treasury_days=[x for x in sorted(tr) if x<date]
 tc=j['treasury']; latest=tr[treasury_days[-1]]
 check(tc['prior_close_date']==treasury_days[-1],date+': Treasury cutoff')
 check(tc['spread_10y_2y_bps']==round((latest['10 Yr']-latest['2 Yr'])*100),date+': Treasury spread')
 for t,c in j['markets'].items():
  rows=[r for r in data[t]['rows'] if r[0]<date]
  check(c['session']==rows[-1][0] and c['session']<date,date+' '+t+': cutoff/latest selection')
  for n in (1,5,20):
   expected=round((rows[-1][1]/rows[-n-1][1]-1)*100,2)
   check(c[f'chg_{n}s_pct']==expected,date+' '+t+': return arithmetic')
  levels=dict(data[t]['as_traded_rows'])
  if t=='CMCSA':check(c['close'] is None and c['ref_20s_close'] is None,date+': CMCSA level suppression')
  else:check(c['close']==m.fmt(levels[rows[-1][0]],t),date+' '+t+': as-traded close')
# Direct regression checks for post-report splits and a split inside the lookback.
c=json.loads((ROOT/'cards/2025-10-01.json').read_text())
check(c['markets']['NFLX']['close']=='1,198.92','NFLX future-split quote unit regression')
check(c['markets']['XLK']['close']=='281.86','XLK future-split quote unit regression')
check(c['markets']['BTC-USD']['session']=='2025-09-30','Crypto previous completed UTC day')
check(json.loads((ROOT/'cards/2025-10-14.json').read_text())['treasury']['prior_close_date']=='2025-10-10','Columbus Day Treasury calendar')
check(json.loads((ROOT/'cards/2025-10-14.json').read_text())['markets']['^GSPC']['session']=='2025-10-13','Columbus Day equity calendar')
check(c['markets']['LCID']['chg_20s_pct']==round((dict(data['LCID']['rows'])['2025-09-30']/dict(data['LCID']['rows'])[c['markets']['LCID']['ref_20s_session']]-1)*100,2),'LCID reverse split comparable return')
result={'passed':not errors,'assertions':assertions,'errors':errors,'cards':23,'instruments_per_card':292,'raw_symbols':len(data),'fetch_failures':sum(x['status']!='ok' for x in fetch),'information_cutoff':'00:00 UTC per report date','retained_price_last_date':'2025-10-31','future_price_rows_retained':0,'level_suppression':['CMCSA'],'sources':['Yahoo Finance daily chart API','US Treasury daily par yield curve']}
(ROOT/'audit/market_validation.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
raise SystemExit(bool(errors))
