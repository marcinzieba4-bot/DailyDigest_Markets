"""Independent October card arithmetic; does not import owner market tools."""
from pathlib import Path
import json, hashlib, datetime as dt, math, urllib.request, csv, io
from urllib.parse import urlsplit,parse_qs
from decimal import Decimal
import exchange_calendars as xc
from pandas.tseries.holiday import USFederalHolidayCalendar

R=Path('/workspace/work/oct2024/repo/corrections/2024-10')
W=Path(__file__).parent
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
dates=[dt.date(2024,10,n).isoformat() for n in range(1,32) if dt.date(2024,10,n).weekday()<5]
err=[];counts={}
def ck(v,msg,group='arithmetic'):
 counts[group]=counts.get(group,0)+1
 if not v:err.append(msg)
def bps(a,b):
 n=(Decimal(str(a))-Decimal(str(b)))*100
 assert n==n.to_integral_value()
 return int(n)
def percent(a,b):return round((a/b-1)*100,2)
def shape(n):return 'inverted' if n<0 else 'positive but very flat' if n<25 else 'positively sloped' if n<60 else 'moderately steep' if n<100 else 'steep'
def move(a,b):
 if abs(a)<4 and abs(b)<4:return 'little changed'
 if a==b:return 'parallel rally (both down equally; spread unchanged)' if a<0 else 'parallel selloff (both up equally; spread unchanged)'
 if a>0 and b>0:return 'bear steepening (both up, 10Y up more)' if b>a else 'bear flattening (both up, 2Y up more)'
 if a<0 and b<0:return 'bull steepening (both down, 2Y down more)' if b>a else 'bull flattening (both down, 10Y down more)'
 if b>0:return 'steepening (10Y up, 2Y down/flat)'
 if a>0:return 'flattening (2Y up, 10Y down/flat)'
 if b<0:return 'flattening (10Y down, 2Y up/flat)'
 return 'steepening (2Y down, 10Y up/flat)'
data={j['ticker']:j for p in (R/'data').glob('yf_*.json') for j in [read(p)]}
cards={d:read(R/'cards'/f'{d}.json') for d in dates}
fetch=read(R/'audit/market_fetch.json');tr=read(R/'data/treasury_par.json')
ck(set(data)=={x['ticker'] for x in fetch} and all(x['status']=='ok' for x in fetch),'Raw inventory/fetch success','inventory')
ck(len(data)==290 and len(cards)==23,'290 raw symbols and23 weekday cards','inventory')
fx={t for t in data if t.endswith('=X')};skip={'^TNX','^IRX'}
ck(len(fx)==7,'Seven raw audit-only spotFX marks','inventory')
actions={t:read(R/'audit'/('actions_'+t.replace('^','_').replace('=','_').replace('.','_')+'.json')) for t in data}
for t,j in data.items():
 rows=j['rows'];levels=dict(j['as_traded_rows']);params=parse_qs(urlsplit(j['source_url']).query)
 ck(rows==sorted(rows) and len(rows)==len(dict(rows)),t+' raw dates sorted/unique','inventory')
 ck(set(dict(rows))==set(levels) and all('2024-08-01'<=d<='2024-10-31' for d,v in rows),t+' bounded date sets','inventory')
 ck(all(math.isfinite(v) and v>0 for d,v in rows+j['as_traded_rows']),t+' positive finite values','inventory')
 ck(params.get('period1')==['1722470400'] and params.get('period2')==['1730419200'],t+' physical historical request bounds','inventory')
 for d,v in rows:
  factor=math.prod(e['factor'] for e in actions[t]['events'] if e['date']>d)
  ck(abs(levels[d]-v*factor)<max(1e-5,levels[d]*1e-7),t+' '+d+' split unit restoration','splits')
 if t=='NBIS':ck(rows[0][0]=='2024-10-21',t+' resumption boundary','inventory')
 else:ck(sum(d<'2024-10-01' for d,v in rows)>=21,t+' sufficient initial return history','inventory')
for d,c in cards.items():
 ck(c['report_date']==d and c['cutoff_utc']==d+'T00:00:00Z',d+' card identity','inventory')
 expected={t for t,j in data.items() if t not in skip|fx and any(day<d for day,v in j['rows'])}
 ck(set(c['markets'])==expected,d+' complete writer inventory withFX excluded','inventory')
 ck(set(c['excluded_vendor_marks']['tickers'])==fx,d+' FX omission declared','inventory')
 ck('DX-Y.NYB' in c['markets'],d+' DXY allowed index retained','inventory')
 for t,x in c['markets'].items():
  j=data[t];prior=[r for r in j['rows'] if r[0]<d];day,close=prior[-1];lev=dict(j['as_traded_rows'])
  ck(x['session']==day<d,d+' '+t+' latest retained completed observation','sessions')
  ck(x['currency']==j['currency'] and x['tz']==j['tz'],d+' '+t+' currency andtimezone')
  ck(x['close']==(None if j.get('level_restriction') else f'{lev[day]:,.2f}'),d+' '+t+' displayclose')
  for n in (1,5,20):
   enough=len(prior)>n
   ck(x[f'chg_{n}s_pct']==(percent(close,prior[-n-1][1]) if enough else None),d+' '+t+' return'+str(n))
   if not enough:ck(t=='NBIS' and bool(x.get('history_limitation')),d+' '+t+' documented insufficient history')
  ref=prior[-21] if len(prior)>20 else None
  ck(x['ref_20s_session']==(ref[0] if ref else None),d+' '+t+' reference session')
  ck(x['ref_20s_close']==(f'{lev[ref[0]]:,.2f}' if ref and not j.get('level_restriction') else None),d+' '+t+' reference units')
  changed=abs(lev[day]/close/(lev[ref[0]]/ref[1])-1)>1e-6 if ref else None
  ck(x['reference_share_units_differ']==changed,d+' '+t+' changing-share-unit warning')
  if t.endswith('-USD'):ck(day==(dt.date.fromisoformat(d)-dt.timedelta(days=1)).isoformat(),d+' '+t+' prior UTCdaily candle','sessions')
  if t=='^VIX':
   ck(x['chg_1s_pts']==round(close-prior[-2][1],2),d+' VIX pointchange')
   ck(x['chg_20s_pts']==round(close-prior[-21][1],2),d+' VIX20 pointchange')
 days=sorted(k for k in tr if k<d);last,old,five=tr[days[-1]],tr[days[-21]],tr[days[-6]];z=c['treasury']
 ck(z['prior_close_date']==days[-1] and z['obs20_earlier_date']==days[-21] and z['prior_5obs_date']==days[-6],d+' Treasurydates','treasury')
 for key,col in {'2y':'2 Yr','10y':'10 Yr','3m':'3 Mo','5y':'5 Yr','30y':'30 Yr','1y':'1 Yr'}.items():ck(z['prior_close_pct'][key]==f'{last[col]:.2f}%',d+' Treasuryyield'+key,'treasury')
 for key,a,b in [('spread_10y_2y_bps','10 Yr','2 Yr'),('spread_10y_3m_bps','10 Yr','3 Mo'),('spread_30y_10y_bps','30 Yr','10 Yr')]:ck(z[key]==bps(last[a],last[b]),d+' '+key,'treasury')
 for key,col in {'2y':'2 Yr','10y':'10 Yr','3m':'3 Mo','30y':'30 Yr'}.items():ck(z['chg_20obs_bps'][key]==bps(last[col],old[col]),d+'20obs'+key,'treasury')
 for key,col in {'2y':'2 Yr','10y':'10 Yr'}.items():
  ck(z['chg_5obs_bps'][key]==bps(last[col],five[col]),d+'5obs'+key,'treasury')
  ck(z['obs20_earlier_pct'][key]==f'{old[col]:.2f}%',d+'oldyield'+key,'treasury')
 ck(z['chg_20obs_bps']['spread']==bps(last['10 Yr'],last['2 Yr'])-bps(old['10 Yr'],old['2 Yr']),d+' spreadchange','treasury')
 ck(z['curve_shape']==shape(z['spread_10y_2y_bps']),d+' shape','treasury')
 ck(z['curve_move_20obs']==move(z['chg_20obs_bps']['2y'],z['chg_20obs_bps']['10y']),d+' curvemove','treasury')

suffix={'.WA':'XWAR','.DE':'XETR','.PA':'XPAR','.CO':'XCSE','.L':'XLON','.SW':'XSWX','.T':'XTKS','.KS':'XKRX','.SS':'XSHG','.HK':'XHKG','.AX':'XASX'}
indices={'^N225':'XTKS','^KS11':'XKRX','^TWII':'XTAI','^HSI':'XHKG','^AXJO':'XASX','^FTSE':'XLON','^GDAXI':'XETR','^FCHI':'XPAR','^STOXX':'XETR','^STOXX50E':'XETR'}
exceptions={'XTAI':{'2024-10-02','2024-10-03','2024-10-31'},'XKRX':{'2024-10-01'},'XHKG':{'2024-09-06'}}
calinventory={};calnotes=[];close_checks=0
for t,j in data.items():
 if t in fx or t.endswith(('=F','-USD')) or t=='DX-Y.NYB':continue
 code=indices.get(t) or next((v for s,v in suffix.items() if t.endswith(s)),'XNYS');cal=xc.get_calendar(code)
 first,last=j['rows'][0][0],j['rows'][-1][0]
 schedule=cal.schedule.loc[first:last]
 expected={idx.strftime('%Y-%m-%d') for idx in schedule.index}-exceptions.get(code,set())
 actual=set(dict(j['rows']))
 ck(expected==actual,t+' full calendar dates '+str(sorted(expected^actual)),'calendars')
 if expected!=actual:calnotes.append({'ticker':t,'calendar':code,'symmetric_difference':sorted(expected^actual)})
 if code not in calinventory:calinventory[code]={'closed_weekdays':sorted(set(dates)-{i.strftime('%Y-%m-%d') for i in cal.sessions_in_range('2024-10-01','2024-10-31') if i.strftime('%Y-%m-%d') not in exceptions.get(code,set())})}
 for d,c in cards.items():
  if t in skip or t not in c['markets']:continue
  eligible=[day for day in expected if day<d];target=max(eligible);x=c['markets'][t]
  ck(x['session']==target,d+' '+t+' independently latest exchange session','calendars')
  close_time=cal.session_close(target)
  ck(close_time.to_pydatetime()<dt.datetime.fromisoformat(d+'T00:00:00+00:00'),d+' '+t+' actual calendar close before cutoff','calendars');close_checks+=1

holidays=set(USFederalHolidayCalendar().holidays('2024-01-01','2024-10-31').strftime('%Y-%m-%d'))|{'2024-03-29'}
first=dt.date.fromisoformat(min(tr));last=dt.date(2024,10,31)
trex={str(first+dt.timedelta(days=n)) for n in range((last-first).days+1) if (first+dt.timedelta(days=n)).weekday()<5 and str(first+dt.timedelta(days=n)) not in holidays}
ck(set(tr)==trex,'Treasury full weekday federal-holiday calendar','treasury')
ck(cards['2024-10-15']['treasury']['prior_close_date']=='2024-10-11' and cards['2024-10-15']['markets']['^GSPC']['session']=='2024-10-14','ColumbusDay distinct Treasury/equity sessions','treasury')
# Independently read the official CSV and compare retained historical yields.
url='https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/2024/all?type=daily_treasury_yield_curve&field_tdr_date_value=2024&page&_format=csv'
raw=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=30).read()
(W/'independent_treasury_2024.csv').write_bytes(raw)
parsed={}
for row in csv.DictReader(io.StringIO(raw.decode())):
 day=dt.datetime.strptime(row['Date'],'%m/%d/%Y').date().isoformat()
 if day<='2024-10-31':parsed[day]={k:float(v) for k,v in row.items() if k!='Date' and v}
ck(parsed==tr,'Official Treasury independent CSV parity','treasury')
out={'status':'accepted' if not err else 'failed','passed':not err,'scope':'Independent offline recomputation from frozen October Yahoo histories/split event ledgers, exchange calendars and separate official Treasury CSV retrieval. Owner build/validate functions were not imported. Report prose and vendor spot-FX close finality are outside this receipt.','dates':dates,'checks':sum(counts.values()),'checks_by_scope':counts,'errors':err,'raw_symbols':len(data),'writer_symbols_per_card':sorted(set(len(c['markets']) for c in cards.values())),'market_fetch_failures':sum(x['status']!='ok' for x in fetch),'exchange_calendar_package':'exchange-calendars '+xc.__version__,'independent_exchange_close_timestamp_checks':close_checks,'calendar_inventory':calinventory,'calendar_discrepancies':calnotes,'exceptions':{k:sorted(v) for k,v in exceptions.items()},'card_sha256':{d:sha(R/'cards'/f'{d}.json') for d in dates},'data_sha256':{p.name:sha(p) for p in sorted((R/'data').glob('*.json'))},'action_sha256':{p.name:sha(p) for p in sorted((R/'audit').glob('actions_*.json'))},'treasury_independent_request':{'url':url,'response_sha256':hashlib.sha256(raw).hexdigest(),'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'parity':parsed==tr},'source_freeze_sha256':sha(R/'audit/source_freeze.json') if (R/'audit/source_freeze.json').exists() else None,'spot_fx_policy':'All seven numeric =X marks and returns absent from every writer card. DXY retained as an index. No vendor FX close is certified.','limitations':['Current-vintage Yahoo histories may contain later vendor revisions; original unrevised historical vintages are not certified.','Split ledgers are tested for mechanical display-unit restoration, including later events, and are not evidence for historical investment conclusions.','Full exchange calendars and actual close timestamps were checked for cash equities/indexes/rate proxies; futures and DXY were checked against latest bounded vendor observation dates, with no separate official settlement tape. Crypto is checked against prior completed UTC daily candles.','This receipt checks card infrastructure; it does not approve numbers, trade selection or claims in report prose.']}
(R/'audit/independent_market_review.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k not in ('data_sha256','action_sha256','card_sha256','calendar_inventory')},indent=2))
raise SystemExit(bool(err))
