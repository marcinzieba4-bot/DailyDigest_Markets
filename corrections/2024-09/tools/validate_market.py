"""Validate September cards, mechanical share units and exchange-local sessions.

Writes only audit/market_validation.json. This is an owner preflight; independent
acceptance is recorded separately. Current-vintage vendor revisions remain a
limitation. Future split events restore units and never supply investment facts.
Run with a Python environment containing exchange-calendars.
"""
from pathlib import Path
import datetime as dt
import hashlib
import importlib.util
import json
import math
from decimal import Decimal
from urllib.parse import urlsplit, parse_qs
import exchange_calendars as xc

ROOT = Path(__file__).resolve().parent.parent
def module(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT/'tools'/file)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod
cards_module = module('sep_cards', 'build_cards.py')
fetch_module = module('sep_fetch', 'fetch_market.py')
DATES = [dt.date(2024,9,n).isoformat() for n in range(1,31) if dt.date(2024,9,n).weekday()<5]
data = {j['ticker']:j for p in (ROOT/'data').glob('yf_*.json') for j in [json.loads(p.read_text())]}
tr = json.loads((ROOT/'data/treasury_par.json').read_text())
fetch = json.loads((ROOT/'audit/market_fetch.json').read_text())
errors=[]; checks=0; calendar_notes=[]
def check(value, message):
    global checks
    checks += 1
    if not value: errors.append(message)
def bp(a,b): return int((Decimal(str(a))-Decimal(str(b)))*100)
def pct(a,b): return round((a/b-1)*100,2)
expected=set(fetch_module.UNIVERSE)
unavailable=set(fetch_module.UNAVAILABLE)
check(len(expected)==len(fetch_module.UNIVERSE), 'Duplicate universe ticker')
check(set(data)==expected-unavailable, 'Retained market universe mismatch')
check({x['ticker'] for x in fetch}==expected, 'Fetch universe mismatch')
check(all(x['status']==('unavailable' if x['ticker'] in unavailable else 'ok') for x in fetch), 'Unexpected fetch failure/status')
check(len(DATES)==21, 'Expected 21 September weekdays')
check(fetch_module.P2==int(dt.datetime(2024,9,30,tzinfo=dt.timezone.utc).timestamp()), 'Request terminal bound')
check(all(d<'2024-09-30' for d in tr), 'Treasury row at/after final cutoff retained')
for t,j in data.items():
    rows=j['rows']; levels=j['as_traded_rows']
    check(bool(rows) and rows==sorted(rows) and len(rows)==len({d for d,_ in rows}), t+': unordered/duplicate rows')
    check(set(dict(rows))==set(dict(levels)), t+': display date mismatch')
    check(all(d<'2024-09-30' for d,_ in rows), t+': price at/after final cutoff retained')
    check(all(math.isfinite(v) and v>0 for _,v in rows+levels), t+': invalid value')
    check(len([x for x in rows if x[0]<'2024-09-02'])>=21, t+': insufficient initial lookback')
    params=parse_qs(urlsplit(j['source_url']).query)
    check(params['period1']==[str(fetch_module.P1)] and params['period2']==[str(fetch_module.P2)], t+': request bounds')
cards={d:json.loads((ROOT/'cards'/f'{d}.json').read_text()) for d in DATES}
for date,c in cards.items():
    check(c['report_date']==date and c['cutoff_utc']==date+'T00:00:00Z', date+': identity')
    check(c==cards_module.card(date), date+': deterministic card recomputation')
    days=sorted(d for d in tr if d<date); tc=c['treasury']; last=tr[days[-1]]; old=tr[days[-21]]
    check(tc['prior_close_date']==days[-1], date+': Treasury latest')
    check(tc['spread_10y_2y_bps']==bp(last['10 Yr'],last['2 Yr']), date+': spread')
    check(tc['chg_20obs_bps']['2y']==bp(last['2 Yr'],old['2 Yr']), date+': 2Y change')
    check(tc['chg_20obs_bps']['10y']==bp(last['10 Yr'],old['10 Yr']), date+': 10Y change')
    for t,x in c['markets'].items():
        raw=data[t]; rows=[r for r in raw['rows'] if r[0]<date]; ld,lc=rows[-1]; levels=dict(raw['as_traded_rows'])
        check(x['session']==ld<date, date+' '+t+': session/cutoff')
        for n in (1,5,20):
            check(x[f'chg_{n}s_pct']==pct(lc,rows[-n-1][1]), date+' '+t+': return '+str(n))
        check(x['ref_1s_session']==rows[-2][0] and x['ref_5s_session']==rows[-6][0] and x['ref_20s_session']==rows[-21][0], date+' '+t+': horizon dates')
        check(x['level_unit']==cards_module.level_unit(t,raw['currency']) and x['return_unit']=='%', date+' '+t+': units')
        if raw.get('level_restriction'):
            check(x['close'] is None and x['ref_20s_close'] is None, date+' '+t+': suppressed levels')
        else:
            check(x['close']==cards_module.fmt(levels[ld],t), date+' '+t+': display units')
        actions=json.loads((ROOT/'audit'/('actions_'+t.replace('^','_').replace('=','_').replace('.','_')+'.json')).read_text())['events']
        for day,value in [rows[-1],rows[-21]]:
            factor=math.prod(e['factor'] for e in actions if e['date']>day)
            check(abs(levels[day]-value*factor)<=max(1e-5,abs(levels[day])*1e-7), date+' '+t+': split arithmetic')
        changed=abs((levels[ld]/lc)/(levels[rows[-21][0]]/rows[-21][1])-1)>1e-6
        check(x['reference_share_units_differ']==changed and bool(x['reference_level_note'])==changed, date+' '+t+': reference share-unit boundary')
        if t.endswith('-USD'):
            check(ld==(dt.date.fromisoformat(date)-dt.timedelta(days=1)).isoformat(), date+' '+t+': completed UTC daily candle')
suffix_calendars={'.WA':'XWAR','.DE':'XETR','.PA':'XPAR','.CO':'XCSE','.L':'XLON','.SW':'XSWX','.T':'XTKS','.KS':'XKRX','.SS':'XSHG','.HK':'XHKG','.AX':'XASX'}
index_calendars={'^VIX':'XCBF','^NDX':'XNAS','^SOX':'XNAS','^N225':'XTKS','^KS11':'XKRX','^TWII':'XTAI','000001.SS':'XSHG','^HSI':'XHKG','^AXJO':'XASX','^FTSE':'XLON','^GDAXI':'XETR','^FCHI':'XPAR','^STOXX':'XETR','^STOXX50E':'XETR'}
calendar_inventory={}; prior_checks=0
for t,raw in sorted(data.items()):
    if t.endswith(('=X','=F','-USD')) or t=='DX-Y.NYB': continue
    code=index_calendars.get(t) or next((v for k,v in suffix_calendars.items() if t.endswith(k)),'XNYS')
    cal=xc.get_calendar(code)
    expected_sessions=cal.sessions_in_range(raw['rows'][0][0],raw['rows'][-1][0]).strftime('%Y-%m-%d').tolist()
    actual={d for d,_ in raw['rows']}; missing=sorted(set(expected_sessions)-actual); extra=sorted(actual-set(expected_sessions))
    # A vendor gap in excess baseline history is retained transparently. Every
    # actually used return horizon is checked against the exchange below.
    first_window=cal.sessions_in_range(raw['rows'][0][0],'2024-09-01')[-21].strftime('%Y-%m-%d')
    relevant_missing=[day for day in missing if day>=first_window]
    if missing or extra: calendar_notes.append({'ticker':t,'calendar':code,'missing':missing,'extra':extra,'earliest_used_20session_reference':first_window,'unused_baseline_gaps':[day for day in missing if day<first_window]})
    check(not relevant_missing and not extra, t+': used calendar inventory missing='+str(relevant_missing)+' extra='+str(extra))
    for date,c in cards.items():
        if t in cards_module.SKIP: continue
        sessions=cal.sessions_in_range(raw['rows'][0][0],(dt.date.fromisoformat(date)-dt.timedelta(days=1)).isoformat())
        expected_date=sessions[-1].strftime('%Y-%m-%d')
        check(c['markets'][t]['session']==expected_date, date+' '+t+': latest eligible exchange session '+expected_date)
        for horizon in (1,5,20):
            check(c['markets'][t][f'ref_{horizon}s_session']==sessions[-horizon-1].strftime('%Y-%m-%d'), date+' '+t+': exchange '+str(horizon)+'-session reference')
        cutoff=dt.datetime.fromisoformat(date).replace(tzinfo=dt.timezone.utc)
        check(cal.session_close(sessions[-1]).to_pydatetime()<=cutoff, date+' '+t+': session close after UTC cutoff')
        prior_checks+=1
    if code not in calendar_inventory:
        sessions=cal.sessions_in_range('2024-09-01','2024-09-30').strftime('%Y-%m-%d').tolist()
        calendar_inventory[code]={'sessions':sessions,'closed_weekdays':sorted(set(DATES)-set(sessions))}
cases=[('2024-09-03','^GSPC','2024-08-30'),('2024-09-09','^HSI','2024-09-05'),('2024-09-17','^N225','2024-09-13'),('2024-09-24','^N225','2024-09-20'),('2024-09-17','000001.SS','2024-09-13'),('2024-09-18','000001.SS','2024-09-13'),('2024-09-19','000001.SS','2024-09-18'),('2024-09-19','^HSI','2024-09-17'),('2024-09-18','^TWII','2024-09-16'),('2024-09-17','^KS11','2024-09-13'),('2024-09-18','^KS11','2024-09-13'),('2024-09-19','^KS11','2024-09-13'),('2024-09-20','^KS11','2024-09-19'),('2024-09-30','^GSPC','2024-09-27')]
for d,t,s in cases: check(cards[d]['markets'][t]['session']==s, d+' '+t+': holiday regression')
check(cards['2024-09-03']['treasury']['prior_close_date']=='2024-08-30', 'Treasury Labor Day closure')
check(cards['2024-09-30']['treasury']['prior_close_date']=='2024-09-27', 'Final Treasury prior close')
check(all(not any(t.endswith('=X') for t in c['markets']) and bool(c.get('excluded_vendor_marks')) for c in cards.values()), 'Numeric spot-FX excluded from every writer card')
check(all(not ({'NBIS','CRWV','SNDK'} & set(c['markets'])) and set(c['unavailable_symbols'])=={'NBIS','CRWV','SNDK'} for c in cards.values()), 'Unavailable symbols have no September metrics')
check(cards['2024-09-02']['markets']['MSTR']['reference_share_units_differ'], 'MSTR early-September old share units flagged')
check(float(cards['2024-09-02']['markets']['NFLX']['close'].replace(',',''))>500, 'NFLX split restoration')
check(float(cards['2024-09-02']['markets']['LCID']['close'].replace(',',''))<10, 'LCID reverse split restoration')
result={'passed':not errors,'assertions':checks,'errors':errors,'dates':DATES,'cards':len(cards),'instruments_per_card':sorted({len(c['markets']) for c in cards.values()}),'raw_symbols':len(data),'explicitly_unavailable_symbols':fetch_module.UNAVAILABLE,'fetch_failures':sum(x['status'] not in ('ok','unavailable') for x in fetch),'retained_date_exclusive':'2024-09-30','future_price_rows_retained':0,'calendar_package':'exchange-calendars','calendar_version':xc.__version__,'exchange_prior_session_checks':prior_checks,'calendar_inventory':calendar_inventory,'calendar_discrepancies':calendar_notes,'calendar_overrides':[],'spot_fx_policy':'Raw =X marks are audit-only. Every numeric spot-FX level and return is excluded from writer cards. DXY levels use index points.','holiday_cases':[{'report_date':d,'ticker':t,'session':s} for d,t,s in cases],'card_sha256':{d:hashlib.sha256((ROOT/'cards'/f'{d}.json').read_bytes()).hexdigest() for d in DATES},'vintage_limit':'Current-vintage retrospective histories can include vendor corrections. Future split metadata only restores historical display units and remains outside writer inputs.'}
(ROOT/'audit/market_validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('card_sha256','calendar_inventory')},indent=2))
raise SystemExit(bool(errors))
