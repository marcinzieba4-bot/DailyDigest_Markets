"""Validate June2025 prior-session availability, returns, share units and holidays.

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

ROOT = Path(__file__).resolve().parent.parent

def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT/'tools'/filename)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod

m = module('market_cards', 'build_cards.py')
f = module('market_fetch', 'fetch_market.py')
DATES = [dt.date(2025, 6, n).isoformat() for n in range(1, 31) if dt.date(2025, 6, n).weekday() < 5]
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
limited_history = {'BMNR', 'CRCL'}
check(len(expected) == len(f.UNIVERSE), 'Duplicate configured ticker')
check({x['ticker'] for x in fetch} == expected == set(data), 'Fetch/data/configuration inventory mismatch')
check(all(x['status'] == 'ok' for x in fetch), 'Unresolved fetch failure')
check(len(DATES) == 21, 'Expected21 June weekdays')
check(all(day <= '2025-06-30' for day in tr), 'Later Treasury rows retained')
check(all({'2 Yr','10 Yr','3 Mo','5 Yr','30 Yr','1 Yr'} <= set(row) for row in tr.values()), 'Missing Treasury tenors')
for t, j in data.items():
    rows = j['rows']; levels = j['as_traded_rows']
    check(rows == sorted(rows), t+': unordered prices')
    check(all(day <= '2025-06-30' for day, _ in rows), t+': later price')
    check(len(rows) == len({day for day, _ in rows}), t+': duplicate observation')
    check(set(dict(rows)) == set(dict(levels)), t+': display-unit rows differ')
    check(all(math.isfinite(value) and value > 0 for _, value in rows+levels), t+': invalid close')
    before = [r for r in rows if r[0] < '2025-06-01']
    check(len(before) >= 21 or t in limited_history, t+': insufficient pre-June lookback')
    if t in limited_history:
        check(rows[0][0] == limitations[t]['first_available_session'] == '2025-06-05', t+': limited-history boundary')
    if len(before) >= 21:
        check(all((dt.date.fromisoformat(b[0])-dt.date.fromisoformat(a[0])).days <= 5
                  or (t == '000001.SS' and a[0] == '2025-04-30' and b[0] == '2025-05-06')
                  for a,b in zip(before[-21:],before[-20:])), t+': unexplained pre-June gap')
    params = parse_qs(urlsplit(j['source_url']).query)
    check(params['period1'] == [str(f.P1)] and params['period2'] == [str(f.P2)], t+': wrong request bounds')
    check(j.get('max_kept_date') == '2025-06-30', t+': wrong retained end date')

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
        check((dt.date.fromisoformat(date)-dt.date.fromisoformat(ld)).days <= 5,date+' '+t+': unexplained staleness')
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

# Separate exchanges have different holidays: Hong Kong was open June2.
calendar_cases=[('2025-06-02','^GSPC','2025-05-30'),('2025-06-20','^GSPC','2025-06-18'),
                ('2025-06-23','^GSPC','2025-06-20'),('2025-06-03','000001.SS','2025-05-30'),
                ('2025-06-03','^HSI','2025-06-02'),('2025-06-04','^KS11','2025-06-02'),
                ('2025-06-09','^KS11','2025-06-05'),('2025-06-02','^TWII','2025-05-29'),
                ('2025-06-10','^AXJO','2025-06-06'),('2025-06-20','PKO.WA','2025-06-18')]
for date,t,session in calendar_cases:
    check(cards[date]['markets'][t]['session'] == session,date+' '+t+': calendar regression')
for date,session in [('2025-06-02','2025-05-30'),('2025-06-20','2025-06-18'),('2025-06-23','2025-06-20')]:
    check(cards[date]['treasury']['prior_close_date'] == session,date+': Treasury holiday regression')
for t in limited_history:
    check(t not in cards['2025-06-05']['markets'],t+': quote before first source session')
    first=cards['2025-06-06']['markets'][t]
    check(first['session']=='2025-06-05' and first['chg_1s_pct'] is None and first['chg_5s_pct'] is None and first['chg_20s_pct'] is None,t+': IPO first-close boundary')
    check(cards['2025-06-09']['markets'][t]['chg_1s_pct'] is not None and cards['2025-06-09']['markets'][t]['chg_5s_pct'] is None,t+': second observation availability')
check(float(cards['2025-06-02']['markets']['NFLX']['close'].replace(',',''))>500,'Netflix later split restoration')
check(float(cards['2025-06-02']['markets']['LCID']['close'].replace(',',''))<10,'Lucid later reverse split restoration')
check(m.curve_move(-10,-10)=='parallel rally (both down equally; spread unchanged)','Parallel rally label')
check(m.curve_move(10,10)=='parallel selloff (both up equally; spread unchanged)','Parallel selloff label')
result={'passed':not errors,'assertions':assertions,'errors':errors,'cards':len(cards),
        'instruments_per_card':sorted({len(c['markets']) for c in cards.values()}),'raw_symbols':len(data),
        'fetch_failures':sum(x['status']!='ok' for x in fetch),'unavailable_short_history_metrics':unavailable,
        'absent_before_first_source_observation':absent,
        'information_cutoff':'00:00 UTC per report; crypto prior UTC candle completes at that boundary',
        'retained_price_last_date':'2025-06-30','future_price_rows_retained':0,'level_suppression':f.SUPPRESS_LEVEL,
        'vintage_limit':'Current-vintage historical data may contain vendor revisions; original contemporaneous vendor snapshots are not asserted.',
        'sources':['Yahoo Finance daily chart API','US Treasury daily par yield curve'],
        'calendar_cases':[{'report_date':d,'ticker':t,'expected_session':s} for d,t,s in calendar_cases],
        'card_sha256':{d:hashlib.sha256((ROOT/'cards'/f'{d}.json').read_bytes()).hexdigest() for d in DATES}}
(ROOT/'audit/market_validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in {'card_sha256','unavailable_short_history_metrics','absent_before_first_source_observation'}},indent=2))
raise SystemExit(bool(errors))
