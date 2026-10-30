"""Validate April2025 prior-session availability, returns, share units and holidays.

Prices are current-vintage vendor histories. Later corporate actions restore only
historical display units; later prices are not retained or supplied to writers.
"""
import datetime as dt
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from decimal import Decimal
from urllib.parse import urlsplit, parse_qs
import exchange_calendars as xc

ROOT = Path(__file__).resolve().parent.parent

def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT/'tools'/filename)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod

m = module('market_cards', 'build_cards.py')
f = module('market_fetch', 'fetch_market.py')
DATES = [dt.date(2025, 4, n).isoformat() for n in range(1, 31) if dt.date(2025, 4, n).weekday() < 5]
data = {j['ticker']: j for p in (ROOT/'data').glob('yf_*.json') for j in [json.loads(p.read_text())]}
tr = json.loads((ROOT/'data/treasury_par.json').read_text())
fetch = json.loads((ROOT/'audit/market_fetch.json').read_text())
limitations = json.loads((ROOT/'audit/market_history_limitations.json').read_text())
errors = []; assertions = 0

def check(value, message):
    global assertions
    assertions += 1
    if not value: errors.append(message)

def bps(a, b): return int((Decimal(str(a))-Decimal(str(b)))*100)
def ret(a, b): return round((a/b-1)*100, 2)
expected = set(f.UNIVERSE)
limited_history = {'CRWV'}
check(len(expected) == len(f.UNIVERSE), 'Duplicate configured ticker')
check({x['ticker'] for x in fetch} == expected == set(data), 'Fetch/data/configuration inventory mismatch')
check(all(x['status'] == 'ok' for x in fetch), 'Unresolved fetch failure')
check(len(DATES) == 22, 'Expected22 April weekdays')
check(all(day <= '2025-04-30' for day in tr), 'Later Treasury rows retained')
check(all({'2 Yr','10 Yr','3 Mo','5 Yr','30 Yr','1 Yr'} <= set(row) for row in tr.values()), 'Missing Treasury tenors')
for t, j in data.items():
    rows = j['rows']; levels = j['as_traded_rows']
    check(rows == sorted(rows), t+': unordered prices')
    check(all(day <= '2025-04-30' for day, _ in rows), t+': later price')
    check(len(rows) == len({day for day, _ in rows}), t+': duplicate observation')
    check(set(dict(rows)) == set(dict(levels)), t+': display-unit rows differ')
    check(all(math.isfinite(value) and value > 0 for _, value in rows+levels), t+': invalid close')
    before = [r for r in rows if r[0] < '2025-04-01']
    check(len(before) >= 21 or t in limited_history, t+': insufficient pre-April lookback')
    if len(before) >= 21:
        check(all((dt.date.fromisoformat(b[0])-dt.date.fromisoformat(a[0])).days <= 5
                  or (t=='NOVO-B.CO' and a[0]=='2025-04-16' and b[0]=='2025-04-22')
                  for a,b in zip(before[-21:],before[-20:])), t+': unexplained pre-April gap')
    params = parse_qs(urlsplit(j['source_url']).query)
    check(params['period1'] == [str(f.P1)] and params['period2'] == [str(f.P2)], t+': wrong request bounds')
    check(j.get('max_kept_date') == '2025-04-30', t+': wrong retained end date')

cards = {}; unavailable = []; absent = []
for date in DATES:
    c = json.loads((ROOT/'cards'/f'{date}.json').read_text()); cards[date] = c
    check(c['report_date'] == date and c['cutoff_utc'] == date+'T00:00:00Z', date+': identity/cutoff')
    available = {t for t, raw in data.items() if t not in m.SKIP and any(day < date for day,_ in raw['rows'])}
    check(set(c['markets']) == available, date+': available instrument inventory')
    for t in expected-m.SKIP-available:
        check(t in limited_history and date <= data[t]['rows'][0][0], date+' '+t+': unexplained missing instrument')
        absent.append({'date':date,'ticker':t,'reason':'No completed source observation before the report cutoff.'})
    days = sorted(d for d in tr if d < date); latest = tr[days[-1]]; earlier = tr[days[-21]]; tc = c['treasury']
    check(tc['prior_close_date'] == days[-1] < date, date+': Treasury prior close')
    check(tc['obs20_earlier_date'] == days[-21] < days[-1], date+': Treasury reference')
    check(tc['spread_10y_2y_bps'] == bps(latest['10 Yr'], latest['2 Yr']), date+': 10Y2Yspread')
    check(tc['spread_10y_3m_bps'] == bps(latest['10 Yr'], latest['3 Mo']), date+': 10Y3Mspread')
    check(tc['spread_30y_10y_bps'] == bps(latest['30 Yr'], latest['10 Yr']), date+': 30Y10Yspread')
    for key,col in [('2y','2 Yr'),('10y','10 Yr'),('3m','3 Mo'),('5y','5 Yr'),('30y','30 Yr'),('1y','1 Yr')]:
        check(tc['prior_close_pct'][key] == f'{latest[col]:.2f}%', date+': yield '+key)
    for key,col in [('2y','2 Yr'),('10y','10 Yr'),('3m','3 Mo'),('30y','30 Yr')]:
        check(tc['chg_20obs_bps'][key] == bps(latest[col], earlier[col]), date+': yield20 '+key)
    for key,col in [('2y','2 Yr'),('10y','10 Yr')]:
        check(tc['chg_5obs_bps'][key] == bps(latest[col],tr[days[-6]][col]), date+': yield5 '+key)
    check(tc['chg_20obs_bps']['spread'] == tc['chg_20obs_bps']['10y']-tc['chg_20obs_bps']['2y'], date+': spread change identity')
    for t,x in c['markets'].items():
        raw=data[t];rows=[r for r in raw['rows'] if r[0] < date];levels=dict(raw['as_traded_rows']);ld,lc=rows[-1]
        check(x['session'] == ld < date,date+' '+t+': latest/cutoff')
        check((dt.date.fromisoformat(date)-dt.date.fromisoformat(ld)).days <= 5 or (t=='NOVO-B.CO' and date=='2025-04-22' and ld=='2025-04-16'),date+' '+t+': unexplained staleness')
        missing=[]
        for n in (1,5,20):
            if len(rows) >= n+1:
                check(x[f'chg_{n}s_pct'] == ret(lc,rows[-n-1][1]),date+' '+t+': return'+str(n))
            else:
                check(x[f'chg_{n}s_pct'] is None,date+' '+t+': fabricated short-history return'+str(n));missing.append(n)
        if missing:
            check(t in limited_history and bool(x.get('history_limitation')) and x.get('prior_observations') == len(rows),date+' '+t+': undocumented partial history')
            unavailable.append({'date':date,'ticker':t,'prior_observations':len(rows),'unavailable_sessions':missing})
        ref_day,ref_value=rows[-21] if len(rows) >= 21 else (None,None)
        if ref_day:
            check(x['ref_20s_session'] == ref_day < ld,date+' '+t+': 20sessionreference')
            check(x['reference_share_units_differ'] == (abs((levels[ld]/lc)/(levels[ref_day]/ref_value)-1)>1e-6),date+' '+t+': reference share units')
        else:
            check(x['ref_20s_session'] is None and x['ref_20s_close'] is None and x['reference_share_units_differ'] is None,date+' '+t+': fabricated long reference')
        if raw.get('level_restriction'):
            check(x['close'] is None and x['ref_20s_close'] is None,date+' '+t+': restricted level exposed')
        else:
            check(x['close'] == m.fmt(levels[ld],t),date+' '+t+': displayed share units')
            if ref_day:check(x['ref_20s_close'] == m.fmt(levels[ref_day],t),date+' '+t+': reference display units')
        actions=json.loads((ROOT/'audit'/('actions_'+t.replace('^','_').replace('=','_').replace('.','_')+'.json')).read_text())['events']
        for day,value in ([rows[-1],rows[-21]] if ref_day else [rows[-1]]):
            factor=math.prod(float(e['factor']) for e in actions if e['date']>day)
            check(abs(levels[day]-value*factor) <= max(1e-5,abs(levels[day])*1e-7),date+' '+t+': split-factor arithmetic')
        if t.endswith('-USD'):
            check(ld == (dt.date.fromisoformat(date)-dt.timedelta(days=1)).isoformat(),date+' '+t+': incomplete/missing prior UTC crypto day')

# A calendar independent of the Yahoo rows catches missing/extra sessions and
# stale closes that arithmetic recomputation alone cannot detect. Foreign ETFs
# and ADRs use their US listing calendar, rather than the underlying country.
suffix_calendars = {'.WA':'XWAR','.DE':'XETR','.PA':'XPAR','.CO':'XCSE',
    '.L':'XLON','.SW':'XSWX','.T':'XTKS','.KS':'XKRX','.SS':'XSHG',
    '.HK':'XHKG','.AX':'XASX'}
index_calendars = {'^N225':'XTKS','^KS11':'XKRX','^TWII':'XTAI',
    '000001.SS':'XSHG','^HSI':'XHKG','^AXJO':'XASX','^FTSE':'XLON',
    '^GDAXI':'XETR','^FCHI':'XPAR','^STOXX':'XETR','^STOXX50E':'XETR'}
calendar_checks = []; calendar_inventory = {}; calendar_mismatches = []
for t,raw in sorted(data.items()):
    if t.endswith(('=X','=F','-USD')) or t == 'DX-Y.NYB': continue
    code = index_calendars.get(t) or next((v for suffix,v in suffix_calendars.items() if t.endswith(suffix)), 'XNYS')
    cal = xc.get_calendar(code)
    sessions = cal.sessions_in_range(raw['rows'][0][0],raw['rows'][-1][0]).strftime('%Y-%m-%d').tolist()
    actual = {day for day,_ in raw['rows']}
    missing = sorted(set(sessions)-actual); extra = sorted(actual-set(sessions))
    known_unused = t == 'BP.L' and missing == ['2025-02-27'] and not extra
    check((not missing and not extra) or known_unused,t+': independent exchange-session inventory')
    if missing or extra:
        calendar_mismatches.append({'ticker':t,'calendar':code,'missing':missing,'extra':extra,
            'resolution':'Confirmed Yahoo null on narrow re-query; outside all April 1/5/20-session card windows. No fill or estimate.' if known_unused else 'unresolved'})
    if known_unused:
        for date,c in cards.items():
            rows = [r for r in raw['rows'] if r[0] < date]
            check(rows[-21][0] > '2025-02-27',date+' BP.L: unused vendor gap affects lookback')
    for date,c in cards.items():
        if t in m.SKIP or t not in c['markets']: continue
        expected_latest = cal.sessions_in_range(raw['rows'][0][0],
            (dt.date.fromisoformat(date)-dt.timedelta(days=1)).isoformat()).strftime('%Y-%m-%d').tolist()[-1]
        check(c['markets'][t]['session'] == expected_latest,date+' '+t+': independently expected prior session')
        calendar_checks.append({'date':date,'ticker':t,'calendar':code,'expected_session':expected_latest})
    if code not in calendar_inventory:
        april = cal.sessions_in_range('2025-04-01','2025-04-30').strftime('%Y-%m-%d').tolist()
        calendar_inventory[code] = {'april_sessions':april,'closed_weekdays':sorted(set(DATES)-set(april))}

# Exchange-specific holiday boundaries, independently checked against dated calendars.
calendar_cases=[
 ('2025-04-03','^TWII','2025-04-02'),('2025-04-04','^TWII','2025-04-02'),
 ('2025-04-07','^TWII','2025-04-02'),('2025-04-08','^TWII','2025-04-07'),
 ('2025-04-04','000001.SS','2025-04-03'),('2025-04-07','000001.SS','2025-04-03'),
 ('2025-04-08','000001.SS','2025-04-07'),
 ('2025-04-04','^HSI','2025-04-03'),('2025-04-07','^HSI','2025-04-03'),('2025-04-08','^HSI','2025-04-07'),
 ('2025-04-18','^GSPC','2025-04-17'),('2025-04-21','^GSPC','2025-04-17'),('2025-04-22','^GSPC','2025-04-21'),
 ('2025-04-18','PKO.WA','2025-04-17'),('2025-04-21','PKO.WA','2025-04-17'),('2025-04-22','PKO.WA','2025-04-17'),('2025-04-23','PKO.WA','2025-04-22'),
 ('2025-04-18','^FTSE','2025-04-17'),('2025-04-22','^FTSE','2025-04-17'),('2025-04-23','^FTSE','2025-04-22'),
 ('2025-04-22','^GDAXI','2025-04-17'),('2025-04-22','^FCHI','2025-04-17'),('2025-04-22','NESN.SW','2025-04-17'),
 ('2025-04-17','NOVO-B.CO','2025-04-16'),('2025-04-18','NOVO-B.CO','2025-04-16'),
 ('2025-04-21','NOVO-B.CO','2025-04-16'),('2025-04-22','NOVO-B.CO','2025-04-16'),('2025-04-23','NOVO-B.CO','2025-04-22'),
 ('2025-04-18','^HSI','2025-04-17'),('2025-04-22','^HSI','2025-04-17'),('2025-04-23','^HSI','2025-04-22'),
 ('2025-04-21','000001.SS','2025-04-18'),('2025-04-22','000001.SS','2025-04-21'),
 ('2025-04-21','^TWII','2025-04-18'),('2025-04-22','^TWII','2025-04-21'),
 ('2025-04-21','^N225','2025-04-18'),('2025-04-22','^N225','2025-04-21'),
 ('2025-04-21','^KS11','2025-04-18'),('2025-04-22','^KS11','2025-04-21'),
 ('2025-04-18','^AXJO','2025-04-17'),('2025-04-22','^AXJO','2025-04-17'),('2025-04-23','^AXJO','2025-04-22'),
 ('2025-04-25','^AXJO','2025-04-24'),('2025-04-28','^AXJO','2025-04-24'),('2025-04-29','^AXJO','2025-04-28'),
 ('2025-04-29','^N225','2025-04-28'),('2025-04-30','^N225','2025-04-28')]
for date,t,session in calendar_cases:
    check(cards[date]['markets'][t]['session'] == session,date+' '+t+': calendar regression')
for date,session in [('2025-04-01','2025-03-31'),('2025-04-18','2025-04-17'),('2025-04-21','2025-04-17'),('2025-04-22','2025-04-21')]:
    check(cards[date]['treasury']['prior_close_date'] == session,date+': Treasury holiday regression')
for t in ('BMNR','CRCL'):
    check(t not in expected and t not in data and all(t not in c['markets'] for c in cards.values()),t+': unavailable April history exposed')
check(float(cards['2025-04-01']['markets']['NFLX']['close'].replace(',',''))>500,'Netflix later split restoration')
check(float(cards['2025-04-01']['markets']['LCID']['close'].replace(',',''))<10,'Lucid later reverse split restoration')
check(m.curve_move(-10,-10)=='parallel rally (both down equally; spread unchanged)','Parallel rally label')
check(m.curve_move(10,10)=='parallel selloff (both up equally; spread unchanged)','Parallel selloff label')
result={'passed':not errors,'assertions':assertions,'errors':errors,'cards':len(cards),
        'instruments_per_card':sorted({len(c['markets']) for c in cards.values()}),'raw_symbols':len(data),
        'fetch_failures':sum(x['status']!='ok' for x in fetch),'unavailable_short_history_metrics':unavailable,
        'absent_before_first_source_observation':absent,
        'information_cutoff':'00:00 UTC per report; crypto prior UTC candle completes at that boundary',
        'retained_price_last_date':'2025-04-30','future_price_rows_retained':0,'level_suppression':f.SUPPRESS_LEVEL,
        'vintage_limit':'Current-vintage historical data may contain vendor revisions; original contemporaneous vendor snapshots are not asserted.',
        'sources':['Yahoo Finance daily chart API','US Treasury daily par yield curve'],
        'excluded_no_April_source_history':limitations,
        'calendar_cases':[{'report_date':d,'ticker':t,'expected_session':s} for d,t,s in calendar_cases],
        'card_sha256':{d:hashlib.sha256((ROOT/'cards'/f'{d}.json').read_bytes()).hexdigest() for d in DATES}}
calendar_result = {
    'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
    'passed':not errors,
    'package':'exchange-calendars','version':xc.__version__,
    'sources':json.loads((ROOT/'audit/market_calendar_sources.json').read_text()),
    'inventory':calendar_inventory,'prior_session_checks':len(calendar_checks),
    'raw_calendar_symbols':sum(not t.endswith(('=X','=F','-USD')) and t!='DX-Y.NYB' for t in data),
    'confirmed_unused_vendor_gaps':calendar_mismatches,
    'allowed_long_gaps':[{'ticker':'NOVO-B.CO','from':'2025-04-16','to':'2025-04-22','reason':'Copenhagen Easter exchange closures'}],
    'guard':'No later-session value is substituted; no forward fill is fabricated.',
    'data_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'data').glob('yf_*.json'))},
    'card_sha256':result['card_sha256'],
    'calendar_sources_sha256':hashlib.sha256((ROOT/'audit/market_calendar_sources.json').read_bytes()).hexdigest(),
    'vendor_null_proof_sha256':hashlib.sha256((ROOT/'audit/market_vendor_null_BP_L.json').read_bytes()).hexdigest(),
}
(ROOT/'audit/market_calendar_review.json').write_text(json.dumps(calendar_result,indent=2)+'\n')
result['independent_calendar_review_sha256'] = hashlib.sha256((ROOT/'audit/market_calendar_review.json').read_bytes()).hexdigest()
result['independent_calendar_prior_session_checks'] = len(calendar_checks)
(ROOT/'audit/market_validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in {'card_sha256','unavailable_short_history_metrics','absent_before_first_source_observation'}},indent=2))
raise SystemExit(bool(errors))
