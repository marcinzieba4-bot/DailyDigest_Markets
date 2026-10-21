"""card_pl.py <date> — Poland market card, same logic as corrections/poland/tools/plcards.py (closes strictly before the date)."""
import csv, json, sys
W = '/tmp/claude-0/-home-user-DailyDigest-Markets/350e9aa9-be2b-5699-b30e-16c2be0713f3/scratchpad/d0624/work/data'
def load(sym): return {r['Date']: float(r['Close']) for r in csv.DictReader(open(f'{W}/yf_{sym}.csv'))}
S = {'usdpln': load('PLN_X'), 'eurpln': load('EURPLN_X'), 'epol_usd': load('EPOL'), 'pko': load('PKO_WA'), 'pekao': load('PEO_WA'), 'orlen': load('PKN_WA'),
     'kghm': load('KGH_WA'), 'pge': load('PGE_WA'), 'allegro': load('ALE_WA'), 'dino': load('DNP_WA'), 'cdprojekt': load('CDR_WA'), 'lpp': load('LPP_WA')}
d = sys.argv[1]
out = {'report_date': d, 'note': 'All values are closes strictly before the report date (prior session). Percent changes are vs ~1 week (5 sessions) and ~4 weeks (20 sessions) earlier.'}
for name, ser in S.items():
    ks = [k for k in sorted(ser) if k < d]; k = ks[-1]; i = ks.index(k); v = ser[k]
    w1 = ser[ks[max(0, i - 5)]]; w4 = ser[ks[max(0, i - 20)]]
    dec = 4 if 'pln' in name else 2
    out[name] = {'date': k, 'close': round(v, dec), 'chg_1w_pct': round((v - w1) / w1 * 100, 1), 'chg_4w_pct': round((v - w4) / w4 * 100, 1)}
print(json.dumps(out, indent=1))
