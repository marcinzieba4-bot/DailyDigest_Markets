"""Independent bounded-input and exchange-calendar preflight for August2024 cards.
Does not import acquisition, card-building, or sanitizing code. No facts generated.
"""
from pathlib import Path
import csv,datetime as dt,json,math,hashlib
from decimal import Decimal
import exchange_calendars as xc
from pandas.tseries.holiday import USFederalHolidayCalendar
ROOT=Path(__file__).resolve().parent.parent
DATES=[dt.date(2024,8,n).isoformat() for n in range(1,32) if dt.date(2024,8,n).weekday()<5]
SUFFIX={'.WA':'XWAR','.DE':'XETR','.PA':'XPAR','.CO':'XCSE','.L':'XLON','.SW':'XSWX','.T':'XTKS','.KS':'XKRX','.SS':'XSHG','.HK':'XHKG','.AX':'XASX'}
INDICES={'^VIX':'XCBF','^NDX':'XNAS','^SOX':'XNAS','^N225':'XTKS','^KS11':'XKRX','^TWII':'XTAI','000001.SS':'XSHG','^HSI':'XHKG','^AXJO':'XASX','^FTSE':'XLON','^GDAXI':'XETR','^FCHI':'XPAR','^STOXX':'XETR','^STOXX50E':'XETR'}
FX={'EURUSD=X','JPY=X','AUDUSD=X','CNY=X','GBPUSD=X','PLN=X','EURPLN=X'}
errors=[];nchecks=0;gaps=[];suppressed=[];closurechecks=0;short=[]
def check(ok,msg):
 global nchecks
 nchecks+=1
 if not ok:errors.append(msg)
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bp(a,b):return int((Decimal(str(a))-Decimal(str(b)))*100)
def pct(a,b):return round((a/b-1)*100,2)
raw={j['ticker']:j for p in (ROOT/'data').glob('yf_*.json') for j in [read(p)]};cards={d:read(ROOT/'cards'/f'{d}.json') for d in DATES};tr=read(ROOT/'data/treasury_par.json')
check(len(raw)==289 and len(cards)==22,'Universe289raw22dates');check(set(raw)&{'NBIS','CRWV','SNDK'}==set(),'Unavailable names have no raw rows')
calinfo={}
for t,j in raw.items():
 rows=j['rows'];levels=dict(j['as_traded_rows']);check(rows==sorted(rows) and len(rows)==len(dict(rows)),t+' orderedunique');check(set(levels)==set(dict(rows)),t+' as-tradedparity');check(all('2024-07-01'<=day<'2024-08-30' and math.isfinite(v) and v>0 for day,v in rows),t+' boundedpositive');check(j['max_kept_date']=='2024-08-29',t+' boundlabel')
 source=Path(j['reuse_provenance']['source_file']);check(source.exists() and sha(source)==j['reuse_provenance']['source_file_sha256'],t+' frozenparenthash');old=read(source);check(rows==[r for r in old['rows'] if r[0]<'2024-08-30'] and j['as_traded_rows']==[r for r in old['as_traded_rows'] if r[0]<'2024-08-30'],t+' exactboundedreuse')
 acts=read(ROOT/'audit'/('actions_'+t.replace('^','_').replace('=','_').replace('.','_')+'.json'));check(acts['ticker']==t and acts['requests'][0]['sha256']==j['source_response_sha256'],t+' requesthash')
 for day,v in rows:
  expected=v*math.prod(e['factor'] for e in acts['events'] if e['date']>day);check(abs(expected-levels[day])<max(1e-5,abs(expected)*1e-7),t+day+' splitunits')
 if not t.endswith(('=F','=X','-USD')) and t!='DX-Y.NYB':
  code=INDICES.get(t) or next((v for k,v in SUFFIX.items() if t.endswith(k)),'XNYS');cal=xc.get_calendar(code);expected=cal.sessions_in_range(rows[0][0],'2024-08-29').strftime('%Y-%m-%d').tolist();missing=sorted(set(expected)-set(dict(rows)));extra=sorted(set(dict(rows))-set(expected));check(not extra,t+' unexpectedcashobservations')
  if missing:gaps.append({'ticker':t,'calendar':code,'missing':missing})
  check(missing==(['2024-08-01'] if t in {'^STOXX','^STOXX50E'} else []),t+' onlyknownprovidergaps')
  calinfo[t]=(cal,expected)
for d,c in cards.items():
 check(c['report_date']==d and c['cutoff_utc']==d+'T00:00:00Z',d+' identity');check(not any(t.endswith('=X') for t in c['markets']) and set(c['excluded_vendor_marks']['tickers'])==FX,d+' noFX');check(not set(c['markets'])&{'NBIS','CRWV','SNDK','^IRX','^TNX'},d+' excluded')
 expected_inventory=set()
 for t,j in raw.items():
  if t in FX|{'^IRX','^TNX'}:continue
  rows=[r for r in j['rows'] if r[0]<d]
  if not rows:continue
  exp=[day for day in calinfo[t][1] if day<d] if t in calinfo else None
  if exp and rows[-1][0]!=exp[-1]:
   check(t not in c['markets'] and t in c['excluded_instruments'],d+t+' missinglatestomitted');suppressed.append({'date':d,'ticker':t,'kind':'entireinstrument','reason':'latestexchangeobservationmissing'});continue
  expected_inventory.add(t);x=c['markets'][t];day,close=rows[-1];levels=dict(j['as_traded_rows']);check(x['session']==day<d,d+t+' latest');check(x['close']==(None if j.get('level_restriction') else f'{levels[day]:,.2f}'),d+t+' level')
  if exp:
   cal=calinfo[t][0];check(cal.session_close(exp[-1]).to_pydatetime()<dt.datetime.fromisoformat(d+'T00:00:00+00:00'),d+t+' realclosebeforecutoff');closurechecks+=1
  if t.endswith('-USD'):check(day==(dt.date.fromisoformat(d)-dt.timedelta(days=1)).isoformat(),d+t+' cryptoclose')
  for n in (1,5,20):
   enough=len(rows)>n;ref=rows[-n-1] if enough else None;expected_ref=exp[-n-1] if exp and len(exp)>n else ref[0] if ref else None;valid=ref is not None and expected_ref==ref[0]
   check(x[f'chg_{n}s_pct']==(pct(close,ref[1]) if valid else None),d+t+str(n)+' comparablepct');check(x[f'ref_{n}s_session']==(ref[0] if valid else None),d+t+str(n)+' exactref')
   if not valid and enough:suppressed.append({'date':d,'ticker':t,'kind':str(n)+'session','reason':'missingvendorobservation'});check(bool(x.get('vendor_gap_limitation')),d+t+str(n)+' gapdisclosed')
   if not enough:short.append({'date':d,'ticker':t,'horizon':n,'observations':len(rows)});check(bool(x.get('history_limitation')),d+t+str(n)+' shorthistorydisclosed')
  valid20=x['ref_20s_session'] is not None;ref=rows[-21] if valid20 else None;check(x['ref_20s_close']==(f'{levels[ref[0]]:,.2f}' if ref and not j.get('level_restriction') else None),d+t+' refprice')
  change=abs((levels[day]/close)/(levels[ref[0]]/ref[1])-1)>1e-6 if ref else None;check(x['reference_share_units_differ']==change,d+t+' unitsflag')
 check(set(c['markets'])==expected_inventory,d+' fullwriterinventory')
 days=sorted(k for k in tr if k<d);z=c['treasury'];last,old,five=tr[days[-1]],tr[days[-21]],tr[days[-6]];check(z['prior_close_date']==days[-1] and z['obs20_earlier_date']==days[-21],d+' treasurydate')
 for key,col in {'2y':'2 Yr','10y':'10 Yr','3m':'3 Mo','5y':'5 Yr','30y':'30 Yr','1y':'1 Yr'}.items():check(z['prior_close_pct'][key]==f'{last[col]:.2f}%',d+' treasury'+key)
 for key,col in {'2y':'2 Yr','10y':'10 Yr','3m':'3 Mo','30y':'30 Yr'}.items():check(z['chg_20obs_bps'][key]==bp(last[col],old[col]),d+' bps'+key)
 sp=bp(last['10 Yr'],last['2 Yr']);check(z['spread_10y_2y_bps']==sp and z['chg_20obs_bps']['spread']==sp-bp(old['10 Yr'],old['2 Yr']),d+' spread');check(z['curve_shape']==('inverted' if sp<0 else 'flat' if sp==0 else 'positive but very flat' if sp<25 else 'positively sloped' if sp<60 else 'moderately steep' if sp<100 else 'steep'),d+' curveshape')
parsed={}
for row in csv.DictReader((ROOT/'audit'/'independent_treasury_2024_through_2024-08-29.csv').open()):
 day=dt.datetime.strptime(row['Date'],'%m/%d/%Y').date().isoformat()
 if day<'2024-08-30':parsed[day]={k:float(v) for k,v in row.items() if k!='Date' and v}
check(parsed==tr,'Official independentlyretrievedTreasuryCSVexactparity')
check(cards['2024-08-05']['markets']['^VIX']['session']=='2024-08-02' and cards['2024-08-05']['markets']['^VIX']['close']=='23.39','Aug5priorFridayVIX');check(cards['2024-08-06']['markets']['^VIX']['close']=='38.57','Aug6Aug5VIXclose');check(cards['2024-08-09']['markets']['MSTR']['reference_share_units_differ'] is True and cards['2024-08-08']['markets']['MSTR']['reference_share_units_differ'] is False,'MSTRAug8splitboundary');check(float(cards['2024-08-08']['markets']['MSTR']['close'].replace(',',''))>1000 and float(cards['2024-08-09']['markets']['MSTR']['close'].replace(',',''))<200,'MSTRas-tradedunitsrestored')
result={'passed':not errors,'assertions':nchecks,'errors':errors,'dates':DATES,'raw_symbols':len(raw),'instruments_per_card':sorted({len(c['markets']) for c in cards.values()}),'exchange_calendar_package':'exchange-calendars '+xc.__version__,'actual_exchange_close_checks':closurechecks,'raw_provider_gaps':gaps,'suppressed_metrics':suppressed,'short_inception_histories':short,'future_price_rows_retained':0,'final_retained_exclusive':'2024-08-30','reused_frozen_market_source':'September2024 infrastructure,strictlytrimmed','spot_fx_policy':'All numerical spotFX marks/returns excluded;DXY retained','split_policy':'Mechanicallyrestored historicalshareunits,comparablepctreturns;futureeventsare audit-only','treasury_parity':'Independent official2024CSVmatchesall167retainedrows','card_sha256':{d:sha(ROOT/'cards'/f'{d}.json') for d in DATES},'limitations':['Current-vintage histories can include vendorcorrections;no originalunrevisedvintagecertified.','Two STOXXhistories lackAug1;affectedlatest/horizonmetrics suppressed;no filledprices.','Futures/DXYuse boundedvendorobservations;no independentofficialsettlementtape.','Infrastructurepreflightdoesnotverifyreportprose.']}
(ROOT/'audit'/'market_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ['card_sha256','suppressed_metrics','short_inception_histories']},ensure_ascii=False,indent=2));print('Suppressedmetrics',len(suppressed),'shorthistorymetrics',len(short));raise SystemExit(bool(errors))
