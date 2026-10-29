"""build_cards.py <dates> — per-report ground-truth market card from ../data/ (Yahoo daily closes, Treasury par curve).
Only observations dated strictly before the report date are used: the last completed session of each instrument
(exchange-local date < report date; crypto UTC day < report date, i.e. the candle that closed at the cutoff or earlier).
Changes: 1, 5 and 20 sessions (Treasury: 20 observations), as in the earlier retrospective sets (February and December)."""
import json, os, sys, glob, datetime as dt
T = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(T, '..', 'data'); OUT = os.path.join(T, '..', 'cards')
NAMES = {
    '^GSPC': 'S&P 500', '^NDX': 'Nasdaq 100', '^RUT': 'Russell 2000', '^DJI': 'Dow Jones Industrial Average', '^VIX': 'VIX',
    '^SOX': 'PHLX Semiconductor Index (SOX)', 'DX-Y.NYB': 'US Dollar Index (DXY)',
    'CL=F': 'WTI crude (front month, $/bbl)', 'BZ=F': 'Brent crude (front month, $/bbl)',
    'NG=F': 'Henry Hub natural gas (front month, $/MMBtu)', 'GC=F': 'Gold (front month, $/oz)', 'SI=F': 'Silver (front month, $/oz)',
    'HG=F': 'Copper (front month, $/lb)', 'PL=F': 'Platinum (front month, $/oz)', 'ZS=F': 'Soybeans (front month, US cents/bu)',
    'BTC-USD': 'Bitcoin (USD)', 'ETH-USD': 'Ether (USD)', 'SOL-USD': 'Solana (USD)', 'XRP-USD': 'XRP (USD)',
    'DOGE-USD': 'Dogecoin (USD)', 'IBIT': 'IBIT (iShares Bitcoin Trust)', 'ETHA': 'ETHA (iShares Ethereum Trust)',
    'COIN': 'Coinbase Global (COIN)', 'MSTR': 'Strategy Inc (MSTR, bitcoin treasury company)', 'HOOD': 'Robinhood Markets (HOOD)',
    'CRCL': 'Circle Internet Group (CRCL, USDC issuer)', 'BMNR': 'BitMine Immersion Technologies (BMNR, ether treasury company)',
    'MARA': 'MARA Holdings (MARA, bitcoin miner)', 'RIOT': 'Riot Platforms (RIOT, bitcoin miner)',
    'IREN': 'IREN (IREN, bitcoin miner and AI cloud)', 'CIFR': 'Cipher Mining (CIFR, bitcoin miner and AI hosting)',
    'EURUSD=X': 'EUR/USD', 'JPY=X': 'USD/JPY', 'AUDUSD=X': 'AUD/USD', 'CNY=X': 'USD/CNY', 'GBPUSD=X': 'GBP/USD',
    'PLN=X': 'USD/PLN', 'EURPLN=X': 'EUR/PLN', 'EPOL': 'EPOL (iShares MSCI Poland ETF, USD)',
    'ETFBW20TR.WA': 'Beta ETF WIG20TR (PLN; WIG20 total-return tracker)',
    'PKO.WA': 'PKO Bank Polski (PKO.WA, PLN)', 'PKN.WA': 'Orlen (PKN.WA, PLN)', 'KGH.WA': 'KGHM Polska Miedz (KGH.WA, PLN)',
    'PZU.WA': 'PZU (PZU.WA, PLN)', 'PEO.WA': 'Bank Pekao (PEO.WA, PLN)', 'ALE.WA': 'Allegro (ALE.WA, PLN)',
    'DNP.WA': 'Dino Polska (DNP.WA, PLN)', 'CDR.WA': 'CD Projekt (CDR.WA, PLN)', 'LPP.WA': 'LPP (LPP.WA, PLN)',
    'PGE.WA': 'PGE (PGE.WA, PLN)', 'MBK.WA': 'mBank (MBK.WA, PLN)',
    'PCO.WA': 'Pepco Group (PCO.WA, PLN)', 'ACP.WA': 'Asseco Poland (ACP.WA, PLN)', 'XTB.WA': 'XTB (XTB.WA, PLN, retail broker)',
    'TPE.WA': 'Tauron (TPE.WA, PLN)', 'JSW.WA': 'JSW (JSW.WA, PLN, coking coal)', 'OPL.WA': 'Orange Polska (OPL.WA, PLN)',
    '^STOXX50E': 'Euro Stoxx 50', '^STOXX': 'STOXX Europe 600', '^GDAXI': 'DAX', '^FCHI': 'CAC 40', '^FTSE': 'FTSE 100',
    'EXV5.DE': 'iShares STOXX Europe 600 Automobiles & Parts ETF (EUR; SXAP tracker)', 'FEZ': 'FEZ (Euro Stoxx 50 ETF, USD)',
    'VGK': 'VGK (Europe ETF, USD)', 'BMW.DE': 'BMW (BMW.DE, EUR)', 'MBG.DE': 'Mercedes-Benz Group (MBG.DE, EUR)',
    'VOW3.DE': 'Volkswagen preference shares (VOW3.DE, EUR)', 'RNO.PA': 'Renault (RNO.PA, EUR)', 'STLA': 'Stellantis (STLA, USD line)',
    'VWAGY': 'Volkswagen (VWAGY, US ADR)', 'RHM.DE': 'Rheinmetall (RHM.DE, EUR)', 'SAP.DE': 'SAP (SAP.DE, EUR)',
    'SIE.DE': 'Siemens (SIE.DE, EUR)', 'AIR.PA': 'Airbus (AIR.PA, EUR)', 'NOVO-B.CO': 'Novo Nordisk (NOVO-B.CO, DKK)',
    'SHEL.L': 'Shell (SHEL.L, GBp)', 'HSBA.L': 'HSBC (HSBA.L, GBp)', 'BP.L': 'BP (BP.L, GBp)', 'NESN.SW': 'Nestle (NESN.SW, CHF)',
    'MC.PA': 'LVMH (MC.PA, EUR)',
    '^N225': 'Nikkei 225', 'EWJ': 'EWJ (Japan ETF, USD)', '9984.T': 'SoftBank Group (9984.T, JPY)',
    '7203.T': 'Toyota Motor (7203.T, JPY)', '6758.T': 'Sony Group (6758.T, JPY)', '8035.T': 'Tokyo Electron (8035.T, JPY)',
    '6857.T': 'Advantest (6857.T, JPY)', '^KS11': 'KOSPI', '005930.KS': 'Samsung Electronics (005930.KS, KRW)',
    '000660.KS': 'SK Hynix (000660.KS, KRW)', '^TWII': 'Taiwan Weighted Index (TAIEX)',
    '000001.SS': 'Shanghai Composite', '^HSI': 'Hang Seng', 'ASHR': 'ASHR (CSI 300 China A-shares ETF, USD)',
    'FXI': 'FXI (China large-cap ETF, USD)', 'KWEB': 'KWEB (China internet ETF, USD)', 'BABA': 'Alibaba (BABA, US ADR)',
    'PDD': 'PDD Holdings (PDD, US ADR)', 'JD': 'JD.com (JD, US ADR)', 'BIDU': 'Baidu (BIDU, US ADR)', 'NIO': 'NIO (NIO, US ADR)',
    '0700.HK': 'Tencent (0700.HK, HKD)', '9988.HK': 'Alibaba (9988.HK, HKD)', '1810.HK': 'Xiaomi (1810.HK, HKD)',
    '^AXJO': 'S&P/ASX 200', 'EWA': 'EWA (Australia ETF, USD)', 'BHP.AX': 'BHP Group (BHP.AX, AUD)',
    'CBA.AX': 'Commonwealth Bank of Australia (CBA.AX, AUD)', 'RIO.AX': 'Rio Tinto (RIO.AX, AUD)',
    'LYC.AX': 'Lynas Rare Earths (LYC.AX, AUD)', 'FMG.AX': 'Fortescue (FMG.AX, AUD)', 'CSL.AX': 'CSL (CSL.AX, AUD)',
    'IWM': 'IWM (Russell 2000 ETF)', 'SPY': 'SPY', 'QQQ': 'QQQ', 'HYG': 'HYG (US high-yield bond ETF)',
    'LQD': 'LQD (US investment-grade bond ETF)', 'TLT': 'TLT (20+Y Treasury ETF)', 'IEF': 'IEF (7-10Y Treasury ETF)',
    'SHY': 'SHY (1-3Y Treasury ETF)', 'EMB': 'EMB (USD emerging-market bond ETF)', 'GLD': 'GLD (gold ETF)', 'SLV': 'SLV (silver ETF)',
    'USO': 'USO (oil ETF)', 'GDX': 'GDX (gold miners ETF)', 'URA': 'URA (uranium ETF)', 'COPX': 'COPX (copper miners ETF)',
    'ARKK': 'ARKK (ARK Innovation ETF)', 'KRE': 'KRE (regional banks ETF)', 'XBI': 'XBI (biotech ETF)',
    'ITA': 'ITA (aerospace & defense ETF)', 'TQQQ': 'TQQQ (3x Nasdaq 100 ETF)', 'SOXL': 'SOXL (3x semiconductor ETF)',
    'SOXX': 'SOXX (semiconductor ETF)', 'SMH': 'SMH (semiconductor ETF)',
    'NVDA': 'Nvidia (NVDA)', 'AMD': 'Advanced Micro Devices (AMD)', 'AVGO': 'Broadcom (AVGO)', 'MU': 'Micron Technology (MU)',
    'INTC': 'Intel (INTC)', 'MSFT': 'Microsoft (MSFT)', 'AAPL': 'Apple (AAPL)', 'GOOGL': 'Alphabet Class A (GOOGL)',
    'AMZN': 'Amazon (AMZN)', 'META': 'Meta Platforms (META)', 'TSLA': 'Tesla (TSLA)', 'NFLX': 'Netflix (NFLX)',
    'ORCL': 'Oracle (ORCL)', 'PLTR': 'Palantir Technologies (PLTR)', 'ASML': 'ASML (ASML, US line)', 'TSM': 'TSMC (TSM, US ADR)',
    'QCOM': 'Qualcomm (QCOM)', 'ARM': 'Arm Holdings (ARM)', 'MRVL': 'Marvell Technology (MRVL)', 'TXN': 'Texas Instruments (TXN)',
    'AMAT': 'Applied Materials (AMAT)', 'LRCX': 'Lam Research (LRCX)', 'KLAC': 'KLA (KLAC)', 'DELL': 'Dell Technologies (DELL)',
    'ANET': 'Arista Networks (ANET)', 'SMCI': 'Super Micro Computer (SMCI)', 'SNDK': 'Sandisk (SNDK)',
    'WDC': 'Western Digital (WDC)', 'STX': 'Seagate Technology (STX)', 'CRDO': 'Credo Technology (CRDO)',
    'ALAB': 'Astera Labs (ALAB)', 'LITE': 'Lumentum (LITE)', 'COHR': 'Coherent (COHR)', 'CRM': 'Salesforce (CRM)',
    'NOW': 'ServiceNow (NOW)', 'ADBE': 'Adobe (ADBE)', 'SNOW': 'Snowflake (SNOW)', 'DDOG': 'Datadog (DDOG)',
    'NET': 'Cloudflare (NET)', 'PANW': 'Palo Alto Networks (PANW)', 'CRWD': 'CrowdStrike (CRWD)', 'ZS': 'Zscaler (ZS)',
    'MDB': 'MongoDB (MDB)', 'IBM': 'IBM (IBM)', 'CSCO': 'Cisco Systems (CSCO)', 'APP': 'AppLovin (APP)', 'RDDT': 'Reddit (RDDT)',
    'SHOP': 'Shopify (SHOP)', 'UBER': 'Uber Technologies (UBER)', 'SPOT': 'Spotify (SPOT)', 'V': 'Visa (V)',
    'MA': 'Mastercard (MA)', 'PYPL': 'PayPal (PYPL)', 'SOFI': 'SoFi Technologies (SOFI)', 'AFRM': 'Affirm (AFRM)',
    'UPST': 'Upstart (UPST)', 'DKNG': 'DraftKings (DKNG)', 'CRWV': 'CoreWeave (CRWV)', 'NBIS': 'Nebius Group (NBIS)',
    'VRT': 'Vertiv (VRT)', 'GEV': 'GE Vernova (GEV)', 'ETN': 'Eaton (ETN)', 'PWR': 'Quanta Services (PWR)',
    'BE': 'Bloom Energy (BE)', 'OKLO': 'Oklo (OKLO)', 'SMR': 'NuScale Power (SMR)', 'NNE': 'Nano Nuclear Energy (NNE)',
    'LEU': 'Centrus Energy (LEU)', 'CCJ': 'Cameco (CCJ)', 'IONQ': 'IonQ (IONQ)', 'RGTI': 'Rigetti Computing (RGTI)',
    'QBTS': 'D-Wave Quantum (QBTS)', 'RKLB': 'Rocket Lab (RKLB)', 'ASTS': 'AST SpaceMobile (ASTS)',
    'JOBY': 'Joby Aviation (JOBY)', 'ACHR': 'Archer Aviation (ACHR)', 'MP': 'MP Materials (MP)', 'OPEN': 'Opendoor Technologies (OPEN)',
    'BYND': 'Beyond Meat (BYND)', 'HIMS': 'Hims & Hers Health (HIMS)', 'SOUN': 'SoundHound AI (SOUN)', 'CVNA': 'Carvana (CVNA)',
    'RIVN': 'Rivian (RIVN)', 'LCID': 'Lucid Group (LCID)', 'GME': 'GameStop (GME)', 'AMC': 'AMC Entertainment (AMC)',
    'JPM': 'JPMorgan Chase (JPM)', 'GS': 'Goldman Sachs (GS)', 'BAC': 'Bank of America (BAC)', 'WFC': 'Wells Fargo (WFC)',
    'C': 'Citigroup (C)', 'MS': 'Morgan Stanley (MS)', 'SCHW': 'Charles Schwab (SCHW)', 'BRK-B': 'Berkshire Hathaway Class B (BRK-B)',
    'XOM': 'Exxon Mobil (XOM)', 'CVX': 'Chevron (CVX)', 'COP': 'ConocoPhillips (COP)', 'OXY': 'Occidental Petroleum (OXY)',
    'SLB': 'SLB (SLB)', 'FCX': 'Freeport-McMoRan (FCX)', 'NEM': 'Newmont (NEM)', 'AA': 'Alcoa (AA)',
    'SCCO': 'Southern Copper (SCCO)', 'NEE': 'NextEra Energy (NEE)', 'CEG': 'Constellation Energy (CEG)', 'VST': 'Vistra (VST)',
    'DUK': 'Duke Energy (DUK)', 'SO': 'Southern Company (SO)', 'LLY': 'Eli Lilly (LLY)', 'UNH': 'UnitedHealth Group (UNH)',
    'NVO': 'Novo Nordisk (NVO, US ADR)', 'PFE': 'Pfizer (PFE)', 'MRK': 'Merck (MRK)', 'ABBV': 'AbbVie (ABBV)',
    'JNJ': 'Johnson & Johnson (JNJ)', 'MRNA': 'Moderna (MRNA)', 'CVS': 'CVS Health (CVS)', 'ISRG': 'Intuitive Surgical (ISRG)',
    'VRTX': 'Vertex Pharmaceuticals (VRTX)', 'AMGN': 'Amgen (AMGN)', 'WMT': 'Walmart (WMT)', 'COST': 'Costco (COST)',
    'HD': 'Home Depot (HD)', 'LOW': "Lowe's (LOW)", 'TGT': 'Target (TGT)', 'TJX': 'TJX Companies (TJX)', 'ROST': 'Ross Stores (ROST)',
    'NKE': 'Nike (NKE)', 'LULU': 'Lululemon (LULU)', 'SBUX': 'Starbucks (SBUX)', 'MCD': "McDonald's (MCD)", 'CMG': 'Chipotle (CMG)',
    'KO': 'Coca-Cola (KO)', 'PEP': 'PepsiCo (PEP)', 'PG': 'Procter & Gamble (PG)', 'DIS': 'Walt Disney (DIS)',
    'CMCSA': 'Comcast (CMCSA)', 'T': 'AT&T (T)', 'VZ': 'Verizon (VZ)', 'BA': 'Boeing (BA)',
    'CAT': 'Caterpillar (CAT)', 'GE': 'GE Aerospace (GE)', 'DE': 'Deere (DE)', 'LMT': 'Lockheed Martin (LMT)', 'RTX': 'RTX (RTX)',
    'XLK': 'XLK (technology sector ETF)', 'XLC': 'XLC (communication services sector ETF)', 'XLF': 'XLF (financials sector ETF)',
    'XLE': 'XLE (energy sector ETF)', 'XLI': 'XLI (industrials sector ETF)', 'XLY': 'XLY (consumer discretionary sector ETF)',
    'XLP': 'XLP (consumer staples sector ETF)', 'XLV': 'XLV (health care sector ETF)', 'XLB': 'XLB (materials sector ETF)',
    'XLRE': 'XLRE (real estate sector ETF)', 'XLU': 'XLU (utilities sector ETF)',
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
    if c2 == c10:
        return 'parallel rally (both down equally; spread unchanged)' if c2 < 0 else 'parallel selloff (both up equally; spread unchanged)'
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
        if len(rows) < 6: continue
        (ld, lc), (d1, c1), (d5, c5) = rows[-1], rows[-2], rows[-6]
        d20, c20 = rows[-21] if len(rows) >= 21 else (None, None)
        levels = dict(j.get('as_traded_rows', j['rows']))
        level_ok = not j.get('level_restriction')
        # A split within the lookback changes nominal reference units.
        units_changed = abs((levels[ld] / lc) / (levels[d20] / c20) - 1) > 1e-6 if c20 is not None else None
        mk[t] = {'name': NAMES.get(t, t), 'session': ld, 'close': fmt(levels[ld], t) if level_ok else None, 'currency': j.get('currency', ''),
                 'chg_1s_pct': pct(lc, c1), 'chg_5s_pct': pct(lc, c5), 'chg_20s_pct': pct(lc, c20) if c20 is not None else None,
                 'ref_20s_session': d20, 'ref_20s_close': fmt(levels[d20], t) if level_ok and d20 is not None else None, 'tz': j['tz'],
                 'level_restriction': j.get('level_restriction'),
                 'price_level_basis': j.get('price_level_basis'), 'price_change_basis': j.get('price_change_basis'),
                 'reference_share_units_differ': units_changed,
                 'reference_level_note': 'Older share units differ; use comparable percentage returns, not the raw reference price as a current trigger' if units_changed else None}
        if c20 is None:
            mk[t]['history_limitation'] = f'Only {len(rows)} prior observations available; 20-session change and reference are unavailable, not estimated'
        if t == '^VIX':
            mk[t]['chg_1s_pts'], mk[t]['chg_20s_pts'] = round(lc - c1, 2), round(lc - c20, 2) if c20 is not None else None
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
