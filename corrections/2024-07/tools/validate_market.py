"""Recompute July2024 market cards from bounded raw inputs and independent exchange calendars.
No acquisition/card-builder/sanitizer imports, no filled observations, no article/prose review.
"""
from pathlib import Path
import json,datetime as dt,hashlib,math,gzip
from decimal import Decimal
from zoneinfo import ZoneInfo
import exchange_calendars as xc
ROOT=Path(__file__).resolve().parent.parent
DATES=[dt.date(2024,7,n).isoformat() for n in range(1,32) if dt.date(2024,7,n).weekday()<5]
FIRST,LAST='2024-05-01','2024-07-30'
SUFFIX={'.WA':'XWAR','.DE':'XETR','.PA':'XPAR','.CO':'XCSE','.L':'XLON','.SW':'XSWX','.T':'XTKS','.KS':'XKRX','.SS':'XSHG','.HK':'XHKG','.AX':'XASX'}
INDICES={'^VIX':'XCBF','^NDX':'XNAS','^SOX':'XNAS','^N225':'XTKS','^KS11':'XKRX','^TWII':'XTAI','000001.SS':'XSHG','^HSI':'XHKG','^AXJO':'XASX','^FTSE':'XLON','^GDAXI':'XETR','^FCHI':'XPAR','^STOXX':'XETR','^STOXX50E':'XETR'}
FX={'EURUSD=X','JPY=X','AUDUSD=X','CNY=X','GBPUSD=X','PLN=X','EURPLN=X'}
errors=[];checks=0;gaps=[];suppressed=[];short=[];closures=0
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def ck(ok,msg):
 global checks
 checks+=1
 if not ok:errors.append(msg)
def bp(a,b):
 x=(Decimal(str(a))-Decimal(str(b)))*100
 ck(x==x.to_integral_value(),'Whole Treasury basis points');return int(x)
def pct(a,b):return round((a/b-1)*100,2)
def movement(a,b):
 if abs(a)<4 and abs(b)<4:return 'little changed'
 if a==b:return 'parallel rally (both down equally; spread unchanged)' if a<0 else 'parallel selloff (both up equally; spread unchanged)'
 if a>0 and b>0:return 'bear steepening (both up, 10Y up more)' if b>a else 'bear flattening (both up, 2Y up more)'
 if a<0 and b<0:return 'bull steepening (both down, 2Y down more)' if b>a else 'bull flattening (both down, 10Y down more)'
 if b>0:return 'steepening (10Y up, 2Y down/flat)'
 if a>0:return 'flattening (2Y up, 10Y down/flat)'
 if b<0:return 'flattening (10Y down, 2Y up/flat)'
 return 'steepening (2Y down, 10Y up/flat)'
raw={j['ticker']:j for p in (ROOT/'data').glob('yf_*.json') for j in [read(p)]}
tr=read(ROOT/'data/treasury_par.json');cards={d:read(ROOT/'cards'/f'{d}.json') for d in DATES};retention=read(ROOT/'audit/market_raw_retention.json');rr={x['ticker']:x for x in retention['sources']};calendars={}
ck(len(raw)==289 and len(cards)==23,'Expected289raw/23cards');ck(not set(raw)&{'NBIS','CRWV','SNDK'},'Unavailable raw identities absent');ck(max(tr)==LAST and all(d<=LAST for d in tr),'Treasury bounded')
for t,j in raw.items():
 rows=j['rows'];levels=dict(j['as_traded_rows']);ck(rows==sorted(rows) and len(rows)==len(dict(rows)),t+' orderedunique');ck(set(levels)==set(dict(rows)),t+' leveldateparity');ck(all(FIRST<=d<=LAST and math.isfinite(v) and v>0 for d,v in rows),t+' boundedpositive');ck(j['max_kept_date']==LAST,t+' finalboundlabel')
 p=ROOT/j['retained_source_path'];blob=gzip.decompress(p.read_bytes());record=rr[t];ck(hashlib.sha256(blob).hexdigest()==j['retained_source_sha256']==record['retained_uncompressed_sha256'] and sha(p)==record['retained_gzip_sha256'],t+' retainedhash');ck(record['original_network_response_sha256']==j['source_response_sha256'],t+' networkhashidentity')
 source=json.loads(blob)['chart']['result'][0];ck(set(source['meta'])<={'currency','symbol','exchangeName','fullExchangeName','instrumentType','timezone','exchangeTimezoneName','firstTradeDate'},t+' no live metadata');parsed=[]
 ck(len(source['timestamp'])==len(source['indicators']['quote'][0]['close']),t+' retainedarraylength')
 ck(all(FIRST<=dt.datetime.fromtimestamp(ts,ZoneInfo(j['tz'])).date().isoformat()<=LAST for ts in source['timestamp']),t+' retainedsourceharddatebound')
 ck(record['retained_historical_pairs_unchanged'] is True,t+' retainedpairparitydisclosure')
 for ts,value in zip(source['timestamp'],source['indicators']['quote'][0]['close']):
  if value is None:continue
  d=dt.datetime.fromtimestamp(ts,ZoneInfo(j['tz'])).date().isoformat()
  if FIRST<=d<=LAST:parsed.append([d,round(float(value),8)])
 ck(parsed==rows,t+' exactretainedreparse');actions=read(ROOT/'audit'/('actions_'+t.replace('^','_').replace('=','_').replace('.','_')+'.json'));ck(actions['ticker']==t and actions['requests'][0]['sha256']==j['source_response_sha256'],t+' actionprovenance')
 for d,v in rows:
  expected=v*math.prod(e['factor'] for e in actions['events'] if e['date']>d);ck(abs(expected-levels[d])<max(1e-5,abs(expected)*1e-7),t+d+' restoredsplitunits')
 if not t.endswith(('=F','=X','-USD')) and t!='DX-Y.NYB':
  code=INDICES.get(t) or next((v for k,v in SUFFIX.items() if t.endswith(k)),'XNYS');cal=xc.get_calendar(code);expected=cal.sessions_in_range(rows[0][0],LAST).strftime('%Y-%m-%d').tolist();missing=sorted(set(expected)-set(dict(rows)));extra=sorted(set(dict(rows))-set(expected));ck(not extra,t+' unexpectedcashdate');calendars[t]=(cal,expected)
  if missing:gaps.append({'ticker':t,'calendar':code,'missing':missing})
for d,c in cards.items():
 cutoff=dt.datetime.fromisoformat(d+'T00:00:00+00:00');ck(c['report_date']==d and c['cutoff_utc']==d+'T00:00:00Z',d+' identity');ck(not any(t.endswith('=X') for t in c['markets']) and set(c['excluded_vendor_marks']['tickers'])==FX,d+' FXexcluded');ck(not set(c['markets'])&{'NBIS','CRWV','SNDK','^IRX','^TNX'},d+' unavailableexcluded');inventory=set()
 for t,j in raw.items():
  if t in FX|{'^IRX','^TNX'}:continue
  rows=[r for r in j['rows'] if r[0]<d]
  if not rows:
   ck(t not in c['markets'] and t in c['unavailable_symbols'],d+t+' prelistingabsent');continue
  exp=[x for x in calendars[t][1] if x<d] if t in calendars else None
  if exp and rows[-1][0]!=exp[-1]:
   ck(t not in c['markets'] and t in c['excluded_instruments'],d+t+' missinglatestomitted');suppressed.append({'date':d,'ticker':t,'kind':'entireinstrument'});continue
  inventory.add(t);x=c['markets'][t];day,v=rows[-1];levels=dict(j['as_traded_rows']);ck(x['session']==day<d,d+t+' latest');ck(x['close']==(None if j.get('level_restriction') else f'{levels[day]:,.2f}'),d+t+' as-tradedlevel');ck(x['currency']==j['currency'] and x['tz']==j['tz'] and x['return_unit']=='%',d+t+' identityunits')
  if t.startswith('^') or t in {'DX-Y.NYB','000001.SS'}:ck(x['level_unit']=='index points',d+t+' indexunit')
  if exp:ck(calendars[t][0].session_close(exp[-1]).to_pydatetime()<cutoff,d+t+' actualclosebeforecutoff');closures+=1
  if t.endswith('-USD'):ck(day==(dt.date.fromisoformat(d)-dt.timedelta(days=1)).isoformat(),d+t+' completedUTCday')
  for n in (1,5,20):
   ref=rows[-n-1] if len(rows)>n else None;expected_ref=exp[-n-1] if exp and len(exp)>n else ref[0] if ref else None;valid=ref is not None and ref[0]==expected_ref
   ck(x[f'ref_{n}s_session']==(ref[0] if valid else None),d+t+str(n)+' reference');ck(x[f'chg_{n}s_pct']==(pct(v,ref[1]) if valid else None),d+t+str(n)+' comparereturn')
   if not valid:
    if ref:suppressed.append({'date':d,'ticker':t,'kind':str(n)+'session'});ck(bool(x.get('vendor_gap_limitation')),d+t+str(n)+' gapdisclosed')
    else:short.append({'date':d,'ticker':t,'horizon':n,'observations':len(rows)});ck(bool(x.get('history_limitation')),d+t+str(n)+' shortdisclosed')
  ref=rows[-21] if x['ref_20s_session'] is not None else None;ck(x['ref_20s_close']==(f'{levels[ref[0]]:,.2f}' if ref and not j.get('level_restriction') else None),d+t+' refprice');flag=abs((levels[day]/v)/(levels[ref[0]]/ref[1])-1)>1e-6 if ref else None;ck(x['reference_share_units_differ']==flag,d+t+' unitsflag')
 ck(set(c['markets'])==inventory,d+' inventory');days=sorted(z for z in tr if z<d);last,old,five=tr[days[-1]],tr[days[-21]],tr[days[-6]];x=c['treasury'];ck(x['prior_close_date']==days[-1] and x['obs20_earlier_date']==days[-21] and x['prior_5obs_date']==days[-6],d+' Treasuryreferences')
 for key,col in {'2y':'2 Yr','10y':'10 Yr','3m':'3 Mo','5y':'5 Yr','30y':'30 Yr','1y':'1 Yr'}.items():ck(x['prior_close_pct'][key]==f'{last[col]:.2f}%',d+' Treasury'+key)
 for key,col in {'2y':'2 Yr','10y':'10 Yr','3m':'3 Mo','30y':'30 Yr'}.items():ck(x['chg_20obs_bps'][key]==bp(last[col],old[col]),d+' bps'+key)
 for key,col in {'2y':'2 Yr','10y':'10 Yr'}.items():ck(x['chg_5obs_bps'][key]==bp(last[col],five[col]),d+' fivebps'+key)
 sp=bp(last['10 Yr'],last['2 Yr']);ck(x['spread_10y_2y_bps']==sp and x['chg_20obs_bps']['spread']==sp-bp(old['10 Yr'],old['2 Yr']),d+' spread');ck(x['curve_shape']==('inverted' if sp<0 else 'flat' if sp==0 else 'positive but very flat' if sp<25 else 'positively sloped' if sp<60 else 'moderately steep' if sp<100 else 'steep'),d+' shape');ck(x['curve_move_20obs']==movement(x['chg_20obs_bps']['2y'],x['chg_20obs_bps']['10y']),d+' movement')
for d in ('2024-07-04','2024-07-05'):
 ck(cards[d]['markets']['^GSPC']['session']=='2024-07-03' and cards[d]['treasury']['prior_close_date']=='2024-07-03',d+' holidaypriorclose')
ck('ETHA' not in cards['2024-07-23']['markets'] and cards['2024-07-24']['markets']['ETHA']['session']=='2024-07-23','ETHAinitialeligibleedition');ck(cards['2024-07-24']['markets']['ETHA']['chg_1s_pct'] is None,'ETHAnoinventedinitialreturn')
ck(cards['2024-07-15']['markets']['AVGO']['reference_share_units_differ'] is False and cards['2024-07-16']['markets']['AVGO']['reference_share_units_differ'] is True,'AVGOsplitboundary');ck(cards['2024-07-01']['markets']['CMG']['reference_share_units_differ'] is True,'CMGlookbacksplit');ck(float(cards['2024-07-01']['markets']['MSTR']['close'].replace(',',''))>1000,'MSTRas-tradedrestoration')
result={'passed':not errors,'assertions':checks,'errors':errors,'dates':DATES,'raw_symbols':len(raw),'instruments_per_card':sorted({len(c['markets']) for c in cards.values()}),'exchange_calendar_package':'exchange-calendars '+xc.__version__,'actual_exchange_close_checks':closures,'raw_provider_gaps':gaps,'suppressed_metrics':suppressed,'short_inception_histories':short,'future_price_rows_retained':0,'first_retained_inclusive':FIRST,'final_retained_inclusive':LAST,'fresh_acquisition':True,'card_sha256':{d:sha(ROOT/'cards'/f'{d}.json') for d in DATES},'source_retention_sha256':sha(ROOT/'audit/market_raw_retention.json'),'tool_sha256':{p.name:sha(p) for p in (ROOT/'tools').glob('*.py') if p.name in {'fetch_market.py','build_cards.py','validate_market.py','market_calendar_policy.py'}},'limitations':['Current-vintage Yahoo/Treasury history may contain vendor corrections; original unrevised publication vintage is not asserted.','Futures and DXY use bounded vendor observations without an independent official settlement tape.','XCBF package July3 timing is a conservative before-cutoff eligibility check, not certification of the exact VIX print time; independent review records the primary Cboe early-close notice.','No source headline or report prose is validated here.']}
(ROOT/'audit/market_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in {'card_sha256','suppressed_metrics','short_inception_histories','tool_sha256'}},indent=2));print('suppressed',len(suppressed),'short',len(short));raise SystemExit(bool(errors))
