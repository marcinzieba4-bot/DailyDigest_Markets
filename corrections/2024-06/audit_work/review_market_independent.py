"""Independent June2024 market infrastructure review; read-only outside audit_work.

No acquisition/card/sanitizer code is imported. Exchange calendars, raw bounded
Yahoo responses, action ledgers, card fields and separately fetched Treasury data
are recomputed independently. Default runs require all20cards and raw retention.
Network samples are bounded; only later split metadata is kept, never later prices.
"""
from pathlib import Path
import argparse,ast,csv,datetime as dt,gzip,hashlib,io,json,math,urllib.parse,urllib.request,time
from decimal import Decimal
from zoneinfo import ZoneInfo
from collections import Counter
import exchange_calendars as xc
from pandas.tseries.holiday import USFederalHolidayCalendar
ROOT=Path('/workspace/work/june2024');WORK=ROOT/'audit_work';UTC=dt.timezone.utc
START,END,LAST='2024-04-01','2024-06-28','2024-06-27'
DATES=[dt.date(2024,6,n).isoformat() for n in range(3,29) if dt.date(2024,6,n).weekday()<5]
FX={'EURUSD=X','JPY=X','AUDUSD=X','CNY=X','GBPUSD=X','PLN=X','EURPLN=X'}
SUFFIX={'.WA':'XWAR','.DE':'XETR','.PA':'XPAR','.CO':'XCSE','.L':'XLON','.SW':'XSWX','.T':'XTKS','.KS':'XKRX','.SS':'XSHG','.HK':'XHKG','.AX':'XASX'}
INDEX={'^VIX':'XCBF','^NDX':'XNAS','^SOX':'XNAS','^N225':'XTKS','^KS11':'XKRX','^TWII':'XTAI','000001.SS':'XSHG','^HSI':'XHKG','^AXJO':'XASX','^FTSE':'XLON','^GDAXI':'XETR','^FCHI':'XPAR','^STOXX':'XETR','^STOXX50E':'XETR'}
FUTURES={'CL=F':'USD/bbl','BZ=F':'USD/bbl','NG=F':'USD/MMBtu','GC=F':'USD/oz','SI=F':'USD/oz','HG=F':'USD/lb','PL=F':'USD/oz','ZS=F':'US cents/bu'}
TREASURY_URL='https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/2024/all?type=daily_treasury_yield_curve&field_tdr_date_value=2024&page&_format=csv'
counts=Counter();errors=[];warnings=[]
def ck(ok,msg,group='arithmetic'):
 counts[group]+=1
 if not ok:errors.append(msg)
def load(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def name(t):return t.replace('^','_').replace('=','_').replace('.','_')
def epoch(d):return int(dt.datetime.fromisoformat(d+'T00:00:00+00:00').timestamp())
def pct(a,b):return round((a/b-1)*100,2)
def canonical_sha(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def bp(a,b):
 v=(Decimal(str(a))-Decimal(str(b)))*100;ck(v==v.to_integral_value(),'Treasury precision','treasury');return int(v)
def shape(v):return 'inverted' if v<0 else 'flat' if v==0 else 'positive but very flat' if v<25 else 'positively sloped' if v<60 else 'moderately steep' if v<100 else 'steep'
def move(a,b):
 if max(abs(a),abs(b))<4:return 'little changed'
 if a==b:return 'parallel rally (both down equally; spread unchanged)' if a<0 else 'parallel selloff (both up equally; spread unchanged)'
 if a>0 and b>0:return 'bear steepening (both up, 10Y up more)' if b>a else 'bear flattening (both up, 2Y up more)'
 if a<0 and b<0:return 'bull steepening (both down, 2Y down more)' if b>a else 'bull flattening (both down, 10Y down more)'
 if b>0:return 'steepening (10Y up, 2Y down/flat)'
 if a>0:return 'flattening (2Y up, 10Y down/flat)'
 if b<0:return 'flattening (10Y down, 2Y up/flat)'
 return 'steepening (2Y down, 10Y up/flat)'
def universe():
 tree=ast.parse((ROOT/'tools/fetch_market.py').read_text())
 for node in tree.body:
  if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='UNIVERSE' for t in node.targets):return ast.literal_eval(node.value)
 raise ValueError('No declared universe')
def request(url):
 for attempt in range(3):
  try:
   with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=35) as r:return r.read()
  except Exception:
   if attempt==2:raise
   time.sleep(attempt+1)
def independent_treasury(offline):
 dest=WORK/'independent_treasury_through_2024-06-27.csv';meta=WORK/'independent_treasury_request.json'
 if offline:
  receipt=load(meta);ck(receipt['retained_csv_sha256']==sha(dest),'Independent Treasury CSV hash','network');raw=dest.read_bytes()
 else:
  raw=request(TREASURY_URL);reader=csv.DictReader(io.StringIO(raw.decode()));fields=reader.fieldnames;retained=[];removed=[]
  for row in reader:
   day=dt.datetime.strptime(row['Date'],'%m/%d/%Y').date().isoformat()
   (retained if START<=day<=LAST else removed).append(row)
  text=io.StringIO();writer=csv.DictWriter(text,fieldnames=fields);writer.writeheader()
  for row in sorted(retained,key=lambda r:dt.datetime.strptime(r['Date'],'%m/%d/%Y')):writer.writerow(row)
  dest.write_text(text.getvalue());receipt={'url':TREASURY_URL,'retrieved_at_utc':dt.datetime.now(UTC).isoformat(),'response_sha256':hashlib.sha256(raw).hexdigest(),'retained_csv_sha256':sha(dest),'retained_first_date':START,'retained_last_date':LAST,'retained_count':len(retained),'removed_count':len(removed),'retention':'Exact source CSV field strings for observations April1 throughJune27 retained; all out-of-range annual-response rows discarded'};dump(meta,receipt);raw=dest.read_bytes()
 rows={}
 for row in csv.DictReader(io.StringIO(raw.decode())):
  day=dt.datetime.strptime(row['Date'],'%m/%d/%Y').date().isoformat()
  ck(START<=day<=LAST and day not in rows,'Independent Treasury bounded unique date '+day,'network')
  rows[day]={k:float(v) for k,v in row.items() if k!='Date' and v}
 return rows,receipt

def sample_yahoo(t,offline):
 dest=WORK/'independent_yahoo_samples'/(name(t)+'.json')
 if offline:return load(dest)
 historical='https://query1.finance.yahoo.com/v8/finance/chart/'+urllib.parse.quote(t,safe='')+f'?period1={epoch(START)}&period2={epoch(END)}&interval=1d&events=div,splits'
 raw=request(historical);r=json.loads(raw)['chart']['result'][0];zone=ZoneInfo(r['meta']['exchangeTimezoneName']);rows=[]
 for ts,c in zip(r.get('timestamp',[]),r['indicators']['quote'][0]['close']):
  day=dt.datetime.fromtimestamp(ts,zone).date().isoformat()
  if c is not None and START<=day<=LAST:rows.append([day,round(float(c),8)])
 action_url='https://query1.finance.yahoo.com/v8/finance/chart/'+urllib.parse.quote(t,safe='')+f'?period1={epoch(END)}&period2={int(dt.datetime.now(UTC).timestamp())}&interval=1d&events=splits'
 later_raw=request(action_url);later=json.loads(later_raw)['chart']['result'][0];events={**r.get('events',{}).get('splits',{}),**later.get('events',{}).get('splits',{})};actions=[]
 for e in events.values():actions.append({'date':dt.datetime.fromtimestamp(e['date'],zone).date().isoformat(),'factor':float(e['numerator'])/float(e['denominator'])})
 identity={k:v for k,v in r['meta'].items() if k in {'currency','symbol','exchangeName','fullExchangeName','instrumentType','firstTradeDate','timezone','exchangeTimezoneName'}}
 result={'ticker':t,'identity_meta':identity,'requests':[{'url':historical,'response_sha256':hashlib.sha256(raw).hexdigest()},{'url':action_url,'response_sha256':hashlib.sha256(later_raw).hexdigest()}],'retrieved_at_utc':dt.datetime.now(UTC).isoformat(),'rows':rows,'actions':sorted(actions,key=lambda e:e['date']),'retention':'Historical rows only throughJune27; later response retained as split-event metadata only, no later prices or current metadata'};dump(dest,result);return result

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--offline',action='store_true');ap.add_argument('--write-acceptance',action='store_true');args=ap.parse_args()
 missing=[d for d in DATES if not (ROOT/'cards'/f'{d}.json').exists()]
 if missing or not (ROOT/'audit/market_raw_retention.json').exists():raise SystemExit('Not ready: require20cards and raw retention receipt; missing '+str(missing))
 data={j['ticker']:j for p in (ROOT/'data').glob('yf_*.json') for j in [load(p)]};cards={d:load(ROOT/'cards'/f'{d}.json') for d in DATES};tr=load(ROOT/'data/treasury_par.json');declared=universe();fetch=load(ROOT/'audit/market_fetch.json');retention=load(ROOT/'audit/market_raw_retention.json')
 ck(len(DATES)==20 and len(set(declared))==len(declared),'20dates and unique universe','inventory');ck(set(data)==set(declared)-{'NBIS'},'Exact declared raw universe except haltedNBIS','inventory');ck({r['ticker'] for r in fetch}==set(declared),'Complete fetch inventory','inventory');ck(all(r['status']==('unavailable' if r['ticker']=='NBIS' else 'ok') for r in fetch),'No unexpected fetch failures','inventory');ck(not {'NBIS','CRWV','SNDK','ETHA'}&set(data) and 'ETHA' not in declared,'No unavailable or pre-listing raw instruments','inventory');ck(len(data)==len(list((ROOT/'data').glob('yf_*.json'))),'One raw normalized file per ticker','inventory');ck(set(p.name for p in (ROOT/'cards').glob('*.json'))=={d+'.json' for d in DATES},'No extra dated cards','inventory')
 retained_sources={x['ticker']:x for x in retention['sources']};ck(set(retained_sources)==set(data),'Exact retained-response inventory','provenance')
 calendars={};gaps=[];raw_paths={};action_paths={};raw_sample_checks=0
 for t,j in sorted(data.items()):
  p=ROOT/'data'/('yf_'+name(t)+'.json');raw_path=ROOT/'audit/market_raw'/(name(t)+'.json.gz');action_path=ROOT/'audit'/('actions_'+name(t)+'.json');raw_paths[t]=raw_path;action_paths[t]=action_path
  rows=j['rows'];levels=dict(j['as_traded_rows']);ck(rows==sorted(rows) and len(rows)==len(dict(rows)),t+' sorted unique rows','raw');ck(set(dict(rows))==set(levels),t+' share-unit date parity','raw');ck(all(START<=d<=LAST and isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>0 for d,v in rows+j['as_traded_rows']),t+' bounded finite prices','raw');ck(j['max_kept_date']==LAST,t+' declared retention bound','raw')
  params=urllib.parse.parse_qs(urllib.parse.urlsplit(j['source_url']).query);ck(params.get('period1')==[str(epoch(START))] and params.get('period2')==[str(epoch(END))],t+' physical request bounds','provenance');ck(urllib.parse.unquote(urllib.parse.urlsplit(j['source_url']).path)=='/v8/finance/chart/'+t,t+' source identity','provenance')
  action=load(action_path);ck(action['ticker']==t and action['requests'][0]['url']==j['source_url'] and action['requests'][0]['sha256']==j['source_response_sha256'],t+' action/request identity','provenance');ck(not {'rows','prices','timestamp','indicators'}&set(action),t+' action ledger has no later prices','provenance');ck(action['events']==sorted(action['events'],key=lambda e:e['date']) and len({e['date'] for e in action['events']})==len(action['events']),t+' ordered unique split events','splits');ck(all(math.isfinite(e['factor']) and e['factor']>0 for e in action['events']),t+' positive finite split factors','splits')
  exact_inputs=action.get('exact_action_inputs',[]);ck(len(exact_inputs)==len(action['requests'])==2,t+' retains both exact split metadata inputs','provenance');exact_events={}
  for source,request_meta in zip(exact_inputs,action['requests']):
   ck(source['request']==request_meta,t+' split input request hash binding','provenance');ck(set(source['retained_identity_meta'])<={'currency','symbol','exchangeName','fullExchangeName','instrumentType','firstTradeDate','timezone','exchangeTimezoneName'} and source['retained_identity_meta'].get('symbol')==t,t+' split-only response identity metadata','provenance');ck(not {'rows','prices','timestamp','indicators'}&set(source),t+' split-only input contains no price arrays','provenance');ck(isinstance(source['discarded_price_observations'],int) and source['discarded_price_observations']>=0,t+' discarded later observation count','provenance');exact_events.update(source['retained_exact_split_events'])
  rederived=[{'date':dt.datetime.fromtimestamp(e['date'],ZoneInfo(j['tz'])).date().isoformat(),'factor':float(e['numerator'])/float(e['denominator']),'ratio':e.get('splitRatio')} for e in exact_events.values()]
  ck(sorted(rederived,key=lambda e:e['date'])==action['events'],t+' exact split metadata independently reproduces ledger','splits')
  for d,v in rows:
   factor=math.prod(e['factor'] for e in action['events'] if e['date']>d);ck(abs(v*factor-levels[d])<=max(1e-5,abs(levels[d])*1e-7),t+d+' reconstructed units','splits')
  rr=retained_sources[t];retained_bytes=gzip.decompress(raw_path.read_bytes());ck(rr['path']==str(raw_path.relative_to(ROOT)) and rr['retained_gzip_sha256']==sha(raw_path) and rr['retained_uncompressed_sha256']==hashlib.sha256(retained_bytes).hexdigest(),t+' retained derivative byte hashes','provenance');ck(rr['original_network_response_sha256']==j['source_response_sha256'] and j['retained_source_path']==rr['path'] and j['retained_source_sha256']==hashlib.sha256(retained_bytes).hexdigest(),t+' original versus retained provenance hashes','provenance');ck(rr.get('retained_historical_pairs_unchanged',rr.get('historical_timestamp_and_close_arrays_unchanged')) is True,t+' retention declares unmodified retained historical pairs','provenance')
  retained=load(raw_path);result=retained['chart']['result'][0] if 'chart' in retained else retained;meta=result['meta'];ck(set(meta)<={'currency','symbol','exchangeName','fullExchangeName','instrumentType','firstTradeDate','timezone','exchangeTimezoneName'},t+' independently allowed metadata only','provenance');ck(set(meta)==set(rr['retained_meta_fields']) and not set(rr['removed_meta_fields'])&set(meta),t+' exact sanitized metadata fields','provenance');ck(set(result['indicators'])=={'quote'} and set(result['indicators']['quote'][0])=={'close'},t+' retained only historical close indicator','raw');ck(meta['exchangeTimezoneName']==j['tz'] and meta.get('currency','')==j['currency'],t+' retained timezone/currency','raw');ck(not {'regularMarketPrice','regularMarketTime','chartPreviousClose','previousClose','fiftyTwoWeekHigh','fiftyTwoWeekLow','regularMarketDayHigh','regularMarketDayLow','regularMarketVolume'}&set(meta),t+' no current price metadata','raw')
  ck(rr.get('removed_out_of_scope_observation_count',0)>=0 and not (rr.get('removed_out_of_scope_observation_count',0)>0 and rr.get('historical_timestamp_and_close_arrays_unchanged')),t+' truthful clipping declaration','provenance')
  removed=rr.get('removed_out_of_scope_observations',[]);ck(rr.get('first_retained_inclusive')==START and rr.get('final_retained_inclusive')==LAST,t+' receipt exact retained range','provenance');ck(len(removed)==rr['removed_out_of_scope_observation_count'] and all(set(e)=={'timestamp','exchange_local_date'} and e['exchange_local_date']==dt.datetime.fromtimestamp(e['timestamp'],ZoneInfo(j['tz'])).date().isoformat() and not START<=e['exchange_local_date']<=LAST for e in removed),t+' exact discarded dates without discarded prices','provenance');ck(set(rr.get('discarded_quote_fields',[]))=={'open','high','low','volume'} and 'adjclose' in rr.get('discarded_indicator_fields',[]),t+' raw retention drops adjusted/dividend and other price fields','provenance')
  rawrows=[];zone=ZoneInfo(meta['exchangeTimezoneName']);times=result.get('timestamp',[]);closes=result['indicators']['quote'][0]['close'];ck(len(times)==len(closes),t+' raw timestamp parity','raw')
  for ts,v in zip(times,closes):
   d=dt.datetime.fromtimestamp(ts,zone).date().isoformat();ck(START<=d<=LAST,t+d+' bounded retained rawbar','raw')
   if v is not None:
    ck(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>0,t+d+' valid retained close','raw');rawrows.append([d,round(float(v),8)])
  ck(all(START<=dt.datetime.fromtimestamp(e['date'],zone).date().isoformat()<=LAST for e in result.get('events',{}).get('splits',{}).values()),t+' bounded retained raw split metadata','raw');ck(meta.get('symbol')==t,t+' exact retained symbol identity','provenance');ck(rawrows==rows,t+' independently reparsed bounded raw rows','raw');ck(rr.get('retained_last_exchange_local_date',rawrows[-1][0])==rawrows[-1][0],t+' receipt last observation date','provenance');raw_sample_checks+=len(rawrows)
  if not t.endswith(('=F','=X','-USD')) and t!='DX-Y.NYB':
   code=INDEX.get(t) or next((v for suffix,v in SUFFIX.items() if t.endswith(suffix)),'XNYS');cal=xc.get_calendar(code);expected=cal.sessions_in_range(rows[0][0],LAST).strftime('%Y-%m-%d').tolist();extra=sorted(set(dict(rows))-set(expected));missing=sorted(set(expected)-set(dict(rows)));ck(not extra,t+' no bars on closed cash session','calendar')
   if missing:gaps.append({'ticker':t,'calendar':code,'missing':missing})
   calendars[t]=(cal,expected,code)
  if t in {'CMCSA','WDC'}:ck(bool(j.get('level_restriction')),t+' distribution level restriction','splits')
 ck(all(START<=d<=LAST for d in tr),'Treasury observations inside bounded window','treasury')
 treasury_source=load(ROOT/'audit/treasury_source.json');treasury_csv=ROOT/'audit/treasury_retained.csv';ck(treasury_source['source_url']==TREASURY_URL and treasury_source.get('retained_exact_cell_strings') is True and treasury_source['retained_csv_sha256']==sha(treasury_csv),'Treasury exact retained CSV hash binding','provenance');treasury_rows={}
 for row in csv.DictReader(treasury_csv.open()):
  day=dt.datetime.strptime(row['Date'],'%m/%d/%Y').date().isoformat();ck(START<=day<=LAST and day not in treasury_rows,'Retained Treasury bounded unique exact input '+day,'treasury');treasury_rows[day]={k:float(v) for k,v in row.items() if k!='Date' and v}
 ck(treasury_rows==tr,'Independently parsed exact Treasury input parity','treasury');ck(treasury_source['retained_row_count']==len(tr) and treasury_source['original_source_row_count']==len(tr)+len(treasury_source['removed_out_of_scope_dates']) and all(not START<=d<=LAST for d in treasury_source['removed_out_of_scope_dates']),'Treasury exact trimming inventory','provenance')
 primary_path=WORK/'market_primary_refs/stoxx_calendar_and_nne_inception.json';primary=load(primary_path);ck(primary['stoxx']['source_version']=='December 2023' and primary['stoxx']['independently_confirmed_dates']==['2024-05-09','2024-05-20'],'Primary administrator STOXX calendar extraction','calendar')
 suppressed=[];inception=[];exchange_close_checks=0;index_source_gates=[];month_closures={}
 for d,c in cards.items():
  ck(c['report_date']==d and c['cutoff_utc']==d+'T00:00:00Z',d+' identity','inventory');ck(not any(t.endswith('=X') for t in c['markets']) and set(c['excluded_vendor_marks']['tickers'])==FX,d+' numeric spotFX excluded','inventory');ck(not {'NBIS','CRWV','SNDK','^IRX','^TNX'}&set(c['markets']),d+' unavailable/rateproxy excluded','inventory');expected_inventory=set()
  for t,j in data.items():
   if t in FX|{'^IRX','^TNX'}:continue
   rows=[r for r in j['rows'] if r[0]<d]
   if not rows:ck(t not in c['markets'],d+t+' no pre-inception marks','inception');continue
   exp=[x for x in calendars[t][1] if x<d] if t in calendars else None
   if exp and rows[-1][0]!=exp[-1]:ck(t not in c['markets'] and bool(c.get('excluded_instruments',{}).get(t)),d+t+' stale latest omitted','calendar');suppressed.append({'date':d,'ticker':t,'kind':'latest_session'});continue
   expected_inventory.add(t);x=c['markets'][t];day,close=rows[-1];levels=dict(j['as_traded_rows']);ck(x['session']==day<d,d+t+' latest eligible session','calendar');ck(x['close']==(None if j.get('level_restriction') else f'{levels[day]:,.2f}'),d+t+' displayed historical units','arithmetic');ck(x['currency']==j['currency'] and x['tz']==j['tz'],d+t+' currency/timezone','arithmetic')
   unit='index points' if t.startswith('^') or t in {'DX-Y.NYB','000001.SS'} else FUTURES.get(t,j['currency']);ck(x['level_unit']==unit and x['return_unit']=='%',d+t+' correct units','arithmetic')
   if exp:
    cal,_,code=calendars[t];scheduled=cal.session_close(exp[-1]).to_pydatetime();gate=scheduled
    if t in {'^STOXX','^STOXX50E'}:
     gate=dt.datetime.fromisoformat(day+'T21:15:00+00:00');index_source_gates.append({'report_date':d,'ticker':t,'session':day,'conservative_dissemination_upper_bound_utc':gate.isoformat(),'source':primary['stoxx']['url'],'calendar_date_proxy':'XETR; not asserted as index venue'})
    ck(gate<dt.datetime.fromisoformat(d+'T00:00:00+00:00'),d+t+' independently scheduled or sourced upper-bound close strictly before cutoff','calendar');exchange_close_checks+=1
    if code not in month_closures:
     sessions=cal.sessions_in_range('2024-06-03','2024-06-28');module=__import__(cal.__module__,fromlist=['']);source=Path(module.__file__);month_closures[code]={'closed_weekdays':sorted(set(DATES)-set(sessions.strftime('%Y-%m-%d'))),'scheduled_closes_utc':{day.strftime('%Y-%m-%d'):cal.session_close(day).isoformat() for day in sessions},'calendar_source_file':source.name,'calendar_source_sha256':sha(source)}
   if t.endswith('-USD'):ck(day==(dt.date.fromisoformat(d)-dt.timedelta(days=1)).isoformat(),d+t+' prior completed UTCcandle','calendar')
   for n in (1,5,20):
    ref=rows[-n-1] if len(rows)>n else None;expected_ref=exp[-n-1] if exp and len(exp)>n else ref[0] if ref else None;valid=ref is not None and expected_ref==ref[0];ck(x[f'chg_{n}s_pct']==(pct(close,ref[1]) if valid else None),d+t+str(n)+' comparable return','arithmetic');ck(x[f'ref_{n}s_session']==(ref[0] if valid else None),d+t+str(n)+' horizon date','calendar')
    if not valid:
     ck(bool(x.get('history_limitation')),d+t+str(n)+' unavailable history disclosed','inception');(inception if ref is None else suppressed).append({'date':d,'ticker':t,'horizon':n,'observations':len(rows)})
   ref=rows[-21] if x['ref_20s_session'] is not None else None;changed=abs((levels[day]/close)/(levels[ref[0]]/ref[1])-1)>1e-6 if ref else None;ck(x['reference_share_units_differ']==changed and (not changed or bool(x['reference_level_note'])),d+t+' lookback share-unit warning','splits');ck(x['ref_20s_close']==(f'{levels[ref[0]]:,.2f}' if ref and not j.get('level_restriction') else None),d+t+' reference level','arithmetic')
   if t=='^VIX':ck(x['chg_1s_pts']==round(close-rows[-2][1],2),d+' VIX point change','arithmetic')
  ck(set(c['markets'])==expected_inventory,d+' exact writer inventory','inventory')
  days=sorted(k for k in tr if k<d);last,old,five=tr[days[-1]],tr[days[-21]],tr[days[-6]];z=c['treasury'];ck(z['prior_close_date']==days[-1] and z['obs20_earlier_date']==days[-21] and z['prior_5obs_date']==days[-6] and z['prior_1obs_date']==days[-2],d+' Treasury dates','treasury')
  for key,col in {'2y':'2 Yr','10y':'10 Yr','3m':'3 Mo','5y':'5 Yr','30y':'30 Yr','1y':'1 Yr'}.items():ck(z['prior_close_pct'][key]==f'{last[col]:.2f}%',d+' Treasury yield '+key,'treasury')
  for key,col in {'2y':'2 Yr','10y':'10 Yr','3m':'3 Mo','30y':'30 Yr'}.items():ck(z['chg_20obs_bps'][key]==bp(last[col],old[col]),d+' Treasury20obs '+key,'treasury')
  for key,col in {'2y':'2 Yr','10y':'10 Yr'}.items():
   ck(z['chg_5obs_bps'][key]==bp(last[col],five[col]),d+' Treasury5obs '+key,'treasury');ck(z['chg_1obs_bps'][key]==bp(last[col],tr[days[-2]][col]),d+' Treasury1obs '+key,'treasury')
  spread=bp(last['10 Yr'],last['2 Yr']);ck(z['spread_10y_2y_bps']==spread and z['spread_10y_3m_bps']==bp(last['10 Yr'],last['3 Mo']) and z['spread_30y_10y_bps']==bp(last['30 Yr'],last['10 Yr']),d+' Treasury spreads','treasury');ck(z['chg_20obs_bps']['spread']==spread-bp(old['10 Yr'],old['2 Yr']),d+' Treasury spread move','treasury');ck(z['curve_shape']==shape(spread) and z['curve_move_20obs']==move(bp(last['2 Yr'],old['2 Yr']),bp(last['10 Yr'],old['10 Yr'])),d+' Treasury curve wording','treasury')
 # Explicit June-only boundary checks. No later prices or listing histories are read.
 for d in ['2024-06-19','2024-06-20']:
  ck(cards[d]['markets']['^GSPC']['session']=='2024-06-18' and cards[d]['treasury']['prior_close_date']=='2024-06-18',d+' Juneteenth prior-session regression','boundary')
 ck(cards['2024-06-03']['markets']['^GSPC']['session']=='2024-05-31','June3 uses May31 cash close','boundary')
 ck(cards['2024-06-28']['markets']['^GSPC']['session']=='2024-06-27','June28 final cash close is June27','boundary')
 ck(not xc.get_calendar('XNYS').is_session('2024-06-19'),'June19 NYSE closed','boundary')
 for d,c in cards.items():
  ck('ETHA' not in c['markets'],d+' no pre-listing ETHA history','boundary')
  ck(float(c['markets']['MSTR']['close'].replace(',',''))>500,d+' June MSTR pre-August split units restored','boundary')
  ck(float(c['markets']['AVGO']['close'].replace(',',''))>500,d+' June AVGO pre-July split units restored','boundary')
  ck(c['markets']['MARA']['name']=='MARA (bitcoin miner)',d+' neutral historical MARA label','boundary')
  ck(c['markets']['NVDA']['reference_share_units_differ']==(d>='2024-06-11'),d+' NVDA June10 split lookback boundary','boundary')
  ck(c['markets']['CMG']['reference_share_units_differ']==(d>='2024-06-27'),d+' CMG June26 split lookback boundary','boundary')
 ck(float(cards['2024-06-10']['markets']['NVDA']['close'].replace(',',''))>1000 and float(cards['2024-06-11']['markets']['NVDA']['close'].replace(',',''))<200,'NVDA nominal split units straddle June10 session','boundary')
 ck(float(cards['2024-06-26']['markets']['CMG']['close'].replace(',',''))>1000 and float(cards['2024-06-27']['markets']['CMG']['close'].replace(',',''))<100,'CMG nominal split units straddle June26 session','boundary')
 independent_tr,tr_receipt=independent_treasury(args.offline);ck(independent_tr==tr,'Independently refetched Treasury exact parity','network');owner_cells={row['Date']:row for row in csv.DictReader((ROOT/'audit/treasury_retained.csv').open())};independent_cells={row['Date']:row for row in csv.DictReader((WORK/'independent_treasury_through_2024-06-27.csv').open())};ck(owner_cells==independent_cells,'Independently refetched Treasury exact source cell strings parity','network')
 holidays=set(USFederalHolidayCalendar().holidays(min(tr),LAST).strftime('%Y-%m-%d'))|{'2024-03-29'};first=dt.date.fromisoformat(min(tr));lastdate=dt.date.fromisoformat(LAST);expected_tr={str(first+dt.timedelta(days=n)) for n in range((lastdate-first).days+1) if (first+dt.timedelta(days=n)).weekday()<5 and str(first+dt.timedelta(days=n)) not in holidays};ck(set(tr)==expected_tr,'Treasury full observation calendar','treasury')
 sample_receipts=[]
 for t in ['NVDA','CMG','AVGO','MSTR','NNE']:
  sampled=sample_yahoo(t,args.offline);ck(sampled['rows']==data[t]['rows'],t+' independently refetched bounded Yahoo history','network');eventmap={e['date']:e['factor'] for e in sampled['actions']};ledger={e['date']:e['factor'] for e in load(action_paths[t])['events']};ck(eventmap==ledger,t+' independently refetched split-event ledger','network')
  if t=='NNE':
   first_day=dt.datetime.fromtimestamp(sampled['identity_meta']['firstTradeDate'],ZoneInfo(sampled['identity_meta']['exchangeTimezoneName'])).date().isoformat();ck(first_day==sampled['rows'][0][0]=='2024-05-08','NNE independently fetched first-trade metadata and actual first bar match primary completed release','boundary')
   for date,count in zip(DATES[:4],[17,18,19,20]):ck(cards[date]['markets']['NNE']['prior_observations']==count and cards[date]['markets']['NNE']['chg_20s_pct'] is None,date+' NNE exact short-inception history','boundary')
   ck(cards['2024-06-07']['markets']['NNE']['ref_20s_session']=='2024-05-08','NNE first full20obs reference is actual first bar','boundary')
  else:
   expected_date,expected_factor={'NVDA':('2024-06-10',10.0),'CMG':('2024-06-26',50.0),'AVGO':('2024-07-15',10.0),'MSTR':('2024-08-08',10.0)}[t];ck(eventmap.get(expected_date)==expected_factor,t+' key mechanical split date/factor','boundary')
  sample_receipts.append({'ticker':t,'path':str((WORK/'independent_yahoo_samples'/(name(t)+'.json')).relative_to(ROOT)),'sha256':sha(WORK/'independent_yahoo_samples'/(name(t)+'.json'))})
 for gap in gaps:
  t=gap['ticker'];refs=[c['markets'][t][f'ref_{n}s_session'] for c in cards.values() if t in c['markets'] for n in (1,5,20) if c['markets'][t][f'ref_{n}s_session'] is not None];gap['earliest_applied_reference']=min(refs) if refs else None;gap['all_gaps_before_applied_horizons']=all(day<min(refs) for day in gap['missing']) if refs else None;gap['classification']='Missing expected index calculation-day observations in Yahoo Zurich series. May9/20 are open under primary STOXX European calendar rules; XETR is a session-date proxy, not the index venue. Omission cause not asserted. No observation filled; affected20obs metrics suppressed.'
 base_inputs=[*sorted((ROOT/'data').glob('*.json')),*sorted((ROOT/'audit').glob('actions_*.json')),*sorted((ROOT/'audit/market_raw').glob('*')),ROOT/'audit/market_raw_retention.json',ROOT/'audit/market_fetch.json',ROOT/'audit/treasury_retained.csv',ROOT/'audit/treasury_source.json',*[(ROOT/'tools'/n) for n in ['fetch_market.py','build_cards.py','market_calendar_policy.py','validate_market.py']]]
 manifest=load(ROOT/'audit/market_card_inputs.json');owner=load(ROOT/'audit/market_owner_checks.json');validation=load(ROOT/'audit/market_validation.json')
 ck(set(manifest['input_sha256'])=={str(p.relative_to(ROOT)) for p in base_inputs},'Owner manifest exact independent base-input inventory','manifest')
 for filename,digest in manifest['input_sha256'].items():ck((ROOT/filename).is_file() and sha(ROOT/filename)==digest,'Owner manifest current input '+filename,'manifest')
 ck(set(manifest['cards'])==set(DATES),'Owner manifest exact date inventory','manifest')
 for d,c in cards.items():
  entry=manifest['cards'][d];ck(entry['path']=='cards/'+d+'.json' and entry['sha256']==sha(ROOT/entry['path']) and entry['cutoff_utc']==c['cutoff_utc'],d+' manifest current card hash/cutoff','manifest');ck(entry['used_symbols']==sorted(c['markets']) and set(entry['eligible_normalized_history_sha256'])==set(c['markets']),d+' manifest exact used symbol inventory','manifest')
  for t in c['markets']:
   j=data[t];digest=canonical_sha({'rows':[x for x in j['rows'] if x[0]<d],'as_traded_rows':[x for x in j['as_traded_rows'] if x[0]<d]});ck(entry['eligible_normalized_history_sha256'][t]==digest,d+t+' independently reconstructed strict eligible slice hash','manifest')
  ck(entry['eligible_treasury_history_sha256']==canonical_sha({k:v for k,v in tr.items() if k<d}),d+' independently reconstructed strict Treasury slice hash','manifest')
 ck(owner['passed'] is True and owner['errors']==[] and owner['cards']==len(DATES) and owner['raw_symbols']==len(data),'Owner receipt identity/results inventory','manifest');ck(owner['market_validation_sha256']==sha(ROOT/'audit/market_validation.json') and owner['market_card_inputs_sha256']==sha(ROOT/'audit/market_card_inputs.json') and owner['market_raw_retention_sha256']==sha(ROOT/'audit/market_raw_retention.json') and owner['owner_check_source_sha256']==sha(WORK/'check_market_owner.py'),'Owner receipt binds current validation/manifest/retention/source','manifest');ck(owner['removed_future_observations_count']==sum(r['removed_out_of_scope_observation_count'] for r in retained_sources.values()),'Owner receipt exact removed terminal observations count','manifest')
 ck(validation['passed'] is True and validation['errors']==[] and validation['dates']==DATES and validation['raw_symbols']==len(data) and validation['future_price_rows_retained']==0,'Owner validator receipt exact coverage','manifest');ck(validation['card_sha256']=={d:sha(ROOT/'cards'/f'{d}.json') for d in DATES} and validation['source_retention_sha256']==sha(ROOT/'audit/market_raw_retention.json'),'Owner validator binds current cards/retention','manifest')
 for filename,digest in validation['tool_sha256'].items():ck(sha(ROOT/'tools'/filename)==digest,'Owner validator current tool hash '+filename,'manifest')
 inputs=[*sorted((ROOT/'cards').glob('2024-06-*.json')),*base_inputs,ROOT/'audit/market_card_inputs.json',ROOT/'audit/market_owner_checks.json',ROOT/'audit/market_validation.json',WORK/'check_market_owner.py',ROOT/'AUTHORING.md',ROOT/'BRIEF.md',primary_path,WORK/'independent_treasury_request.json',WORK/'independent_treasury_through_2024-06-27.csv',*[(WORK/'independent_yahoo_samples'/(name(t)+'.json')) for t in ['NVDA','CMG','AVGO','MSTR','NNE']]]
 result={'reviewer':{'agent':'/root/june_markets/market_replay','relationship':'Separate child reviewer; no acquisition/card/sanitizer/owner-check functions imported or executed','scope':'Market infrastructure, independent source samples and manifest replay only'},'news_source_freeze_binding':'pending accepted news source freeze; not bound','passed':not errors,'status':'accepted' if not errors else 'failed','reviewed_at_utc':dt.datetime.now(UTC).isoformat(),'scope':'Independent June2024 raw/card arithmetic, split units, inception limits, exchange sessions and before-cutoff gates, separately fetched Treasury and Yahoo samples. Does not certify report prose. No owner functions imported.','assertions':sum(counts.values()),'assertions_by_scope':dict(counts),'errors':errors,'warnings':warnings,'dates':DATES,'raw_symbols':len(data),'writer_symbols_per_card':sorted({len(c['markets']) for c in cards.values()}),'independently_reparsed_raw_price_rows':raw_sample_checks,'actual_or_sourced_proxy_close_checks':exchange_close_checks,'raw_provider_gaps':gaps,'suppressed_metrics':suppressed,'short_inception_metrics':inception,'calendar_inventory':month_closures,'calendar_package':'exchange-calendars '+xc.__version__,'calendar_timing_override':None,'index_calendar_primary_review':primary['stoxx'],'primary_reference_path':str(primary_path.relative_to(ROOT)),'primary_reference_sha256':sha(primary_path),'actual_cash_exchange_close_checks':exchange_close_checks-len(index_source_gates),'sourced_index_dissemination_upper_bound_checks':len(index_source_gates),'index_source_gates':index_source_gates,'independent_treasury_request':tr_receipt,'independent_yahoo_sample_receipts':sample_receipts,'input_sha256':{str(p.relative_to(ROOT)):sha(p) for p in inputs if p.exists()},'review_script_sha256':sha(Path(__file__)),'card_sha256':{d:sha(ROOT/'cards'/f'{d}.json') for d in DATES},'raw_retention_receipt_sha256':sha(ROOT/'audit/market_raw_retention.json'),'limitations':['Current-vintage historical data can contain corrections; original unrevised publication vintage is not certified.','The sanitized retained Yahoo responses are explicit derivatives of network responses; original network SHA256 and retained-byte SHA256 are separately recorded.','Later split-event metadata is used solely to restore historical share units. No later price arrays or current price metadata enter retained inputs.','Independent calendar gates certify completed daily-session eligibility. Exact Yahoo print timestamps are not certified; cash-market exchange session-close schedules are checked independently.','Futures/DXY use bounded vendor observations rather than an independently acquired settlement tape.','This receipt covers infrastructure only; every authored numeric and factual claim still needs own-date editorial review.']}
 dump(WORK/'independent_market_review.json',result)
 if args.write_acceptance and not errors:dump(ROOT/'audit/independent_market_review.json',result)
 print(json.dumps({k:result[k] for k in ['passed','assertions','assertions_by_scope','errors','raw_symbols','writer_symbols_per_card','independently_reparsed_raw_price_rows','actual_or_sourced_proxy_close_checks']},indent=2));return bool(errors)
if __name__=='__main__':raise SystemExit(main())
