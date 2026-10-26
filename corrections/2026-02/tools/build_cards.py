"""build_cards.py <dates> — per-report ground-truth market card from ../data/ (Yahoo daily closes, Treasury par curve).
Only observations dated strictly before the report date are used: the last completed session of each instrument
(exchange-local date < report date; crypto UTC day < report date, i.e. the candle that closed at the cutoff or earlier).
Changes: 1, 5 and 20 sessions (Treasury: 20 observations), as in the March retrospective briefings."""
import json, os, sys, glob, datetime as dt
T = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(T, '..', 'data'); OUT = os.path.join(T, '..', 'cards')
NAMES = {
    '^GSPC': 'S&P 500', '^NDX': 'Nasdaq 100', '^RUT': 'Russell 2000', '^DJI': 'Dow Jones Industrial Average', '^VIX': 'VIX',
    'DX-Y.NYB': 'US Dollar Index (DXY)', 'CL=F': 'WTI crude (front month, $/bbl)', 'BZ=F': 'Brent crude (front month, $/bbl)',
    'NG=F': 'Henry Hub natural gas (front month, $/MMBtu)', 'GC=F': 'Gold (front month, $/oz)', 'SI=F': 'Silver (front month, $/oz)',
    'HG=F': 'Copper (front month, $/lb)', 'BTC-USD': 'Bitcoin (USD)', 'ETH-USD': 'Ether (USD)', 'SOL-USD': 'Solana (USD)',
    'EURUSD=X': 'EUR/USD', 'JPY=X': 'USD/JPY', 'AUDUSD=X': 'AUD/USD', 'CNY=X': 'USD/CNY', 'GBPUSD=X': 'GBP/USD',
    'PLN=X': 'USD/PLN', 'EURPLN=X': 'EUR/PLN', 'EPOL': 'EPOL (iShares MSCI Poland ETF, USD)',
    'ETFBW20TR.WA': 'Beta ETF WIG20TR (PLN; WIG20 total-return tracker)',
    '^STOXX50E': 'Euro Stoxx 50', '^STOXX': 'STOXX Europe 600', '^GDAXI': 'DAX', '^FCHI': 'CAC 40', '^FTSE': 'FTSE 100',
    'EXV5.DE': 'iShares STOXX Europe 600 Automobiles & Parts ETF (EUR; SXAP tracker)', '^N225': 'Nikkei 225',
    '000001.SS': 'Shanghai Composite', '^HSI': 'Hang Seng', 'ASHR': 'ASHR (CSI 300 China A-shares ETF, USD)', 'FXI': 'FXI (China large-cap ETF, USD)',
    'KWEB': 'KWEB (China internet ETF, USD)', '^AXJO': 'S&P/ASX 200', 'IWM': 'IWM (Russell 2000 ETF)', 'SPY': 'SPY', 'QQQ': 'QQQ',
    'HYG': 'HYG (US high-yield bond ETF)', 'LQD': 'LQD (US investment-grade bond ETF)', 'TLT': 'TLT (20+Y Treasury ETF)',
    'IEF': 'IEF (7-10Y Treasury ETF)', 'GLD': 'GLD (gold ETF)', 'SLV': 'SLV (silver ETF)', 'USO': 'USO (oil ETF)',
    'IBIT': 'IBIT (iShares Bitcoin Trust)', 'SOXX': 'SOXX (semiconductor ETF)', 'SMH': 'SMH (semiconductor ETF)',
}
SKIP = {'^TNX', '^IRX'}          # the curve comes from the official Treasury par yields

def fmt(v, t):
    if t.endswith('=X'):
        return f'{v:,.4f}'
    if t in ('BTC-USD', 'ETH-USD') or v >= 1000:
        return f'{v:,.2f}'
    return f'{v:,.2f}'

def curve_shape(s):
    if s < 0: return 'inverted'
    if s < 25: return 'positive but very flat'
    if s < 60: return 'positively sloped but still flat by historical standards (long-run average about +90 to +100 bps)'
    if s < 100: return 'moderately steep, approaching the long-run average'
    return 'steep'

def curve_move(c2, c10):
    if abs(c2) < 4 and abs(c10) < 4: return 'little changed'
    if c10 >= c2 and c10 > 0: return 'bear steepening (both up, 10Y up more)' if c2 > 0 else 'steepening (10Y up, 2Y down/flat)'
    if c10 < c2 and c2 > 0: return 'bear flattening (both up, 2Y up more)' if c10 > 0 else 'flattening (2Y up, 10Y down/flat)'
    if c10 <= c2 and c10 < 0: return 'bull flattening (both down, 10Y down more)' if c2 < 0 else 'flattening (10Y down, 2Y up/flat)'
    if c2 < c10 and c2 < 0: return 'bull steepening (both down, 2Y down more)' if c10 < 0 else 'steepening (2Y down, 10Y up/flat)'
    return 'mixed'

def pct(a, b): return round((a / b - 1) * 100, 2)

def card(d):
    D = dt.date.fromisoformat(d)
    tr = json.load(open(os.path.join(DATA, 'treasury_par.json')))
    days = [k for k in sorted(tr) if k < d]
    p, p20 = days[-1], days[-21]
    pc, pr = tr[p], tr[p20]
    g = lambda r, k: r[k]
    y = {'2y': pc['2 Yr'], '10y': pc['10 Yr'], '3m': pc['3 Mo'], '5y': pc['5 Yr'], '30y': pc['30 Yr'], '1y': pc['1 Yr']}
    c2, c10 = round((pc['2 Yr'] - pr['2 Yr']) * 100), round((pc['10 Yr'] - pr['10 Yr']) * 100)
    sp = round((pc['10 Yr'] - pc['2 Yr']) * 100); sp20 = round((pr['10 Yr'] - pr['2 Yr']) * 100)
    treasury = {
        'source': 'US Treasury daily par yield curve', 'prior_close_date': p,
        'prior_close_pct': {k: f'{v:.2f}%' for k, v in y.items()},
        'spread_10y_2y_bps': sp, 'spread_10y_3m_bps': round((pc['10 Yr'] - pc['3 Mo']) * 100),
        'spread_30y_10y_bps': round((pc['30 Yr'] - pc['10 Yr']) * 100),
        'obs20_earlier_date': p20, 'obs20_earlier_pct': {'2y': f"{pr['2 Yr']:.2f}%", '10y': f"{pr['10 Yr']:.2f}%"},
        'chg_20obs_bps': {'2y': c2, '10y': c10, 'spread': sp - sp20, '3m': round((pc['3 Mo'] - pr['3 Mo']) * 100),
                          '30y': round((pc['30 Yr'] - pr['30 Yr']) * 100)},
        'prior_5obs_date': days[-6], 'chg_5obs_bps': {'2y': round((pc['2 Yr'] - tr[days[-6]]['2 Yr']) * 100),
                                                     '10y': round((pc['10 Yr'] - tr[days[-6]]['10 Yr']) * 100)},
        'curve_shape': curve_shape(sp), 'curve_move_20obs': curve_move(c2, c10),
    }
    mk = {}
    for f in sorted(glob.glob(os.path.join(DATA, 'yf_*.json'))):
        j = json.load(open(f)); t = j['ticker']
        if t in SKIP: continue
        rows = [r for r in j['rows'] if r[0] < d]
        if len(rows) < 22: continue
        (ld, lc), (d1, c1), (d5, c5), (d20, c20) = rows[-1], rows[-2], rows[-6], rows[-21]
        mk[t] = {'name': NAMES.get(t, t), 'session': ld, 'close': fmt(lc, t), 'currency': j.get('currency', ''),
                 'chg_1s_pct': pct(lc, c1), 'chg_5s_pct': pct(lc, c5), 'chg_20s_pct': pct(lc, c20),
                 'ref_20s_session': d20, 'ref_20s_close': fmt(c20, t), 'tz': j['tz']}
        if t == '^VIX':
            mk[t]['chg_1s_pts'], mk[t]['chg_20s_pts'] = round(lc - c1, 2), round(lc - c20, 2)
    label = D.strftime('%A, %B %d %Y')
    return {'report_date': d, 'label': label, 'cutoff_utc': f'{d}T00:00:00Z',
            'rule': 'every value is a completed observation dated strictly before the report date',
            'treasury': treasury, 'markets': mk}

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    for d in sys.argv[1:]:
        c = card(d)
        json.dump(c, open(os.path.join(OUT, f'{d}.json'), 'w'), ensure_ascii=False, indent=1)
        t = c['treasury']
        print(d, t['prior_close_date'], '2Y', t['prior_close_pct']['2y'], '10Y', t['prior_close_pct']['10y'], f"{t['spread_10y_2y_bps']:+d}bps",
              'SPX', c['markets']['^GSPC']['session'], c['markets']['^GSPC']['close'], 'BTC', c['markets']['BTC-USD']['session'],
              c['markets']['BTC-USD']['close'], len(c['markets']), 'instruments')
