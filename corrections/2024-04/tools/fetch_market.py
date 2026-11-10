"""fetch_market.py [TICKER ...] — download daily closes (Yahoo Finance chart API) and the US Treasury daily par yield
curve into ../data/. Without arguments it fetches the default universe. Each Yahoo row is stamped with the
exchange-local session date; crypto rows are UTC days (the candle dated X closes at X+1 00:00 UTC).

April 2024 set: retained observations stop before the final report cutoff, 2024-04-30 00:00 UTC. A separate
request obtains split-event metadata through the retrieval date to reverse Yahoo's
retrospective unit scaling; later prices from that response are discarded. Future
corporate-action metadata is retained only in audit/, outside writers' inputs.
Returns use split-adjusted closes, while displayed price levels use as-traded units.
The universe follows the corrected late-2026 tool (cards show only available tickers)."""
import urllib.request, urllib.parse, json, os, sys, time, csv, io, datetime as dt
import hashlib, math
import gzip
import concurrent.futures as cf
import argparse
from pathlib import Path
from zoneinfo import ZoneInfo
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
H = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
FIRST, LAST = '2024-02-01', '2024-04-29'
P1, P2 = int(dt.datetime(2024, 2, 1, tzinfo=dt.timezone.utc).timestamp()), int(dt.datetime(2024, 4, 30, tzinfo=dt.timezone.utc).timestamp())
ACTION_P2 = int(dt.datetime.now(dt.timezone.utc).timestamp())
AUDIT = Path(D).parent / 'audit'
KEEP_META = {'currency', 'symbol', 'exchangeName', 'fullExchangeName', 'instrumentType',
             'timezone', 'exchangeTimezoneName', 'firstTradeDate'}
# A spin-off cannot safely be undone as though it were an ordinary share split.
UNAVAILABLE = {'NNE': 'No eligible listed trading history before the April cutoffs', 'NBIS': 'No eligible April trading: shares remained halted until 2024-10-21; earlier Yandex rows are not Nebius trading metrics'}
SUPPRESS_LEVEL = {'CMCSA': 'corporate-action/spin-off adjustment; quote percentage changes only',
                  'WDC': 'Sandisk spin-off distribution adjustment is not an ordinary share split; quote percentage changes only'}
UNIVERSE = [
    # indices, volatility, dollar, rates proxies
    '^GSPC', '^NDX', '^RUT', '^DJI', '^VIX', '^SOX', 'DX-Y.NYB', '^TNX', '^IRX',
    # commodities
    'CL=F', 'BZ=F', 'NG=F', 'GC=F', 'SI=F', 'HG=F', 'PL=F', 'ZS=F',
    # crypto and crypto equities
    'BTC-USD', 'ETH-USD', 'SOL-USD', 'XRP-USD', 'DOGE-USD', 'IBIT', 'COIN', 'MSTR', 'HOOD', 'DJT',
    'MARA', 'RIOT', 'IREN', 'CIFR',
    # FX
    'EURUSD=X', 'JPY=X', 'AUDUSD=X', 'CNY=X', 'GBPUSD=X', 'PLN=X', 'EURPLN=X',
    # Poland
    'EPOL', 'ETFBW20TR.WA', 'PKO.WA', 'PKN.WA', 'KGH.WA', 'PZU.WA', 'PEO.WA', 'ALE.WA', 'DNP.WA', 'CDR.WA', 'LPP.WA',
    'PGE.WA', 'MBK.WA', 'PCO.WA', 'ACP.WA', 'XTB.WA', 'TPE.WA', 'JSW.WA', 'OPL.WA',
    # Europe
    '^STOXX50E', '^STOXX', '^GDAXI', '^FCHI', '^FTSE', 'EXV5.DE', 'FEZ', 'VGK',
    'BMW.DE', 'MBG.DE', 'VOW3.DE', 'RNO.PA', 'STLA', 'VWAGY', 'RHM.DE', 'SAP.DE', 'SIE.DE', 'AIR.PA', 'NOVO-B.CO',
    'SHEL.L', 'HSBA.L', 'BP.L', 'NESN.SW', 'MC.PA',
    # Japan, Korea, Taiwan, China, Australia
    '^N225', 'EWJ', '9984.T', '7203.T', '6758.T', '8035.T', '6857.T', '^KS11', '005930.KS', '000660.KS', '^TWII',
    '000001.SS', '^HSI', 'ASHR', 'FXI', 'KWEB', 'BABA', 'PDD', 'JD', 'BIDU', 'NIO', '0700.HK', '9988.HK', '1810.HK',
    '^AXJO', 'EWA', 'BHP.AX', 'CBA.AX', 'RIO.AX', 'LYC.AX', 'FMG.AX', 'CSL.AX',
    # US sectors, factors, bonds, commodity ETFs
    'XLK', 'XLC', 'XLF', 'XLE', 'XLI', 'XLY', 'XLP', 'XLV', 'XLB', 'XLRE', 'XLU', 'SOXX', 'SMH', 'IWM', 'SPY', 'QQQ',
    'HYG', 'LQD', 'TLT', 'IEF', 'SHY', 'EMB', 'GLD', 'SLV', 'USO', 'GDX', 'URA', 'COPX', 'ARKK', 'KRE', 'XBI', 'ITA',
    'TQQQ', 'SOXL',
    # mega-cap tech and semis
    'NVDA', 'AMD', 'AVGO', 'MU', 'INTC', 'MSFT', 'AAPL', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NFLX', 'ORCL', 'PLTR',
    'ASML', 'TSM', 'QCOM', 'ARM', 'MRVL', 'TXN', 'AMAT', 'LRCX', 'KLAC', 'DELL', 'ANET', 'SMCI', 'WDC', 'STX',
    'CRDO', 'ALAB', 'LITE', 'COHR',
    # software, internet, fintech
    'CRM', 'NOW', 'ADBE', 'SNOW', 'DDOG', 'NET', 'PANW', 'CRWD', 'ZS', 'MDB', 'IBM', 'CSCO', 'APP', 'RDDT', 'SHOP',
    'UBER', 'SPOT', 'V', 'MA', 'PYPL', 'SOFI', 'AFRM', 'UPST', 'DKNG',
    # AI infrastructure / neoclouds / power / nuclear / quantum / space / speculative favourites
    'NBIS', 'VRT', 'GEV', 'ETN', 'PWR', 'BE', 'OKLO', 'SMR', 'NNE', 'LEU', 'CCJ', 'IONQ', 'RGTI', 'QBTS',
    'RKLB', 'ASTS', 'JOBY', 'ACHR', 'MP', 'OPEN', 'BYND', 'HIMS', 'SOUN', 'CVNA', 'RIVN', 'LCID', 'GME', 'AMC',
    # financials
    'JPM', 'GS', 'BAC', 'WFC', 'C', 'MS', 'SCHW', 'BRK-B',
    # energy, materials, utilities
    'XOM', 'CVX', 'COP', 'OXY', 'SLB', 'FCX', 'NEM', 'AA', 'NEE', 'CEG', 'VST', 'DUK', 'SO',
    # health care
    'LLY', 'UNH', 'NVO', 'PFE', 'MRK', 'ABBV', 'JNJ', 'MRNA', 'CVS', 'ISRG', 'VRTX', 'AMGN',
    # consumer, industrials, media
    'WMT', 'COST', 'HD', 'LOW', 'TGT', 'TJX', 'ROST', 'NKE', 'LULU', 'SBUX', 'MCD', 'CMG', 'KO', 'PEP', 'PG', 'DIS',
    'CMCSA', 'T', 'VZ', 'BA', 'CAT', 'GE', 'DE', 'LMT', 'RTX',
]


def get_chart(t, start, end):
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(t, safe="")}?period1={start}&period2={end}&interval=1d&events=div,splits'
    raw = urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=25).read()
    payload = json.loads(raw)['chart']
    if payload.get('error') or not payload.get('result'):
        raise ValueError('Chart returned no valid series: ' + str(payload.get('error')))
    result = payload['result'][0]
    result['_raw_response'] = raw
    result['_retrieval'] = {'url': url, 'sha256': hashlib.sha256(raw).hexdigest(),
                            'fetched_at_utc': dt.datetime.now(dt.timezone.utc).isoformat()}
    return result

def retain_bounded_chart(t, result):
    """Keep historical arrays, discarding the API's current-market quote metadata."""
    payload = json.loads(result['_raw_response'])
    original = payload['chart']['result'][0]
    timestamps = original.get('timestamp', [])
    closes = original['indicators']['quote'][0]['close']
    if len(timestamps) != len(closes): raise ValueError('Raw timestamp/close length mismatch')
    zone = ZoneInfo(original['meta']['exchangeTimezoneName'])
    day_for = lambda ts: dt.datetime.fromtimestamp(ts, zone).date().isoformat()
    retained_pairs = [(ts, value) for ts, value in zip(timestamps, closes)
                      if FIRST <= day_for(ts) <= LAST]
    removed_pairs = [(ts, value) for ts, value in zip(timestamps, closes)
                     if not FIRST <= day_for(ts) <= LAST]
    source_splits = original.get('events', {}).get('splits', {})
    retained_splits = {key: value for key, value in source_splits.items()
                       if FIRST <= day_for(value['date']) <= LAST}
    retained = {'meta': {k: v for k, v in original['meta'].items() if k in KEEP_META},
                'timestamp': [ts for ts, value in retained_pairs],
                'indicators': {'quote': [{'close': [value for ts, value in retained_pairs]}]},
                'events': {'splits': retained_splits}}
    raw = json.dumps({'chart': {'result': [retained], 'error': None}}, ensure_ascii=False,
                     separators=(',', ':')).encode()
    directory = AUDIT / 'market_raw'; directory.mkdir(parents=True, exist_ok=True)
    name = t.replace('^', '_').replace('=', '_').replace('.', '_')
    path = directory / (name + '.json.gz')
    path.write_bytes(gzip.compress(raw, mtime=0))
    receipt = {'ticker': t, 'path': str(path.relative_to(AUDIT.parent)),
               'original_network_response_sha256': result['_retrieval']['sha256'],
               'retained_uncompressed_sha256': hashlib.sha256(raw).hexdigest(),
               'retained_gzip_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
               'removed_meta_fields': sorted(set(original['meta']) - KEEP_META),
               'historical_timestamp_and_close_arrays_unchanged': len(retained_pairs) == len(timestamps),
               'retained_historical_pairs_unchanged': True,
               'removed_out_of_scope_observation_count': len(timestamps) - len(retained_pairs),
               'removed_out_of_scope_observations': [{'timestamp': ts, 'exchange_local_date': day_for(ts)} for ts, value in removed_pairs],
               'removed_out_of_scope_split_events': sorted(set(source_splits) - set(retained_splits)),
               'discarded_indicator_fields': sorted(set(original['indicators']) - {'quote'}),
               'discarded_quote_fields': sorted(set(original['indicators']['quote'][0]) - {'close'}),
               'first_retained_inclusive': FIRST, 'final_retained_inclusive': LAST,
               'retained_last_exchange_local_date': max(dt.datetime.fromtimestamp(ts, zone).date().isoformat() for ts, value in retained_pairs),
               'retained_meta_fields': sorted(retained['meta'])}
    (directory / (name + '.retention.json')).write_text(json.dumps(receipt, indent=2))
    return receipt

def yahoo(t):
    err = None
    for a in range(4):
        try:
            r = get_chart(t, P1, P2)
            # Yahoo retrospectively scales quote.close for splits after the requested
            # history window. Only keep future ACTION metadata from this response,
            # never its price observations. This is mechanical unit reconstruction,
            # not information used for investment conclusions.
            after = get_chart(t, P2, ACTION_P2)
            splits = {**r.get('events', {}).get('splits', {}), **after.get('events', {}).get('splits', {})}
            tz = r['meta']['exchangeTimezoneName']
            zone = ZoneInfo(tz)
            split_rows = []
            for ev in splits.values():
                day = dt.datetime.fromtimestamp(ev['date'], zone).date().isoformat()
                ratio = float(ev['numerator']) / float(ev['denominator'])
                if not math.isfinite(ratio) or ratio <= 0: raise ValueError('Invalid split factor')
                split_rows.append({'date': day, 'factor': ratio, 'ratio': ev.get('splitRatio')})
            q = r['indicators']['quote'][0]
            if len(r.get('timestamp', [])) != len(q['close']): raise ValueError('Timestamp/close length mismatch')
            rows = []
            for ts, c in zip(r.get('timestamp', []), q['close']):
                if c is None: continue
                if isinstance(c, bool) or not isinstance(c, (int, float)) or not math.isfinite(c) or c <= 0:
                    raise ValueError('Invalid daily close')
                day = dt.datetime.fromtimestamp(ts, zone).date().isoformat()
                if not FIRST <= day <= LAST or (t == 'NBIS' and day < '2024-10-21'): continue
                factor = 1.0
                for event in split_rows:
                    if event['date'] > day: factor *= event['factor']
                rows.append((day, float(c), float(c) * factor))
            dd = {}
            for day, c, level in rows:
                if day in dd: raise ValueError('Duplicate exchange-local date ' + day)
                dd[day] = (c, level)
            if not dd: raise ValueError('No retained daily observations')
            AUDIT.mkdir(exist_ok=True)
            retained_source = retain_bounded_chart(t, r)
            action_inputs = []
            for chart in (r, after):
                action_inputs.append({'request': chart['_retrieval'],
                    'retained_exact_split_events': chart.get('events', {}).get('splits', {}),
                    'retained_identity_meta': {k: v for k, v in chart['meta'].items() if k in KEEP_META},
                    'discarded_price_observations': len(chart.get('timestamp', [])),
                    'discarded_meta_fields': sorted(set(chart['meta']) - KEEP_META)})
            (AUDIT / ('actions_' + t.replace('^', '_').replace('=', '_').replace('.', '_') + '.json')).write_text(json.dumps({'ticker': t, 'source': 'Yahoo Finance split events', 'purpose': 'mechanical reconstruction only; keep away from report writers', 'events': sorted(split_rows, key=lambda x: x['date']), 'requests': [r['_retrieval'], after['_retrieval']], 'exact_action_inputs': action_inputs}, indent=1))
            return {'ticker': t, 'tz': tz, 'currency': r['meta'].get('currency', ''),
                    'rows': [[day, round(pair[0], 8)] for day, pair in sorted(dd.items())],
                    'as_traded_rows': [[day, round(pair[1], 8)] for day, pair in sorted(dd.items())],
                    'level_restriction': SUPPRESS_LEVEL.get(t),
                    'price_change_basis': 'split-adjusted close, excluding dividends',
                    'price_level_basis': 'as-traded share units, reconstructed from Yahoo close and split events',
                    'source': 'Yahoo Finance daily chart API', 'source_url': r['_retrieval']['url'],
                    'retrieved_at_utc': r['_retrieval']['fetched_at_utc'],
                    'source_response_sha256': r['_retrieval']['sha256'], 'max_kept_date': LAST,
                    'retained_source_path': retained_source['path'],
                    'retained_source_sha256': retained_source['retained_uncompressed_sha256'],
                    'vintage_note': 'Retrospectively retrieved history may contain vendor corrections; original unrevised publication vintage is not asserted.'}
        except Exception as e:
            err = e; time.sleep(2 * (a + 1))
    print('FAIL', t, err); return None


def treasury():
    out = {}
    for y in (2024,):
        url = (f'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{y}/all'
               f'?type=daily_treasury_yield_curve&field_tdr_date_value={y}&page&_format=csv')
        for attempt in range(6):
            try:
                txt = urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=30).read().decode()
                break
            except Exception:
                if attempt == 5: raise
                time.sleep(min(2 ** attempt, 15))
        source_rows = list(csv.DictReader(io.StringIO(txt)))
        retained_rows = []
        removed_dates = []
        for row in source_rows:
            day = dt.datetime.strptime(row['Date'], '%m/%d/%Y').date().isoformat()
            if not FIRST <= day <= LAST:
                removed_dates.append(day)
                continue
            if day in out: raise ValueError('Duplicate Treasury observation date')
            out[day] = {k: float(v) for k, v in row.items() if k != 'Date' and v}
            retained_rows.append(row)
        AUDIT.mkdir(exist_ok=True)
        retained_csv = io.StringIO(); writer = csv.DictWriter(retained_csv, fieldnames=list(source_rows[0])); writer.writeheader()
        writer.writerows(retained_rows)
        (AUDIT / 'treasury_retained.csv').write_text(retained_csv.getvalue())
        (AUDIT / 'treasury_source.json').write_text(json.dumps({'source_url': url,
            'retrieved_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
            'response_sha256': hashlib.sha256(txt.encode()).hexdigest(), 'retained_last_date': LAST,
            'retained_first_date': FIRST, 'retained_exact_cell_strings': True,
            'retained_csv_sha256': hashlib.sha256(retained_csv.getvalue().encode()).hexdigest(),
            'original_source_row_count': len(source_rows), 'retained_row_count': len(retained_rows),
            'removed_out_of_scope_dates': sorted(removed_dates),
            'vintage_note': 'Daily observation dates do not assert original unrevised publication timestamps.'}, indent=1))
    json.dump(dict(sorted(out.items())), open(os.path.join(D, 'treasury_par.json'), 'w'), indent=0)
    print('treasury', len(out), 'days, last', max(out))


if __name__ == '__main__':
    os.makedirs(D, exist_ok=True)
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('tickers', nargs='*'); ap.add_argument('--resume', action='store_true')
    args = ap.parse_args(); ts = args.tickers or UNIVERSE
    if not args.tickers and not (args.resume and Path(D, 'treasury_par.json').exists()): treasury()
    def run(t):
        if t in UNAVAILABLE:
            result = {'ticker': t, 'status': 'unavailable', 'observations': 0, 'reason': UNAVAILABLE[t]}
            print(json.dumps(result), flush=True); return result
        fn = Path(D) / ('yf_' + t.replace('^', '_').replace('=', '_').replace('.', '_') + '.json')
        if args.resume and fn.exists():
            cached = json.loads(fn.read_text())
            before = [r for r in cached.get('rows', []) if r[0] < '2024-04-01']
            if cached.get('source_url') and (len(before) >= 21 or t == 'NBIS') and all(r[0] <= LAST for r in cached['rows']) and set(dict(cached['rows'])) == set(dict(cached.get('as_traded_rows', []))):
                result = {'ticker': t, 'status': 'ok', 'observations': len(cached['rows']), 'last': cached['rows'][-1][0], 'retrieval': 'reused frozen cache'}
                print(json.dumps(result), flush=True); return result
        r = yahoo(t)
        if not r: return {'ticker': t, 'status': 'failed'}
        json.dump(r,
                  open(os.path.join(D, 'yf_' + t.replace('^', '_').replace('=', '_').replace('.', '_') + '.json'), 'w'))
        result = {'ticker': t, 'status': 'ok', 'observations': len(r['rows']), 'last': r['rows'][-1][0] if r['rows'] else None}
        print(json.dumps(result), flush=True)
        return result
    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        result = list(pool.map(run, ts))
    AUDIT.mkdir(exist_ok=True)
    (AUDIT / 'market_fetch.json').write_text(json.dumps(result, indent=1))
    receipts = [json.loads(p.read_text()) for p in sorted((AUDIT / 'market_raw').glob('*.retention.json'))]
    if receipts:
        (AUDIT / 'market_raw_retention.json').write_text(json.dumps({
            'purpose': 'Exact historical quote arrays retained for independent replay; live quote metadata discarded. Original network and retained-source hashes are explicitly separate.',
            'sources': receipts}, indent=2) + '\n')
    if any(x['status'] == 'failed' for x in result): raise SystemExit(1)

