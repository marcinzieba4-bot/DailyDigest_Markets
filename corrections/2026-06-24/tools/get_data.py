"""Download Treasury par curve 2026 and Yahoo daily closes into work/data (same file layout as the earlier sessions)."""
import urllib.request, json, csv, datetime as dt, sys, os
D = sys.argv[1]; H = {'User-Agent': 'Mozilla/5.0'}
u = 'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/2026/all?type=daily_treasury_yield_curve&field_tdr_date_value=2026&page&_format=csv'
open(f'{D}/treasury_2026.csv', 'wb').write(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=60).read())
SYM = {'TNX': '^TNX', 'IRX': '^IRX', 'PLN_X': 'PLN=X', 'EURPLN_X': 'EURPLN=X', 'EPOL': 'EPOL', 'PKO_WA': 'PKO.WA', 'PEO_WA': 'PEO.WA',
       'PKN_WA': 'PKN.WA', 'KGH_WA': 'KGH.WA', 'PGE_WA': 'PGE.WA', 'ALE_WA': 'ALE.WA', 'DNP_WA': 'DNP.WA', 'CDR_WA': 'CDR.WA', 'LPP_WA': 'LPP.WA'}
p1 = int(dt.datetime(2026, 4, 1, tzinfo=dt.timezone.utc).timestamp()); p2 = int(dt.datetime(2026, 7, 10, tzinfo=dt.timezone.utc).timestamp())
for name, s in SYM.items():
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{urllib.request.quote(s)}?period1={p1}&period2={p2}&interval=1d'
    j = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=30))['chart']['result'][0]
    off = j['meta'].get('gmtoffset', 0)
    rows = [(dt.datetime.fromtimestamp(t + off, dt.timezone.utc).strftime('%Y-%m-%d'), c)
            for t, c in zip(j['timestamp'], j['indicators']['quote'][0]['close']) if c is not None]
    with open(f'{D}/yf_{name}.csv', 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['Date', 'Close']); w.writerows(rows)
    print(name, len(rows), rows[0][0], rows[-1][0])
