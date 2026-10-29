"""Validate July 2025 cutoffs, observation arithmetic, share units and exchange holidays.

This audits retained historical observations, not an original unrevised vendor vintage.
Later split events are used only to restore historical display units and remain in audit/.
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
DATES = [dt.date(2025, 7, n).isoformat() for n in range(1, 32) if dt.date(2025, 7, n).weekday() < 5]
data = {j['ticker']: j for p in (ROOT/'data').glob('yf_*.json') for j in [json.loads(p.read_text())]}
tr = json.loads((ROOT/'data/treasury_par.json').read_text())
fetch = json.loads((ROOT/'audit/market_fetch.json').read_text())
errors = []; assertions = 0
def check(value, message):
    global assertions
    assertions += 1
    if not value: errors.append(message)
def bps(a, b): return int((Decimal(str(a))-Decimal(str(b)))*100)
def ret(a, b): return round((a/b-1)*100, 2)
expected = set(f.UNIVERSE)
limitations = json.loads((ROOT/'audit/market_history_limitations.json').read_text())
limited_history = {'BMNR', 'CRCL'}
check(len(expected) == len(f.UNIVERSE), 'Duplicate ticker in configured universe')
check({x['ticker'] for x in fetch} == expected == set(data), 'Fetch/data/configured inventory mismatch')
check(all(x['status'] == 'ok' for x in fetch), 'Unresolved source fetch failure')
check(len(DATES) == 23, 'Expected 23 July weekday dates')
check(all(day <= '2025-07-31' for day in tr), 'Later Treasury rows retained')
check(all({'2 Yr','10 Yr','3 Mo','5 Yr','30 Yr','1 Yr'} <= set(row) for row in tr.values()), 'Missing actual Treasury tenor columns')
for t, j in data.items():
    rows = j['rows']; levels = j['as_traded_rows']
    check(rows == sorted(rows), t+': unordered prices')
    check(all(day <= '2025-07-31' for day, _ in rows), t+': later price')
    check(len(rows) == len({day for day, _ in rows}), t+': duplicate price date')
    check(set(dict(rows)) == set(dict(levels)), t+': display-unit row mismatch')
    check(all(math.isfinite(value) and value > 0 for _, value in rows+levels), t+': nonpositive/nonfinite close')
    before = [r for r in rows if r[0] < '2025-07-01']
    # Extended requests independently confirm these two vendor series start June 5.
    # Do not infer an IPO date or splice a predecessor/OTC security into the series.
    check(len(before) >= 21 or t in limited_history, t+': missing pre-July 20-session history')
    if t in limited_history:
        check(rows[0][0] == limitations[t]['first_available_session'] == '2025-06-05', t+': limited-history boundary')
    if len(before) >= 21:
        check(max((dt.date.fromisoformat(b[0])-dt.date.fromisoformat(a[0])).days for a,b in zip(before[-21:],before[-20:])) <= 5,
              t+': unexpected gap inside July 1 lookback')
    params = parse_qs(urlsplit(j['source_url']).query)
    check(params['period1'] == [str(f.P1)] and params['period2'] == [str(f.P2)], t+': wrong request bounds')
cards = {}
missing = []
for date in DATES:
    c = json.loads((ROOT/'cards'/f'{date}.json').read_text()); cards[date] = c
    check(c['report_date'] == date and c['cutoff_utc'] == date+'T00:00:00Z', date+': identity/cutoff')
    check(set(c['markets']) == expected-m.SKIP, date+': market inventory')
    days = sorted(d for d in tr if d < date); latest = tr[days[-1]]; earlier = tr[days[-21]]; tc = c['treasury']
    check(tc['prior_close_date'] == days[-1] < date, date+': Treasury prior close')
    check(tc['obs20_earlier_date'] == days[-21] < days[-1], date+': Treasury 20-observation reference')
    check(tc['spread_10y_2y_bps'] == bps(latest['10 Yr'], latest['2 Yr']), date+': Treasury spread')
    for key, col in [('2y','2 Yr'),('10y','10 Yr'),('3m','3 Mo'),('30y','30 Yr')]:
        check(tc['prior_close_pct'][key] == f'{latest[col]:.2f}%', date+': yield level '+key)
        check(tc['chg_20obs_bps'][key] == bps(latest[col], earlier[col]), date+': yield change '+key)
    check(tc['chg_20obs_bps']['spread'] == tc['chg_20obs_bps']['10y']-tc['chg_20obs_bps']['2y'], date+': spread change identity')
    for t, x in c['markets'].items():
        raw = data[t]; rows = [r for r in raw['rows'] if r[0] < date]; levels = dict(raw['as_traded_rows'])
        latest_day, latest_value = rows[-1]
        check(x['session'] == latest_day < date, date+' '+t+': latest/cutoff')
        check((dt.date.fromisoformat(date)-dt.date.fromisoformat(latest_day)).days <= 5, date+' '+t+': unexpected staleness')
        for n in (1,5): check(x[f'chg_{n}s_pct'] == ret(latest_value, rows[-n-1][1]), date+' '+t+': return '+str(n))
        if len(rows) >= 21:
            ref_day, ref_value = rows[-21]
            check(x['ref_20s_session'] == ref_day < latest_day, date+' '+t+': 20-session reference/cutoff')
            check(x['chg_20s_pct'] == ret(latest_value, ref_value), date+' '+t+': return 20')
            unit_diff = abs((levels[latest_day]/latest_value)/(levels[ref_day]/ref_value)-1) > 1e-6
            check(x['reference_share_units_differ'] == unit_diff, date+' '+t+': split reference warning')
        else:
            ref_day = None
            check(x['chg_20s_pct'] is None and x['ref_20s_session'] is None and x['ref_20s_close'] is None and bool(x.get('history_limitation')),
                  date+' '+t+': unavailable 20-session history fabricated')
            check(t in limited_history, date+' '+t+': unexpected unavailable metric')
            missing.append({'date':date,'ticker':t,'prior_observations':len(rows)})
        if raw.get('level_restriction'):
            check(x['close'] is None and x['ref_20s_close'] is None, date+' '+t+': restricted display level exposed')
        else:
            check(x['close'] == m.fmt(levels[latest_day], t), date+' '+t+': current share units')
            if ref_day: check(x['ref_20s_close'] == m.fmt(levels[ref_day], t), date+' '+t+': reference share units')
        actions = json.loads((ROOT/'audit'/('actions_'+t.replace('^','_').replace('=','_').replace('.','_')+'.json')).read_text())['events']
        for day, value in ([rows[-1], rows[-21]] if ref_day else [rows[-1]]):
            factor = math.prod(float(e['factor']) for e in actions if e['date'] > day)
            check(abs(levels[day]-value*factor) <= max(1e-5, abs(levels[day])*1e-7), date+' '+t+': independent split-factor arithmetic')

# Explicit calendar cases ensure date-only filtering is consistent with actual holidays.
for date, session in [('2025-07-01','2025-06-30'),('2025-07-04','2025-07-03'),('2025-07-07','2025-07-03')]:
    check(cards[date]['markets']['^GSPC']['session'] == session, date+': US exchange holiday/prior-session regression')
    check(cards[date]['treasury']['prior_close_date'] == session, date+': Treasury holiday/prior-session regression')
check(cards['2025-07-07']['markets']['BTC-USD']['session'] == '2025-07-06', 'Crypto Sunday session missing')
check(cards['2025-07-02']['markets']['^HSI']['session'] == '2025-06-30', 'Hong Kong July 1 holiday regression')
check(cards['2025-07-22']['markets']['^N225']['session'] == '2025-07-18', 'Japan July 21 holiday regression')
check(float(cards['2025-07-01']['markets']['NFLX']['close'].replace(',','')) > 500, 'Netflix later split unit restoration')
check(float(cards['2025-07-01']['markets']['LCID']['close'].replace(',','')) < 10, 'Lucid later reverse-split unit restoration')
check(m.curve_move(-10,-10) == 'parallel rally (both down equally; spread unchanged)', 'Parallel rally label')
check(m.curve_move(10,10) == 'parallel selloff (both up equally; spread unchanged)', 'Parallel selloff label')
result = {'passed':not errors,'assertions':assertions,'errors':errors,'cards':len(cards),
          'instruments_per_card':sorted({len(c['markets']) for c in cards.values()}),'raw_symbols':len(data),
          'fetch_failures':sum(x['status'] != 'ok' for x in fetch), 'unavailable_20_session_metrics':missing,
          'information_cutoff':'00:00 UTC per report date; crypto prior UTC candle completes at that boundary',
          'retained_price_last_date':'2025-07-31','future_price_rows_retained':0,'level_suppression':f.SUPPRESS_LEVEL,
          'vintage_limit':'Retrospectively retrieved vendor history may contain later corrections; unrevised original vintages are not asserted.',
          'sources':['Yahoo Finance daily chart API','US Treasury daily par yield curve'],
          'card_sha256':{d:hashlib.sha256((ROOT/'cards'/f'{d}.json').read_bytes()).hexdigest() for d in DATES}}
(ROOT/'audit/market_validation.json').write_text(json.dumps(result, indent=2))
print(json.dumps({k:v for k,v in result.items() if k != 'card_sha256'}, indent=2))
raise SystemExit(bool(errors))
