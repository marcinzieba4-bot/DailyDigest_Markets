"""Independent September infrastructure replay; never imports acquisition/build tools.

Run with /workspace/.report-tools/bin/python. Writes only audit_work unless --receipt
is supplied after the source/card owners and root have frozen their inputs.
"""
from pathlib import Path
import argparse, ast, csv, datetime as dt, hashlib, io, json, math, urllib.request
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit, unquote
import exchange_calendars as xc
from pandas.tseries.holiday import USFederalHolidayCalendar

ROOT = Path('/workspace/work/sep2024/repo/corrections/2024-09')
WORK = Path(__file__).resolve().parent
DATES = [dt.date(2024,9,n).isoformat() for n in range(1,31) if dt.date(2024,9,n).weekday()<5]
START, END = '2024-07-01', '2024-09-30'
LAST = '2024-09-29'
CUTOFF_LAST = dt.datetime(2024,9,30,tzinfo=dt.timezone.utc)
FX = {'EURUSD=X','JPY=X','AUDUSD=X','CNY=X','GBPUSD=X','PLN=X','EURPLN=X'}
SKIP = {'^TNX','^IRX'}
SUFFIX = {'.WA':'XWAR','.DE':'XETR','.PA':'XPAR','.CO':'XCSE','.L':'XLON','.SW':'XSWX','.T':'XTKS','.KS':'XKRX','.SS':'XSHG','.HK':'XHKG','.AX':'XASX'}
INDICES = {'^VIX':'XCBF','^NDX':'XNAS','^SOX':'XNAS','^N225':'XTKS','^KS11':'XKRX','^TWII':'XTAI','^HSI':'XHKG','^AXJO':'XASX','^FTSE':'XLON','^GDAXI':'XETR','^FCHI':'XPAR','^STOXX':'XETR','^STOXX50E':'XETR'}
BASELINE_PROVIDER_GAPS = {'^STOXX': {'2024-08-01'}, '^STOXX50E': {'2024-08-01'}}
FIRST_RETAINED = {'ETHA':'2024-07-23'}
FUTURE_UNITS = {'CL=F':'USD/bbl','BZ=F':'USD/bbl','NG=F':'USD/MMBtu','GC=F':'USD/oz','SI=F':'USD/oz','HG=F':'USD/lb','PL=F':'USD/oz','ZS=F':'US cents/bu'}
REQUIRED_CLOSURES = {'XNYS':['2024-09-02'],'XTKS':['2024-09-16','2024-09-23'],'XSHG':['2024-09-16','2024-09-17'],'XHKG':['2024-09-06','2024-09-18'],'XTAI':['2024-09-17'],'XKRX':['2024-09-16','2024-09-17','2024-09-18']}
err=[]; counts={}
def ck(ok,msg,scope='arithmetic'):
    counts[scope]=counts.get(scope,0)+1
    if not ok:err.append(msg)
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pct(a,b):return round((a/b-1)*100,2)
def bp(a,b):
    n=(Decimal(str(a))-Decimal(str(b)))*100
    ck(n==n.to_integral_value(),'Treasury value not whole basis points','treasury')
    return int(n)
def shape(spread):
    return 'inverted' if spread<0 else 'flat' if spread==0 else 'positive but very flat' if spread<25 else 'positively sloped' if spread<60 else 'moderately steep' if spread<100 else 'steep'
def move(a,b):
    if abs(a)<4 and abs(b)<4:return 'little changed'
    if a==b:return 'parallel rally (both down equally; spread unchanged)' if a<0 else 'parallel selloff (both up equally; spread unchanged)'
    if a>0 and b>0:return 'bear steepening (both up, 10Y up more)' if b>a else 'bear flattening (both up, 2Y up more)'
    if a<0 and b<0:return 'bull steepening (both down, 2Y down more)' if b>a else 'bull flattening (both down, 10Y down more)'
    if b>0:return 'steepening (10Y up, 2Y down/flat)'
    if a>0:return 'flattening (2Y up, 10Y down/flat)'
    if b<0:return 'flattening (10Y down, 2Y up/flat)'
    return 'steepening (2Y down, 10Y up/flat)'
def epoch(day):return str(int(dt.datetime.fromisoformat(day+'T00:00:00+00:00').timestamp()))
def literal_from_tool(path,key):
    for node in ast.parse(path.read_text()).body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id==key for t in node.targets):return ast.literal_eval(node.value)
    raise ValueError('Missing literal '+key)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--receipt',type=Path);ap.add_argument('--offline-treasury',action='store_true');args=ap.parse_args()
    rawpaths=sorted((ROOT/'data').glob('yf_*.json'))
    data={j['ticker']:j for p in rawpaths for j in [read(p)]}
    cards={d:read(ROOT/'cards'/f'{d}.json') for d in DATES}
    fetch=read(ROOT/'audit/market_fetch.json'); tr=read(ROOT/'data/treasury_par.json')
    universe=literal_from_tool(ROOT/'tools/fetch_market.py','UNIVERSE')
    ck(set(data)==set(universe)-{'NBIS'},'Declared universe fully acquired except separately unavailable NBIS','inventory')
    ck(len(rawpaths)==len(data),'Raw ticker inventory unique','inventory')
    ck(len(data)==289 and len(cards)==21,'289 usable raw symbols and21 weekday cards','inventory')
    ck(len(fetch)==len(universe) and len({r['ticker'] for r in fetch})==len(universe),'Complete unique fetch ledger','inventory')
    status={r['ticker']:r['status'] for r in fetch}
    ck(set(status)==set(universe) and all(status[t]=='ok' for t in data),'Usable raw inventory corresponds to successful fetches','inventory')
    ck(status.get('NBIS') in {'unavailable','unavailable_halted','not_available','expected_unavailable'},'NBIS explicitly unavailable in September fetch ledger','inventory')
    ck({t for t in data if t.endswith('=X')}==FX,'Exactly seven raw audit-only spotFX series','inventory')
    ck('NBIS' not in data,'No old Yandex or invented NBIS raw history','inventory')
    actionpaths={t:ROOT/'audit'/('actions_'+t.replace('^','_').replace('=','_').replace('.','_')+'.json') for t in data}
    ck(set((ROOT/'audit').glob('actions_*.json'))==set(actionpaths.values()),'Exact action ledger inventory; no future/unavailable ticker ledger','inventory')
    actions={t:read(p) for t,p in actionpaths.items()}
    for t,j in data.items():
        rows=j['rows']; levels=dict(j['as_traded_rows']); params=parse_qs(urlsplit(j['source_url']).query)
        ck(rows==sorted(rows) and len(rows)==len(dict(rows)),t+' raw dates sorted/unique','inventory')
        ck(set(dict(rows))==set(levels) and all(START<=day<=LAST for day,v in rows),t+' raw date bounds and as-traded date parity','inventory')
        ck(all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>0 for day,v in rows+j['as_traded_rows']),t+' positive finite values','inventory')
        ck(params.get('period1')==[epoch(START)] and params.get('period2')==[epoch(END)],t+' physical historical request bounds','inventory')
        ck(urlsplit(j['source_url']).hostname=='query1.finance.yahoo.com' and unquote(urlsplit(j['source_url']).path)=='/v8/finance/chart/'+t,t+' physical source ticker identity','provenance')
        ck(not ({'timestamp','indicators','prices','chart'} & set(j)),t+' no unbounded response or future price arrays in retainedraw','inventory')
        ck(j.get('max_kept_date')==LAST,t+' declared maximum retained date','inventory')
        ck(sum(day<'2024-09-01' for day,v in rows)>=21,t+' sufficient September initial comparable history','inventory')
        a=actions[t];events=a['events'];req=a['requests']
        ck(a.get('ticker')==t and len(req)==2 and req[0]['url']==j['source_url'] and req[0]['sha256']==j['source_response_sha256'],t+' source/action request hash identity','provenance')
        ck(events==sorted(events,key=lambda e:e['date']) and len({e['date'] for e in events})==len(events),t+' split ledger order/uniqueness','splits')
        ck(all(math.isfinite(e['factor']) and e['factor']>0 for e in events),t+' valid split factors','splits')
        ck(parse_qs(urlsplit(req[1]['url']).query).get('period1')==[epoch(END)],t+' future metadata request begins at historical bound','provenance')
        ck(not any(k in a for k in ('rows','prices','timestamp','indicators')),t+' audit action ledger holds no future observations','provenance')
        for day,close in rows:
            factor=math.prod(e['factor'] for e in events if e['date']>day)
            ck(abs(levels[day]-close*factor)<max(1e-5,levels[day]*1e-7),t+' '+day+' as-traded split restoration','splits')
        if t in {'WDC','CMCSA'}:ck(bool(j.get('level_restriction')),t+' spin-off level restriction','splits')
    for d,c in cards.items():
        ck(c['report_date']==d and c['cutoff_utc']==d+'T00:00:00Z',d+' card identity','inventory')
        expected={t for t,j in data.items() if t not in SKIP|FX and any(day<d for day,v in j['rows'])}
        ck(set(c['markets'])==expected,d+' full writer inventory, FX and rate proxies excluded','inventory')
        ck(set(c['excluded_vendor_marks']['tickers'])==FX,d+' declared FX exclusion','inventory')
        ck('DX-Y.NYB' in c['markets'] and not ({'NBIS','CRWV','SNDK'} & set(c['markets'])),d+' DXY allowed and unavailable names omitted','inventory')
        ck(set(c['unavailable_symbols'])=={'NBIS','CRWV','SNDK'},d+' unavailable symbols disclosed','inventory')
        for t,x in c['markets'].items():
            j=data[t]; prior=[r for r in j['rows'] if r[0]<d]; day,close=prior[-1];levels=dict(j['as_traded_rows'])
            ck(x['session']==day<d,d+' '+t+' latest retained completed observation','sessions')
            ck(x['currency']==j['currency'] and x['tz']==j['tz'],d+' '+t+' currency/timezone')
            unit='index points' if t.startswith('^') or t in {'DX-Y.NYB','000001.SS'} else FUTURE_UNITS.get(t,j['currency'])
            ck(x['level_unit']==unit and x['return_unit']=='%',d+' '+t+' explicit level and return units')
            ck(x['ref_1s_session']==prior[-2][0] and x['ref_5s_session']==prior[-6][0],d+' '+t+' short horizon date references')
            ck(x['close']==(None if j.get('level_restriction') else f'{levels[day]:,.2f}'),d+' '+t+' displayed as-traded close')
            ck(all(x.get(k)==('Historical nominal vendor units cannot be certified; quote comparable percentage changes only.' if k=='level_restriction' and t in {'WDC','CMCSA'} else j.get(k)) for k in ['source','source_url','vintage_note','level_restriction','price_level_basis','price_change_basis']),d+' '+t+' provenance/basis retained with audit-only event detail sanitized in restricted-level note','provenance')
            for n in (1,5,20):
                enough=len(prior)>n
                ck(x[f'chg_{n}s_pct']==(pct(close,prior[-n-1][1]) if enough else None),d+' '+t+' comparable return '+str(n))
                if not enough:ck(bool(x.get('history_limitation')),d+' '+t+' missing history disclosed')
            ref=prior[-21] if len(prior)>20 else None
            ck(x['ref_20s_session']==(ref[0] if ref else None),d+' '+t+' reference session')
            ck(x['ref_20s_close']==(f'{levels[ref[0]]:,.2f}' if ref and not j.get('level_restriction') else None),d+' '+t+' reference as-traded level')
            changed=abs(levels[day]/close/(levels[ref[0]]/ref[1])-1)>1e-6 if ref else None
            ck(x['reference_share_units_differ']==changed and (not changed or bool(x.get('reference_level_note'))),d+' '+t+' reference-unit warning')
            if t.endswith('-USD'):
                ck(day==(dt.date.fromisoformat(d)-dt.timedelta(days=1)).isoformat(),d+' '+t+' prior completed UTCdaily candle','sessions')
                close_time=dt.datetime.fromisoformat(day+'T00:00:00+00:00')+dt.timedelta(days=1)
                ck(close_time<=dt.datetime.fromisoformat(d+'T00:00:00+00:00'),d+' '+t+' UTCcandle completed by cutoff','sessions')
            if t in {'WDC','CMCSA'}:ck(x['close'] is None and x['ref_20s_close'] is None,d+' '+t+' spin-off levels absent','splits')
            if t=='^VIX':
                ck(x['chg_1s_pts']==round(close-prior[-2][1],2),d+' VIX prior point move')
                ck(x['chg_20s_pts']==round(close-prior[-21][1],2),d+' VIX20 point move')
        days=sorted(k for k in tr if k<d); last,old,five=tr[days[-1]],tr[days[-21]],tr[days[-6]];z=c['treasury']
        ck(z['prior_close_date']==days[-1] and z['obs20_earlier_date']==days[-21] and z['prior_5obs_date']==days[-6],d+' Treasury observation dates','treasury')
        for key,col in {'2y':'2 Yr','10y':'10 Yr','3m':'3 Mo','5y':'5 Yr','30y':'30 Yr','1y':'1 Yr'}.items():ck(z['prior_close_pct'][key]==f'{last[col]:.2f}%',d+' Treasury yield '+key,'treasury')
        for key,a,b in [('spread_10y_2y_bps','10 Yr','2 Yr'),('spread_10y_3m_bps','10 Yr','3 Mo'),('spread_30y_10y_bps','30 Yr','10 Yr')]:ck(z[key]==bp(last[a],last[b]),d+' '+key,'treasury')
        for key,col in {'2y':'2 Yr','10y':'10 Yr','3m':'3 Mo','30y':'30 Yr'}.items():ck(z['chg_20obs_bps'][key]==bp(last[col],old[col]),d+'20obs '+key,'treasury')
        for key,col in {'2y':'2 Yr','10y':'10 Yr'}.items():
            ck(z['chg_5obs_bps'][key]==bp(last[col],five[col]),d+'5obs '+key,'treasury')
            ck(z['obs20_earlier_pct'][key]==f'{old[col]:.2f}%',d+' oldyield '+key,'treasury')
        ck(z['chg_20obs_bps']['spread']==bp(last['10 Yr'],last['2 Yr'])-bp(old['10 Yr'],old['2 Yr']),d+' spread change','treasury')
        ck(z['curve_shape']==shape(z['spread_10y_2y_bps']),d+' curve shape','treasury')
        ck(z['curve_move_20obs']==move(z['chg_20obs_bps']['2y'],z['chg_20obs_bps']['10y']),d+' curve move','treasury')
    ck(cards['2024-09-02']['markets']['MSTR']['ref_20s_session']<'2024-08-08' and cards['2024-09-02']['markets']['MSTR']['reference_share_units_differ'] is True,'Early September MSTR lookback crosses August8 split; warning retained','splits')
    cals={};calnotes=[];closechecks=0;cashsymbols=0
    for t,j in data.items():
        if t in FX or t.endswith(('=F','-USD')) or t=='DX-Y.NYB':continue
        code=INDICES.get(t) or next((v for s,v in SUFFIX.items() if t.endswith(s)),'XNYS');cal=xc.get_calendar(code);cashsymbols+=1
        schedule=cal.schedule.loc[FIRST_RETAINED.get(t,START):LAST]
        expected={idx.strftime('%Y-%m-%d') for idx in schedule.index};actual=set(dict(j['rows']))
        missing=expected-actual;extra=actual-expected
        ck(missing==BASELINE_PROVIDER_GAPS.get(t,set()) and not extra,t+' independent exchange inventory or documented unused baseline gap '+str(sorted(expected^actual)),'calendars')
        if expected!=actual:calnotes.append({'ticker':t,'calendar':code,'missing_vendor_observations':sorted(missing),'extra_observations':sorted(extra),'classification':'unused baseline vendor gap; not an exchange closure','earliest_applied_20session_reference':min(c['markets'][t]['ref_20s_session'] for c in cards.values()),'all_gaps_before_applied_horizons':all(day<min(c['markets'][t]['ref_20s_session'] for c in cards.values()) for day in missing)})
        if code not in cals:
            source=Path(__import__(cal.__module__,fromlist=['']).__file__)
            cals[code]={'closed_weekdays':sorted(set(DATES)-{i.strftime('%Y-%m-%d') for i in cal.sessions_in_range('2024-09-01','2024-09-30')}),'calendar_code_sha256':sha(source),'calendar_source_file':source.name,'actual_september_session_closes_utc':{i.strftime('%Y-%m-%d'):cal.session_close(i).isoformat() for i in cal.sessions_in_range('2024-09-01','2024-09-30')}}
        for d,c in cards.items():
            if t in SKIP or t not in c['markets']:continue
            eligible=sorted(day for day in expected if day<d);target=eligible[-1]
            ck(c['markets'][t]['session']==target,d+' '+t+' latest independent exchange session','calendars')
            for n in (1,5,20):ck(c['markets'][t]['ref_'+str(n)+'s_session']==eligible[-n-1],d+' '+t+' exact '+str(n)+'session exchange reference','calendars')
            ck(cal.session_close(target).to_pydatetime()<dt.datetime.fromisoformat(d+'T00:00:00+00:00'),d+' '+t+' actual exchange close before UTCcutoff','calendars');closechecks+=1
    for code,days in REQUIRED_CLOSURES.items():
        for day in days:ck(day in cals[code]['closed_weekdays'],code+' exceptional/holiday closure '+day,'calendars')
    ck(cards['2024-09-09']['markets']['^HSI']['session']=='2024-09-05','HongKong Yagi closure makes September9 card use September5','calendars')
    ck(cards['2024-09-30']['markets']['^GSPC']['session']=='2024-09-27','Final Monday card has no Monday completed move','calendars')
    holidays=set(USFederalHolidayCalendar().holidays('2024-01-01',LAST).strftime('%Y-%m-%d'))|{'2024-03-29'}
    first=dt.date.fromisoformat(min(tr));last=dt.date.fromisoformat(LAST)
    expected_tr={str(first+dt.timedelta(days=n)) for n in range((last-first).days+1) if (first+dt.timedelta(days=n)).weekday()<5 and str(first+dt.timedelta(days=n)) not in holidays}
    ck(set(tr)==expected_tr,'Treasury complete weekday/federalholiday calendar through final cutoff','treasury')
    ck(cards['2024-09-03']['treasury']['prior_close_date']=='2024-08-30' and cards['2024-09-03']['markets']['^GSPC']['session']=='2024-08-30','LaborDay equity andTreasury observation closure','treasury')
    url='https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/2024/all?type=daily_treasury_yield_curve&field_tdr_date_value=2024&page&_format=csv'
    csvpath=WORK/'independent_treasury_2024_through_2024-09-27.csv';metapath=WORK/'independent_treasury_request.json'
    if args.offline_treasury:
        parsed={};meta=read(metapath)
        for row in csv.DictReader(io.StringIO(csvpath.read_text())):
            day=row.pop('Date');parsed[day]={k:float(v) for k,v in row.items() if v}
        ck(meta['retained_csv_sha256']==sha(csvpath),'Retained independent CSV hash','treasury')
    else:
        raw=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=40).read();parsed={}
        for row in csv.DictReader(io.StringIO(raw.decode())):
            day=dt.datetime.strptime(row['Date'],'%m/%d/%Y').date().isoformat()
            if day<=LAST:parsed[day]={k:float(v) for k,v in row.items() if k!='Date' and v}
        sio=io.StringIO();fields=['Date']+list(next(iter(parsed.values())).keys());wr=csv.DictWriter(sio,fieldnames=fields);wr.writeheader()
        for day,row in sorted(parsed.items()):wr.writerow({'Date':day,**row})
        csvpath.write_text(sio.getvalue());meta={'url':url,'response_sha256':hashlib.sha256(raw).hexdigest(),'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'retained_csv_sha256':sha(csvpath),'retained_through':max(parsed),'response_retention':'Only rows through final-report cutoff retained; later annual-response rows discarded.'};metapath.write_text(json.dumps(meta,indent=2)+'\n')
    ck(parsed==tr,'Independently fetched official Treasury CSV parity','treasury')
    out={'status':'accepted' if not err else 'failed','passed':not err,'scope':'Independent recomputation of September card infrastructure from bounded Yahoo historical closes and split ledgers, exchange calendars and separately fetched official Treasury CSV. Acquisition/build/validate functions were not imported. Report prose is outside this receipt.','dates':DATES,'checks':sum(counts.values()),'checks_by_scope':counts,'errors':err,'raw_symbols':len(data),'writer_symbols_per_card':sorted({len(c['markets']) for c in cards.values()}),'market_fetch_failures':sum(status[t]!='ok' for t in data),'expected_unavailable_symbols':['NBIS'],'exchange_calendar_package':'exchange-calendars '+xc.__version__,'independent_exchange_close_timestamp_checks':closechecks,'cash_symbols_calendar_checked':cashsymbols,'calendar_inventory':cals,'calendar_discrepancies':calnotes,'calendar_overrides':{},'calendar_mapping':{'ticker_overrides':INDICES,'suffix_calendars':SUFFIX,'default':'XNYS','note':'US exchange calendars share report-period holiday/regular-close conventions; VIX uses XCBF20:15UTC close rather than NYSE20:00UTC. STOXX indexes use the XETR cash-calendar proxy and retain their separate unused vendor baseline gaps.'},'raw_series_inception_bounds':FIRST_RETAINED,'known_unused_baseline_provider_gaps':{t:sorted(v) for t,v in BASELINE_PROVIDER_GAPS.items()},'required_holiday_and_exceptional_closures':REQUIRED_CLOSURES,'card_sha256':{d:sha(ROOT/'cards'/f'{d}.json') for d in DATES},'data_sha256':{p.name:sha(p) for p in sorted((ROOT/'data').glob('*.json'))},'action_sha256':{p.name:sha(p) for p in sorted((ROOT/'audit').glob('actions_*.json'))},'actual_tool_sha256':{p.name:sha(p) for p in sorted((ROOT/'tools').glob('*.py')) if p.name in {'fetch_market.py','build_cards.py','validate_market.py'}},'contract_sha256':{f:sha(ROOT/f) for f in ['AUTHORING.md','BRIEF.md']},'independent_replay_script_sha256':sha(Path(__file__)),'treasury_independent_request':dict(meta,parity=parsed==tr),'source_freeze_sha256':sha(ROOT/'audit/source_freeze.json') if (ROOT/'audit/source_freeze.json').exists() else None,'spot_fx_policy':'Exactly seven raw numeric =X series remain audit-only; no spot-FX level or return is in any writer card. DXY retained as an index. Vendor FX finality is not certified.','retained_observation_policy':{'historical_request_start_utc':START+'T00:00:00Z','historical_request_end_exclusive_utc':END+'T00:00:00Z','latest_retained_date':LAST,'future_action_metadata':'audit-only; no future observation arrays retained'},'limitations':['Current-vintage Yahoo history can include vendor corrections; original unrevised historical publication vintages are not certified.','Split ledgers are checked mechanically for as-traded display-unit restoration, including later audit-only actions. They are not historical investment evidence.','Cash equities, indexes and rate proxies use independent exchange session calendars and actual scheduled close timestamps. Futures and DXY use latest bounded vendor observations; a separate official settlement tape was not acquired.','Crypto candles are independently checked as the prior UTC day completed at the report cutoff; these candles close exactly at midnight UTC.','Two Yahoo STOXX index histories lack August1 observations despite the XETR proxy calendar being open. These remain disclosed provider baseline gaps, not closure overrides; every applied1/5/20session horizon independently matches the calendar and begins no earlier than August2. ETHA starts with the retainedJuly23 series; no pre-inception prices are estimated.','This receipt accepts card infrastructure only. Every report number, company role, release timing and trade claim still needs separate own-date review.']}
    path=args.receipt or WORK/'market_replay_result.json';path.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({'path':str(path),'status':out['status'],'checks':out['checks'],'checks_by_scope':counts,'errors':err,'calendar_discrepancies':calnotes,'raw_symbols':len(data),'writer_symbols_per_card':out['writer_symbols_per_card'],'independent_exchange_close_timestamp_checks':closechecks},indent=2))
    return bool(err)
if __name__=='__main__':raise SystemExit(main())
