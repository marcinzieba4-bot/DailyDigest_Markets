"""fetch_market.py [TICKER ...] — download daily closes (Yahoo Finance chart API) and the US Treasury daily par yield
curve into ../data/. Without arguments it fetches the default universe. Each Yahoo row is stamped with the
exchange-local session date; crypto rows are UTC days (the candle dated X closes at X+1 00:00 UTC).

November 2025 set: retained observations stop at the 2025-11-28 close. A separate
request obtains split-event metadata through the retrieval date to reverse Yahoo's
retrospective unit scaling; later prices from that response are discarded. Future
corporate-action metadata is retained only in audit/, outside writers' inputs.
Returns use split-adjusted closes, while displayed price levels use as-traded units.
The universe follows the latest November tool (cards show only available tickers)."""
import urllib.request, urllib.parse, json, os, sys, time, csv, io, datetime as dt
import concurrent.futures as cf
from pathlib import Path
from zoneinfo import ZoneInfo
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
H = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
LAST = '2025-11-28'
P1, P2 = int(dt.datetime(2025, 8, 1, tzinfo=dt.timezone.utc).timestamp()), int(dt.datetime(2025, 12, 1, tzinfo=dt.timezone.utc).timestamp())
ACTION_P2 = int(dt.datetime(2026, 10, 29, tzinfo=dt.timezone.utc).timestamp())
AUDIT = Path(D).parent / 'audit'
# A spin-off cannot safely be undone as though it were an ordinary share split.
SUPPRESS_LEVEL = {'CMCSA': 'corporate-action/spin-off adjustment; quote percentage changes only'}
UNIVERSE = [
    # indices, volatility, dollar, rates proxies
    '^GSPC', '^NDX', '^RUT', '^DJI', '^VIX', '^SOX', 'DX-Y.NYB', '^TNX', '^IRX',
    # commodities
    'CL=F', 'BZ=F', 'NG=F', 'GC=F', 'SI=F', 'HG=F', 'PL=F', 'ZS=F',
    # crypto and crypto equities
    'BTC-USD', 'ETH-USD', 'SOL-USD', 'XRP-USD', 'DOGE-USD', 'IBIT', 'ETHA', 'COIN', 'MSTR', 'HOOD', 'CRCL', 'BMNR',
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
    'ASML', 'TSM', 'QCOM', 'ARM', 'MRVL', 'TXN', 'AMAT', 'LRCX', 'KLAC', 'DELL', 'ANET', 'SMCI', 'SNDK', 'WDC', 'STX',
    'CRDO', 'ALAB', 'LITE', 'COHR',
    # software, internet, fintech
    'CRM', 'NOW', 'ADBE', 'SNOW', 'DDOG', 'NET', 'PANW', 'CRWD', 'ZS', 'MDB', 'IBM', 'CSCO', 'APP', 'RDDT', 'SHOP',
    'UBER', 'SPOT', 'V', 'MA', 'PYPL', 'SOFI', 'AFRM', 'UPST', 'DKNG',
    # AI infrastructure / neoclouds / power / nuclear / quantum / space / speculative favourites
    'CRWV', 'NBIS', 'VRT', 'GEV', 'ETN', 'PWR', 'BE', 'OKLO', 'SMR', 'NNE', 'LEU', 'CCJ', 'IONQ', 'RGTI', 'QBTS',
    'RKLB', 'ASTS', 'JOBY', 'ACHR', 'MP', 'OPEN', 'BYND', 'HIMS', 'SOUN', 'CVNA', 'RIVN', 'LCID', 'GME', 'AMC',
    # financials
    'JPM', 'GS', 'BAC', 'WFC', 'C', 'MS', 'SCHW', 'BRK-B',
    # energy, materials, utilities
    'XOM', 'CVX', 'COP', 'OXY', 'SLB', 'FCX', 'NEM', 'AA', 'SCCO', 'NEE', 'CEG', 'VST', 'DUK', 'SO',
    # health care
    'LLY', 'UNH', 'NVO', 'PFE', 'MRK', 'ABBV', 'JNJ', 'MRNA', 'CVS', 'ISRG', 'VRTX', 'AMGN',
    # consumer, industrials, media
    'WMT', 'COST', 'HD', 'LOW', 'TGT', 'TJX', 'ROST', 'NKE', 'LULU', 'SBUX', 'MCD', 'CMG', 'KO', 'PEP', 'PG', 'DIS',
    'CMCSA', 'T', 'VZ', 'BA', 'CAT', 'GE', 'DE', 'LMT', 'RTX',
]


def get_chart(t, start, end):
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(t, safe="")}?period1={start}&period2={end}&interval=1d&events=div,splits'
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=25).read())['chart']['result'][0]

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
            tz = r['meta'].get('exchangeTimezoneName', 'UTC')
            zone = ZoneInfo(tz)
            split_rows = []
            for ev in splits.values():
                day = dt.datetime.fromtimestamp(ev['date'], zone).date().isoformat()
                ratio = float(ev['numerator']) / float(ev['denominator'])
                if ratio <= 0: raise ValueError('Invalid split factor')
                split_rows.append({'date': day, 'factor': ratio, 'ratio': ev.get('splitRatio')})
            q = r['indicators']['quote'][0]
            rows = []
            for ts, c in zip(r.get('timestamp', []), q['close']):
                if c is None: continue
                day = dt.datetime.fromtimestamp(ts, zone).date().isoformat()
                if day > LAST: continue
                factor = 1.0
                for event in split_rows:
                    if event['date'] > day: factor *= event['factor']
                rows.append((day, float(c), float(c) * factor))
            dd = {}
            for day, c, level in rows: dd[day] = (c, level)
            AUDIT.mkdir(exist_ok=True)
            (AUDIT / ('actions_' + t.replace('^', '_').replace('=', '_').replace('.', '_') + '.json')).write_text(json.dumps({'ticker': t, 'source': 'Yahoo Finance split events', 'purpose': 'mechanical reconstruction only; keep away from report writers', 'events': sorted(split_rows, key=lambda x: x['date'])}, indent=1))
            return {'ticker': t, 'tz': tz, 'currency': r['meta'].get('currency', ''),
                    'rows': [[day, round(pair[0], 8)] for day, pair in sorted(dd.items())],
                    'as_traded_rows': [[day, round(pair[1], 8)] for day, pair in sorted(dd.items())],
                    'level_restriction': SUPPRESS_LEVEL.get(t),
                    'price_change_basis': 'split-adjusted close, excluding dividends',
                    'price_level_basis': 'as-traded share units, reconstructed from Yahoo close and split events',
                    'source': 'Yahoo Finance daily chart API', 'max_kept_date': LAST}
        except Exception as e:
            err = e; time.sleep(2 * (a + 1))
    print('FAIL', t, err); return None


def treasury():
    out = {}
    for y in (2025,):
        url = (f'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{y}/all'
               f'?type=daily_treasury_yield_curve&field_tdr_date_value={y}&page&_format=csv')
        txt = urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=30).read().decode()
        for row in csv.DictReader(io.StringIO(txt)):
            m, d_, yy = row['Date'].split('/')
            day = f'{yy}-{m}-{d_}'
            if day > LAST: continue
            out[day] = {k: float(v) for k, v in row.items() if k != 'Date' and v}
    json.dump(dict(sorted(out.items())), open(os.path.join(D, 'treasury_par.json'), 'w'), indent=0)
    print('treasury', len(out), 'days, last', max(out))


if __name__ == '__main__':
    os.makedirs(D, exist_ok=True)
    ts = sys.argv[1:] or UNIVERSE
    if not sys.argv[1:]: treasury()
    def run(t):
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
    if any(x['status'] == 'failed' for x in result): raise SystemExit(1)
