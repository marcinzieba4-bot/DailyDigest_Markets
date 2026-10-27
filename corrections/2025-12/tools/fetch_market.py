"""fetch_market.py [TICKER ...] — download daily closes (Yahoo Finance chart API) and the US Treasury daily par yield
curve into ../data/. Without arguments it fetches the default universe. Each Yahoo row is stamped with the
exchange-local session date; crypto rows are UTC days (the candle dated X closes at X+1 00:00 UTC)."""
import urllib.request, json, os, sys, time, csv, io, datetime as dt
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
H = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
P1, P2 = int(dt.datetime(2025, 9, 1).timestamp()), int(dt.datetime(2026, 3, 3).timestamp())
UNIVERSE = [
    '^GSPC', '^NDX', '^RUT', '^DJI', '^VIX', 'DX-Y.NYB', '^TNX', '^IRX',
    'CL=F', 'BZ=F', 'NG=F', 'GC=F', 'SI=F', 'HG=F',
    'BTC-USD', 'ETH-USD', 'SOL-USD', 'IBIT', 'COIN', 'MSTR',
    'EURUSD=X', 'JPY=X', 'AUDUSD=X', 'CNY=X', 'GBPUSD=X', 'PLN=X', 'EURPLN=X',
    'EPOL', 'WIG20.WA', 'PKO.WA', 'PKN.WA', 'KGH.WA', 'PZU.WA', 'PEO.WA', 'ALE.WA', 'DNP.WA', 'CDR.WA', 'LPP.WA', 'PGE.WA',
    '^STOXX50E', '^STOXX', '^GDAXI', '^FCHI', '^FTSE', 'EXV5.DE', '^N225', '000300.SS', '^HSI', 'FXI', 'KWEB', '^AXJO',
    'XLK', 'XLC', 'XLF', 'XLE', 'XLI', 'XLY', 'XLP', 'XLV', 'XLB', 'XLRE', 'XLU', 'SOXX', 'SMH', 'IWM', 'SPY', 'QQQ',
    'HYG', 'LQD', 'TLT', 'IEF', 'GLD', 'SLV', 'USO',
    'ASML', 'TSM', 'NVDA', 'AMD', 'AVGO', 'MU', 'INTC', 'MSFT', 'AAPL', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NFLX', 'ORCL',
    'PLTR', 'JPM', 'GS', 'BAC', 'XOM', 'CVX', 'LLY', 'UNH', 'WMT', 'COST', 'HD', 'NKE', 'DIS', 'BA', 'CAT', 'GE',
    'VWAGY', 'STLA', 'BMW.DE', 'MBG.DE', 'VOW3.DE', 'RNO.PA', 'NEE', 'CEG', 'VST', 'FCX', 'NEM',
]

def yahoo(t):
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(t)}?period1={P1}&period2={P2}&interval=1d'
    for a in range(4):
        try:
            j = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=25).read())
            r = j['chart']['result'][0]
            off = r['meta'].get('gmtoffset', 0)
            q = r['indicators']['quote'][0]
            rows = []
            for ts, c in zip(r.get('timestamp', []), q['close']):
                if c is None: continue
                day = dt.datetime.fromtimestamp(ts + off, dt.timezone.utc).date().isoformat()
                rows.append((day, round(c, 6)))
            dd = {}
            for day, c in rows: dd[day] = c                       # last row per local day wins
            return sorted(dd.items()), r['meta'].get('exchangeTimezoneName', ''), r['meta'].get('currency', '')
        except Exception as e:
            err = e; time.sleep(2 * (a + 1))
    print('FAIL', t, err); return None

def treasury():
    out = {}
    for y in (2025, 2026):
        url = (f'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{y}/all'
               f'?type=daily_treasury_yield_curve&field_tdr_date_value={y}&page&_format=csv')
        txt = urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=30).read().decode()
        for row in csv.DictReader(io.StringIO(txt)):
            m, d_, yy = row['Date'].split('/')
            out[f'{yy}-{m}-{d_}'] = {k: float(v) for k, v in row.items() if k != 'Date' and v}
    json.dump(dict(sorted(out.items())), open(os.path.join(D, 'treasury_par.json'), 'w'), indent=0)
    print('treasury', len(out), 'days')

import urllib.parse
if __name__ == '__main__':
    os.makedirs(D, exist_ok=True)
    ts = sys.argv[1:] or UNIVERSE
    if not sys.argv[1:]: treasury()
    for t in ts:
        r = yahoo(t)
        if not r: continue
        rows, tz, cur = r
        json.dump({'ticker': t, 'tz': tz, 'currency': cur, 'rows': rows},
                  open(os.path.join(D, 'yf_' + t.replace('^', '_').replace('=', '_').replace('.', '_') + '.json'), 'w'))
        print(t, len(rows), rows[-1] if rows else None, tz, flush=True)
        time.sleep(0.3)
