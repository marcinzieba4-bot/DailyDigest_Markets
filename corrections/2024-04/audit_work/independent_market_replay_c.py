"""Independent April market replay. Never imports the producer or its validator.

The reviewer first read the acquisition/card/calendar code and retained inputs.
This executable evidence redoes source hashes, exact split metadata, session
selection, comparable returns, nominal levels and Treasury arithmetic separately.
Run without --accept for observations; --accept requires a final source freeze.
"""
from pathlib import Path
from collections import Counter
from decimal import Decimal
from zoneinfo import ZoneInfo
import argparse
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import math
import re
import urllib.parse
import exchange_calendars as xc

ROOT = Path(__file__).resolve().parents[1]
DATES = [dt.date(2024, 4, n).isoformat() for n in range(1, 31)
         if dt.date(2024, 4, n).weekday() < 5]
FIRST, LAST = '2024-02-01', '2024-04-29'
UTC = dt.timezone.utc
checks = Counter()
errors = []
bound = {}
samples = []
rounding_ties = []


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def read(name):
    path = ROOT / name
    blob = path.read_bytes()
    digest = sha(blob)
    if name in bound and digest != bound[name]:
        raise ValueError('Input changed during independent review: ' + name)
    bound[name] = digest
    return blob


def obj(name):
    return json.loads(read(name))


def check(condition, what, group):
    checks[group] += 1
    if not condition:
        errors.append(what)


def same(actual, expected, what, group):
    check(actual == expected, f'{what}: {actual!r} != {expected!r}', group)


def safe(ticker):
    return re.sub(r'[\^=.]', '_', ticker)


def local_day(stamp, zone):
    return dt.datetime.fromtimestamp(stamp, ZoneInfo(zone)).date().isoformat()


def calendar_for(ticker):
    # Explicit venue classification, separate from producer code imports.
    if ticker.endswith(('=X', '=F', '-USD')) or ticker == 'DX-Y.NYB':
        return None
    indices = {'^VIX': 'XCBF', '^NDX': 'XNAS', '^SOX': 'XNAS', '^N225': 'XTKS',
               '^KS11': 'XKRX', '^TWII': 'XTAI', '^HSI': 'XHKG', '^AXJO': 'XASX',
               '^FTSE': 'XLON', '^GDAXI': 'XETR', '^FCHI': 'XPAR',
               '^STOXX': 'XETR', '^STOXX50E': 'XETR'}
    if ticker in indices:
        return indices[ticker]
    venues = {'.WA': 'XWAR', '.DE': 'XETR', '.PA': 'XPAR', '.CO': 'XCSE',
              '.L': 'XLON', '.SW': 'XSWX', '.T': 'XTKS', '.KS': 'XKRX',
              '.SS': 'XSHG', '.HK': 'XHKG', '.AX': 'XASX'}
    return next((venue for suffix, venue in venues.items() if ticker.endswith(suffix)), 'XNYS')


def bp(a, b):
    return int((a - b) * 100)


def atomic(name, value):
    path = ROOT / name
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def run(accept):
    # Code and audit artifacts were actually read; hashes prevent silent rebinding.
    tools = ['fetch_market.py', 'build_cards.py', 'market_calendar_policy.py', 'validate_market.py']
    for name in tools:
        read('tools/' + name)
    read('audit_work/independent_market_replay_c.py')
    provenance = obj('code_provenance.json')
    adaptation = provenance['market_tool_adaptation']
    same(adaptation['dates'], DATES, 'Code provenance report dates', 'code_binding')
    same(adaptation['retained_price_window'], {'first': FIRST, 'last': LAST},
         'Code provenance retained window', 'code_binding')
    same(adaptation['tool_sha256'], {name: bound['tools/' + name] for name in tools},
         'Code provenance actual market tool hashes', 'code_binding')
    same(adaptation['runtime_packages']['exchange-calendars'], xc.__version__,
         'Code provenance calendar runtime', 'code_binding')
    fetch = obj('audit/market_fetch.json')
    if (ROOT / 'audit/market_fetch_initial.json').is_file():
        obj('audit/market_fetch_initial.json')
    check(all(r['status'] in {'ok', 'unavailable'} for r in fetch), 'Unresolved fetch failure', 'inventory')
    same(len({r['ticker'] for r in fetch}), len(fetch), 'Duplicate fetch ticker', 'inventory')
    retention = obj('audit/market_raw_retention.json')
    receipts = {r['ticker']: r for r in retention['sources']}
    same(len(receipts), len(retention['sources']), 'Duplicate retention receipt', 'inventory')
    processed = {}
    raw = {}
    nominal = {}
    split_factors = {}
    exact_events = {}
    for path in sorted((ROOT / 'data').glob('yf_*.json')):
        name = path.relative_to(ROOT).as_posix()
        data = obj(name)
        ticker = data['ticker']
        processed[ticker] = data
        receipt = receipts[ticker]
        source_blob = read(receipt['path'])
        plain = gzip.decompress(source_blob)
        same(sha(source_blob), receipt['retained_gzip_sha256'], ticker + ' gzip hash', 'raw_integrity')
        same(sha(plain), receipt['retained_uncompressed_sha256'], ticker + ' plain hash', 'raw_integrity')
        same(obj('audit/market_raw/' + safe(ticker) + '.retention.json'), receipt,
             ticker + ' consolidated/individual receipt', 'raw_integrity')
        chart = json.loads(plain)['chart']['result'][0]
        meta = chart['meta']
        zone = meta['exchangeTimezoneName']
        aliases = {ticker, 'USDJPY=X'} if ticker == 'JPY=X' else {ticker}
        check(meta['symbol'] in aliases, ticker + ' unexpected source identity ' + meta['symbol'], 'raw_integrity')
        check(set(meta) <= {'currency', 'symbol', 'exchangeName', 'fullExchangeName',
                           'instrumentType', 'timezone', 'exchangeTimezoneName', 'firstTradeDate'},
              ticker + ' leaked current quote metadata', 'retained_bounds')
        same(set(chart), {'meta', 'timestamp', 'indicators', 'events'}, ticker + ' retained chart fields', 'retained_bounds')
        same(set(chart['indicators']), {'quote'}, ticker + ' future/adjusted arrays', 'retained_bounds')
        same(set(chart['indicators']['quote'][0]), {'close'}, ticker + ' extra quote fields', 'retained_bounds')
        values = chart['indicators']['quote'][0]['close']
        stamps = chart['timestamp']
        same(len(values), len(stamps), ticker + ' raw parallel arrays', 'raw_integrity')
        same(stamps, sorted(set(stamps)), ticker + ' raw unique chronological timestamps', 'raw_integrity')
        for stamp in stamps:
            day = local_day(stamp, zone)
            check(FIRST <= day <= LAST, ticker + ' out-of-scope price ' + day, 'retained_bounds')
        same(receipt['first_retained_inclusive'], FIRST, ticker + ' lower bound', 'retained_bounds')
        same(receipt['final_retained_inclusive'], LAST, ticker + ' upper bound', 'retained_bounds')
        same(receipt['retained_last_exchange_local_date'], max(local_day(s, zone) for s in stamps),
             ticker + ' retained end date', 'retained_bounds')
        for removed in receipt['removed_out_of_scope_observations']:
            day = local_day(removed['timestamp'], zone)
            same(day, removed['exchange_local_date'], ticker + ' removed date', 'retained_bounds')
            check(day < FIRST or day > LAST, ticker + ' removed in-scope date', 'retained_bounds')
        action = obj('audit/actions_' + safe(ticker) + '.json')
        same(action['ticker'], ticker, ticker + ' action identity', 'split_reconstruction')
        same(len(action['exact_action_inputs']), 2, ticker + ' action request count', 'split_reconstruction')
        same([a['request'] for a in action['exact_action_inputs']], action['requests'],
             ticker + ' action request binding', 'split_reconstruction')
        # Merge exact event dictionaries using event IDs, as an external source replay.
        events = {}
        for source in action['exact_action_inputs']:
            check(set(source) == {'request', 'retained_exact_split_events', 'retained_identity_meta',
                                  'discarded_price_observations', 'discarded_meta_fields'},
                  ticker + ' action-only input fields', 'retained_bounds')
            check(source['retained_identity_meta']['symbol'] in aliases,
                  ticker + ' unexpected action source identity', 'split_reconstruction')
            events.update(source['retained_exact_split_events'])
        factors = []
        for event in events.values():
            factor = float(event['numerator']) / float(event['denominator'])
            check(math.isfinite(factor) and factor > 0, ticker + ' invalid exact split', 'split_reconstruction')
            factors.append((local_day(event['date'], zone), factor, event.get('splitRatio')))
        expected_actions = [{'date': day, 'factor': factor, 'ratio': ratio}
                            for day, factor, ratio in sorted(factors)]
        same(action['events'], expected_actions, ticker + ' summarized/exact splits', 'split_reconstruction')
        historical_events = {k: e for k, e in events.items() if FIRST <= local_day(e['date'], zone) <= LAST}
        same(chart['events']['splits'], historical_events, ticker + ' raw historical split events', 'split_reconstruction')
        same(action['requests'][0]['sha256'], receipt['original_network_response_sha256'],
             ticker + ' original network hash', 'raw_integrity')
        same(action['requests'][0]['url'], data['source_url'], ticker + ' historical request URL', 'source_requests')
        for index, request in enumerate(action['requests']):
            address = urllib.parse.urlsplit(request['url'])
            query = urllib.parse.parse_qs(address.query)
            same(address.scheme + '://' + address.netloc, 'https://query1.finance.yahoo.com',
                 ticker + ' request source host', 'source_requests')
            same(urllib.parse.unquote(address.path), '/v8/finance/chart/' + ticker,
                 ticker + ' request instrument', 'source_requests')
            same(query['interval'], ['1d'], ticker + ' request daily frequency', 'source_requests')
            same(query['events'], ['div,splits'], ticker + ' request action fields', 'source_requests')
            requested_first = int(query['period1'][0])
            requested_end = int(query['period2'][0])
            lower = int(dt.datetime(2024, 2, 1, tzinfo=UTC).timestamp())
            upper = int(dt.datetime(2024, 4, 30, tzinfo=UTC).timestamp())
            same(requested_first, lower if index == 0 else upper,
                 ticker + ' request lower bound ' + str(index), 'source_requests')
            if index == 0:
                same(requested_end, upper, ticker + ' history request upper bound', 'source_requests')
            else:
                fetched = dt.datetime.fromisoformat(request['fetched_at_utc']).timestamp()
                check(upper < requested_end <= fetched,
                      ticker + ' action-only request ends after retrieval', 'source_requests')
        same(data['source_response_sha256'], receipt['original_network_response_sha256'],
             ticker + ' processed network binding', 'raw_integrity')
        same(data['retained_source_path'], receipt['path'], ticker + ' retained path', 'raw_integrity')
        same(data['retained_source_sha256'], sha(plain), ticker + ' processed retained hash', 'raw_integrity')
        same(data['tz'], zone, ticker + ' exchange timezone', 'units')
        same(data['currency'], meta.get('currency', ''), ticker + ' source currency', 'units')
        records = []
        levels = []
        multipliers = {}
        for stamp, close in zip(stamps, values):
            if close is None:
                continue
            check(type(close) in (int, float) and math.isfinite(close) and close > 0,
                  ticker + ' invalid source price', 'raw_integrity')
            day = local_day(stamp, zone)
            multiplier = math.prod(factor for split_day, factor, ratio in factors if split_day > day)
            records.append([day, round(float(close), 8)])
            levels.append([day, round(float(close) * multiplier, 8)])
            multipliers[day] = multiplier
        same(records, data['rows'], ticker + ' source/processed comparable rows', 'raw_replay')
        same(levels, data['as_traded_rows'], ticker + ' source/processed nominal rows', 'raw_replay')
        same([r[0] for r in records], sorted({r[0] for r in records}),
             ticker + ' unique exchange-local sessions', 'raw_replay')
        expected_restriction = ticker in {'CMCSA', 'WDC'}
        same(bool(data.get('level_restriction')), expected_restriction,
             ticker + ' nominal-unit restriction', 'units')
        raw[ticker], nominal[ticker], split_factors[ticker], exact_events[ticker] = records, dict(levels), multipliers, factors

    same(set(receipts), set(processed), 'Retained/processed symbol inventory', 'inventory')
    same({r['ticker'] for r in fetch if r['status'] == 'ok'}, set(processed),
         'Successful-fetch/processed inventory', 'inventory')
    same({r['ticker'] for r in fetch if r['status'] == 'unavailable'}, {'NNE', 'NBIS'},
         'Unavailable acquisition inventory', 'inventory')
    allowed_data = {p.name for p in (ROOT / 'data').glob('*') if p.is_file()}
    same(allowed_data, {'yf_' + safe(t) + '.json' for t in processed} | {'treasury_par.json'},
         'Unexpected unreviewed data artifact', 'inventory')
    # Independently parse source CSV strings as Decimal, avoiding float basis-point error.
    treasury_source = obj('audit/treasury_source.json')
    csv_bytes = read('audit/treasury_retained.csv')
    same(sha(csv_bytes), treasury_source['retained_csv_sha256'], 'Treasury retained CSV hash', 'treasury')
    check(treasury_source['source_url'].startswith('https://home.treasury.gov/'),
          'Treasury source domain', 'treasury')
    treasury = {}
    for row in csv.DictReader(io.StringIO(csv_bytes.decode())):
        day = dt.datetime.strptime(row['Date'], '%m/%d/%Y').date().isoformat()
        check(FIRST <= day <= LAST and day not in treasury, 'Treasury scope/duplicate ' + day, 'treasury')
        treasury[day] = {key: Decimal(value) for key, value in row.items() if key != 'Date' and value}
    same(len(treasury), treasury_source['retained_row_count'], 'Treasury retained rows', 'treasury')
    same(sorted(treasury)[0], FIRST, 'Treasury first retained day', 'treasury')
    same(sorted(treasury)[-1], LAST, 'Treasury last retained day', 'treasury')
    tr_processed = obj('data/treasury_par.json')
    same(tr_processed, {d: {k: float(v) for k, v in row.items()} for d, row in sorted(treasury.items())},
         'Treasury exact source/processed cells', 'treasury')
    check('2024-03-29' not in treasury and '2024-02-19' not in treasury,
          'Treasury holiday observations incorrectly retained', 'treasury')
    for day in treasury_source['removed_out_of_scope_dates']:
        check(day < FIRST or day > LAST, 'Treasury removed in-scope day ' + day, 'treasury')
    same(treasury_source['original_source_row_count'],
         len(treasury) + len(treasury_source['removed_out_of_scope_dates']),
         'Treasury source row accounting', 'treasury')

    excluded = {'^TNX', '^IRX', 'OKLO', 'NNE', 'GE', 'NBIS', 'CRWV', 'SNDK'}
    identities = {'DJT': '2024-03-26', 'GEV': '2024-04-02'}
    future_units = {'CL=F': 'USD/bbl', 'BZ=F': 'USD/bbl', 'NG=F': 'USD/MMBtu',
                    'GC=F': 'USD/oz', 'SI=F': 'USD/oz', 'HG=F': 'USD/lb',
                    'PL=F': 'USD/oz', 'ZS=F': 'US cents/bu'}
    fx = {'EURUSD=X', 'JPY=X', 'AUDUSD=X', 'CNY=X', 'GBPUSD=X', 'PLN=X', 'EURPLN=X'}
    cards = {}
    close_checks = 0
    horizon_checks = 0
    missing_short = []
    venues = set()
    for date in DATES:
        card = obj('cards/' + date + '.json')
        cards[date] = card
        cutoff = dt.datetime.fromisoformat(date).replace(tzinfo=UTC)
        same(card['report_date'], date, date + ' report date', 'cutoff')
        same(card['cutoff_utc'], date + 'T00:00:00Z', date + ' UTC cutoff', 'cutoff')
        same(set(card['excluded_vendor_marks']['tickers']), fx, date + ' FX exclusion inventory', 'inventory')
        expected_tickers = set()
        for ticker, records in raw.items():
            if ticker in excluded or ticker.endswith('=X'):
                continue
            eligible = [r for r in records if identities.get(ticker, '0000-00-00') <= r[0] < date]
            if not eligible:
                check(ticker in card['unavailable_symbols'], date + ' missing unavailable identity ' + ticker, 'inventory')
                continue
            expected_tickers.add(ticker)
            check(ticker in card['markets'], date + ' missing eligible instrument ' + ticker, 'inventory')
            if ticker not in card['markets']:
                continue
            mark = card['markets'][ticker]
            session, close = eligible[-1]
            same(mark['session'], session, date + '/' + ticker + ' latest date', 'cutoff')
            check(session < date, date + '/' + ticker + ' report-day observation', 'cutoff')
            data = processed[ticker]
            same(mark['currency'], data['currency'], date + '/' + ticker + ' card currency', 'units')
            expected_unit = ('index points' if ticker.startswith('^') or ticker in {'DX-Y.NYB', '000001.SS'}
                             else future_units.get(ticker, data['currency']))
            same(mark['level_unit'], expected_unit, date + '/' + ticker + ' level unit', 'units')
            same(mark['return_unit'], '%', date + '/' + ticker + ' return unit', 'units')
            same(mark['tz'], data['tz'], date + '/' + ticker + ' timezone', 'units')
            if ticker.endswith('.L'):
                same(mark['currency'], 'GBp', date + '/' + ticker + ' pence versus pounds', 'units')
            if ticker in {'CMCSA', 'WDC'}:
                same(mark['close'], None, date + '/' + ticker + ' restricted nominal level', 'units')
                same(mark['ref_20s_close'], None, date + '/' + ticker + ' restricted reference level', 'units')
                check(bool(mark['level_restriction']), date + '/' + ticker + ' missing restriction note', 'units')
            else:
                same(mark['close'], format(nominal[ticker][session], ',.2f'), date + '/' + ticker + ' nominal close', 'card_replay')
            calendar_code = calendar_for(ticker)
            calendar_dates = None
            if calendar_code:
                venues.add(calendar_code)
                calendar = xc.get_calendar(calendar_code)
                first = max(records[0][0], identities.get(ticker, '0000-00-00'))
                # Select by actual UTC close, not by observation timestamps or weekdays.
                schedule = calendar.schedule.loc[first:(cutoff.date() - dt.timedelta(days=1)).isoformat()]
                completed = schedule[schedule['close'] < cutoff]
                calendar_dates = completed.index.strftime('%Y-%m-%d').tolist()
                same(session, calendar_dates[-1], date + '/' + ticker + ' actual latest exchange session', 'exchange_calendar')
                check(completed.iloc[-1]['close'].to_pydatetime() < cutoff,
                      date + '/' + ticker + ' exchange close after cutoff', 'exchange_calendar')
                same([r[0] for r in eligible], calendar_dates,
                     date + '/' + ticker + ' all retained cash sessions/no gaps', 'exchange_calendar')
                close_checks += 1
            elif ticker.endswith('-USD'):
                close_time = dt.datetime.fromisoformat(session).replace(tzinfo=UTC) + dt.timedelta(days=1)
                check(close_time <= cutoff, date + '/' + ticker + ' crypto candle incomplete', 'crypto_cutoff')
                same(session, (cutoff.date() - dt.timedelta(days=1)).isoformat(),
                     date + '/' + ticker + ' latest completed UTC candle', 'crypto_cutoff')
                same([r[0] for r in eligible],
                     [(dt.date.fromisoformat(eligible[0][0]) + dt.timedelta(days=n)).isoformat()
                      for n in range(len(eligible))], date + '/' + ticker + ' crypto daily continuity', 'crypto_cutoff')
            for horizon in (1, 5, 20):
                if len(eligible) <= horizon:
                    same(mark.get(f'chg_{horizon}s_pct'), None, date + '/' + ticker + ' unavailable return ' + str(horizon), 'short_histories')
                    same(mark.get(f'ref_{horizon}s_session'), None, date + '/' + ticker + ' unavailable reference ' + str(horizon), 'short_histories')
                    check(bool(mark.get('history_limitation')), date + '/' + ticker + ' short history disclosure', 'short_histories')
                    missing_short.append({'date': date, 'ticker': ticker, 'horizon': horizon, 'observations': len(eligible)})
                    if horizon == 20:
                        same(mark['ref_20s_close'], None, date + '/' + ticker + ' unavailable ref20 level', 'short_histories')
                    continue
                earlier, previous = eligible[-1-horizon]
                # Arithmetic on independently re-extracted rounded source closes.
                exact_return = (Decimal(str(close)) - Decimal(str(previous))) / Decimal(str(previous)) * 100
                expected_return = exact_return.quantize(Decimal('0.01'))
                actual_return = Decimal(str(mark[f'chg_{horizon}s_pct']))
                # At exactly half a display unit either nearest endpoint is valid;
                # equivalent binary-float formula order can choose opposite ties.
                valid_tie = abs(actual_return - exact_return) == Decimal('0.005')
                check(actual_return == expected_return or valid_tie,
                      date + '/' + ticker + ' return ' + str(horizon) + ': ' +
                      str(actual_return) + ' versus exact ' + str(exact_return), 'card_replay')
                if valid_tie and actual_return != expected_return:
                    rounding_ties.append({'date': date, 'ticker': ticker, 'horizon': horizon,
                                          'exact_pct': str(exact_return), 'card_pct': str(actual_return),
                                          'finding': 'Valid nearest hundredth at exact half; binary-float producer formula rounds away from zero here.'})
                same(mark[f'ref_{horizon}s_session'], earlier,
                     date + '/' + ticker + ' reference ' + str(horizon), 'card_replay')
                if calendar_dates:
                    same(earlier, calendar_dates[-1-horizon],
                         date + '/' + ticker + ' calendar horizon ' + str(horizon), 'exchange_calendar')
                if horizon == 20:
                    if ticker not in {'CMCSA', 'WDC'}:
                        same(mark['ref_20s_close'], format(nominal[ticker][earlier], ',.2f'),
                             date + '/' + ticker + ' nominal ref20', 'card_replay')
                    changed = abs(split_factors[ticker][session] / split_factors[ticker][earlier] - 1) > 0.000001
                    same(mark['reference_share_units_differ'], changed,
                         date + '/' + ticker + ' split reference warning', 'split_reconstruction')
                    same(bool(mark.get('reference_level_note')), changed,
                         date + '/' + ticker + ' split warning prose', 'split_reconstruction')
                horizon_checks += 1
            if ticker == '^VIX':
                for horizon in (1, 20):
                    expected = round(close - eligible[-1-horizon][1], 2)
                    same(mark[f'chg_{horizon}s_pts'], expected,
                         date + ' VIX points ' + str(horizon), 'card_replay')
            check('vendor corrections' in mark['vintage_note'], date + '/' + ticker + ' current-vintage disclosure', 'scope')
            check('excluding dividends' in mark['price_change_basis'], date + '/' + ticker + ' price-return disclosure', 'scope')
            same(mark['source_url'], data['source_url'], date + '/' + ticker + ' source URL binding', 'scope')
        same(set(card['markets']), expected_tickers, date + ' complete permitted card universe', 'inventory')
        check(not card['excluded_instruments'], date + ' unexplained stale-source exclusion', 'exchange_calendar')
        check(not (set(card['markets']) & (excluded | fx)), date + ' prohibited mark exposed', 'inventory')
        # Treasury: prior valid observations, never assumed calendar-day windows.
        days = sorted(d for d in treasury if d < date)
        latest = treasury[days[-1]]
        old20 = treasury[days[-21]]
        tr = card['treasury']
        same(tr['prior_close_date'], days[-1], date + ' Treasury last observation', 'treasury')
        same(tr['obs20_earlier_date'], days[-21], date + ' Treasury 20 observation date', 'treasury')
        same(tr['prior_1obs_date'], days[-2], date + ' Treasury prior observation date', 'treasury')
        same(tr['prior_5obs_date'], days[-6], date + ' Treasury five observation date', 'treasury')
        keys = {'2y': '2 Yr', '10y': '10 Yr', '3m': '3 Mo', '5y': '5 Yr', '30y': '30 Yr', '1y': '1 Yr'}
        same(tr['prior_close_pct'], {key: f'{latest[column]:.2f}%' for key, column in keys.items()},
             date + ' Treasury levels percent', 'treasury')
        same(tr['obs20_earlier_pct'], {key: f'{old20[keys[key]]:.2f}%' for key in ('2y', '10y')},
             date + ' Treasury prior20 levels', 'treasury')
        spread = bp(latest['10 Yr'], latest['2 Yr'])
        same(tr['spread_10y_2y_bps'], spread, date + ' Treasury 10Y2Y basis points', 'treasury')
        same(tr['spread_10y_3m_bps'], bp(latest['10 Yr'], latest['3 Mo']), date + ' Treasury 10Y3M', 'treasury')
        same(tr['spread_30y_10y_bps'], bp(latest['30 Yr'], latest['10 Yr']), date + ' Treasury 30Y10Y', 'treasury')
        for horizon in (1, 5, 20):
            old = treasury[days[-1-horizon]]
            expected = {key: bp(latest[keys[key]], old[keys[key]]) for key in ('2y', '10y')}
            if horizon == 20:
                expected.update({key: bp(latest[keys[key]], old[keys[key]]) for key in ('3m', '30y')})
                expected['spread'] = spread - bp(old['10 Yr'], old['2 Yr'])
            same(tr[f'chg_{horizon}obs_bps'], expected, date + ' Treasury changes ' + str(horizon), 'treasury')
        check(spread < 0 and tr['curve_shape'] == 'inverted', date + ' Treasury curve shape', 'treasury')
        c2, c10 = tr['chg_20obs_bps']['2y'], tr['chg_20obs_bps']['10y']
        descriptor = tr['curve_move_20obs']
        if abs(c2) < 4 and abs(c10) < 4:
            same(descriptor, 'little changed', date + ' Treasury move', 'treasury')
        elif c2 == c10:
            check(descriptor.startswith('parallel rally' if c2 < 0 else 'parallel selloff'), date + ' Treasury parallel move', 'treasury')
        else:
            check(('steepening' in descriptor) == (c10 > c2), date + ' Treasury spread direction', 'treasury')
            if c2 > 0 and c10 > 0:
                check(descriptor.startswith('bear'), date + ' Treasury bear move', 'treasury')
            if c2 < 0 and c10 < 0:
                check(descriptor.startswith('bull'), date + ' Treasury bull move', 'treasury')
        if date in {'2024-04-01', '2024-04-03', '2024-04-17', '2024-04-22', '2024-04-30'}:
            samples.append({'date': date, 'treasury': tr, 'selected_marks':
                            {ticker: {key: card['markets'][ticker].get(key) for key in
                                      ('session', 'close', 'level_unit', 'chg_1s_pct', 'chg_20s_pct',
                                       'ref_20s_session', 'ref_20s_close', 'reference_share_units_differ')}
                             for ticker in ('NVDA', 'MSTR', 'SMCI', 'BTC-USD', '^VIX', 'CL=F',
                                            'DX-Y.NYB', 'DJT', 'GEV', 'ETFBW20TR.WA', 'SHEL.L')
                             if ticker in card['markets']}})

    # Explicit identity/holiday/split probes make the difficult boundaries reviewable.
    same(cards['2024-04-01']['treasury']['prior_close_date'], '2024-03-28', 'Easter Monday Treasury prior close', 'boundary_probes')
    for ticker in ('^GSPC', 'SPY', 'NVDA', 'DJT'):
        same(cards['2024-04-01']['markets'][ticker]['session'], '2024-03-28', ticker + ' Good Friday omitted', 'boundary_probes')
    same(cards['2024-04-01']['markets']['BTC-USD']['session'], '2024-03-31', 'Weekend crypto completed candle', 'boundary_probes')
    for date in ('2024-04-01', '2024-04-02'):
        check('GEV' not in cards[date]['markets'], date + ' GEV pre-regular listing quotes', 'boundary_probes')
    same(cards['2024-04-03']['markets']['GEV']['session'], '2024-04-02', 'GEV regular listing starts', 'boundary_probes')
    same(cards['2024-04-03']['markets']['GEV']['prior_observations'], 1, 'GEV excludes when-issued observations', 'boundary_probes')
    same(cards['2024-04-01']['markets']['DJT']['prior_observations'], 3, 'DJT excludes DWAC identity history', 'boundary_probes')
    same(cards['2024-04-01']['markets']['DJT']['chg_20s_pct'], None, 'DJT long return unavailable', 'boundary_probes')
    for ticker, day, expected_factor in [('NVDA', '2024-03-28', 10), ('MSTR', '2024-03-28', 10),
                                         ('SMCI', '2024-03-28', 10), ('CMG', '2024-03-28', 50)]:
        same(split_factors[ticker][day], expected_factor, ticker + ' future split nominal reconstruction', 'boundary_probes')
    same(cards['2024-04-01']['markets']['SHEL.L']['level_unit'], 'GBp', 'UK pence units', 'boundary_probes')
    for ticker in ('ALAB', 'RDDT'):
        same(cards['2024-04-01']['markets'][ticker]['chg_20s_pct'], None, ticker + ' new listing no invented long return', 'boundary_probes')
    validation = obj('audit/market_validation.json')
    check(validation.get('passed') is True and not validation.get('errors'), 'Producer validator did not pass', 'cross_check')
    same(validation['card_sha256'], {date: bound['cards/' + date + '.json'] for date in DATES},
         'Existing validator bound to current actual card bytes', 'cross_check')
    same(validation['raw_symbols'], len(processed), 'Existing validator source count', 'cross_check')
    same(validation['tool_sha256'], {name: bound['tools/' + name] for name in tools},
         'Existing validator actual tool hashes', 'cross_check')
    same(validation['source_retention_sha256'], bound['audit/market_raw_retention.json'],
         'Existing validator actual retained-source receipt', 'cross_check')
    same(validation['actual_exchange_close_checks'], close_checks, 'Independent close-check population', 'cross_check')
    order = lambda row: (row['date'], row['ticker'], row['horizon'], row['observations'])
    same(sorted(validation['short_inception_histories'], key=order), sorted(missing_short, key=order),
         'Independent short-history population', 'cross_check')
    # Prove bytes did not mutate while the independent checks were running.
    for name, digest in list(bound.items()):
        same(sha((ROOT / name).read_bytes()), digest, 'Stable reviewed input ' + name, 'stability')
    freeze = ROOT / 'audit/source_freeze.json'
    freeze_hash = None
    if freeze.is_file():
        frozen = obj('audit/source_freeze.json')
        freeze_hash = bound['audit/source_freeze.json']
        check(frozen.get('status') == 'all_22_ready', 'Source freeze not finalized', 'binding')
        same([row['date'] for row in frozen['dates']], DATES, 'Source freeze exact April dates', 'binding')
    elif accept:
        errors.append('Final source_freeze.json required before market acceptance')
    result = {'status': 'accepted' if accept and not errors else ('failed' if errors else 'replayed_awaiting_source_freeze'),
              'passed': not errors, 'dates': DATES, 'errors': errors,
              'reviewer': '/root/nonretail_c (independent of market acquisition, card building and original validation)',
              'reviewed_at_utc': dt.datetime.now(UTC).isoformat(),
              'review_scope': 'Market source pipeline and actual retained source/card bytes only; report prose is outside this acceptance.',
              'independent_method': 'No producer or original validator imported. Re-extracted every historical timestamp/close, reconstructed nominal units from exact split numerator/denominator inputs, independently selected actual UTC-closed cash sessions, recomputed every 1/5/20-observation return, and recomputed official Treasury values from retained CSV strings using Decimal.',
              'assertions': sum(checks.values()), 'assertion_groups': dict(checks),
              'raw_symbols': len(processed), 'retained_price_rows': sum(len(r) for r in raw.values()),
              'cash_actual_close_checks': close_checks, 'available_return_horizons': horizon_checks,
              'calendar_venues': sorted(venues), 'exchange_calendar_package': xc.__version__,
              'exact_half_hundredth_rounding_observations': rounding_ties,
              'short_inception_histories': missing_short,
              'card_sha256': {date: bound['cards/' + date + '.json'] for date in DATES},
              'source_freeze_sha256': freeze_hash, 'input_sha256': dict(sorted(bound.items())),
              'manual_code_review': [
                  'Acquisition preserves exact bounded historical timestamp/close pairs and whitelisted identity metadata; full original network responses are not retained, so their recorded hashes are commitments rather than a byte replay claim.',
                  'Future request inputs retain split-event metadata only. Future quote arrays and current quote metadata are discarded. Post-April split metadata is used solely to restore historical share units, never to supply report facts.',
                  'Producer differentiates comparable split-adjusted price returns from as-traded nominal levels; dividends are excluded. CMCSA/WDC nominal levels are withheld because distribution adjustments cannot be certified as ordinary splits.',
                  'Cash instruments use independent actual exchange sessions; latest gaps omit the instrument and horizon gaps suppress metrics rather than shift or fill them. This retained set has no cash-session gaps.',
                  'DJT begins with its March 26 operating-company ticker identity; GEV begins April 2 regular-way trading. GE/OKLO/NNE/NBIS/CRWV/SNDK are withheld with explicit identity/history limitations.',
                  'All numeric spot-FX marks/returns are excluded from writer cards. DXY is an index with index-point levels. Futures units, UK pence, VIX point moves and crypto UTC candle boundaries were checked.',
                  'The historical JPY=X request is labeled USDJPY=X by Yahoo in one response; this is the explicit USD/JPY vendor alias, and all numeric FX remains outside writer cards. Two exact half-hundredth price returns have valid nearest display rounding despite equivalent floating-point formula ordering selecting opposite tie directions.',
                  'Treasury data use official par yields, prior actual observation dates and basis-point arithmetic. Good Friday is absent; April 1 uses March 28. Report-day observations are never selected.'
              ],
              'limitations': [
                  'History was retrieved retrospectively and may include vendor or Treasury corrections; original unrevised publication vintage is not certified.',
                  'Retained historical pairs can be replayed exactly, but full original Yahoo/Treasury network responses were not retained. Original-response hashes alone cannot establish byte-for-byte original response contents.',
                  'Futures and DXY use bounded vendor daily observations rather than an independent official settlement tape; numeric spot FX is excluded.',
                  'No source-headline semantics, publication-clock news screening or report prose is accepted by this market-only review.'
              ]}
    atomic('audit_work/independent_market_replay_observations.json', result)
    atomic('audit_work/independent_market_boundary_probes.json', samples)
    if accept and not errors:
        atomic('audit/independent_market_review.json', result)
    print(json.dumps({key: result[key] for key in ('status', 'passed', 'assertions', 'assertion_groups',
          'raw_symbols', 'retained_price_rows', 'cash_actual_close_checks', 'available_return_horizons', 'errors')}, indent=2))
    return bool(errors)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--accept', action='store_true')
    raise SystemExit(run(parser.parse_args().accept))
