"""fetch_market.py [TICKER ...] — download daily closes (Yahoo Finance chart API) and the US Treasury daily par yield
curve into ../data/. Without arguments it fetches the default universe. Each Yahoo row is stamped with the
exchange-local session date; crypto rows are UTC days (the candle dated X closes at X+1 00:00 UTC).

November 2025 set: data stop at the 2025-11-28 close (period2 = 2025-12-01), so nothing dated after the last report
date is stored in this folder. The universe is the February / December one plus the names retail and the earnings
season were trading in October-November 2025 (cards only show tickers that are in the data)."""
import urllib.request, urllib.parse, json, os, sys, time, csv, io, datetime as dt
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
H = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
LAST = '2025-11-28'                                              # last report date in the set; nothing later is kept
P1, P2 = int(dt.datetime(2025, 8, 20).timestamp()), int(dt.datetime(2025, 12, 1).timestamp())
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


def yahoo(t):
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(t)}?period1={P1}&period2={P2}&interval=1d'
    err = None
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
                if day > LAST: continue
                rows.append((day, round(c, 6)))
            dd = {}
            for day, c in rows: dd[day] = c                       # last row per local day wins
            return sorted(dd.items()), r['meta'].get('exchangeTimezoneName', ''), r['meta'].get('currency', '')
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
    for t in ts:
        r = yahoo(t)
        if not r: continue
        rows, tz, cur = r
        json.dump({'ticker': t, 'tz': tz, 'currency': cur, 'rows': rows},
                  open(os.path.join(D, 'yf_' + t.replace('^', '_').replace('=', '_').replace('.', '_') + '.json'), 'w'))
        print(t, len(rows), rows[-1] if rows else None, tz, flush=True)
        time.sleep(0.3)
