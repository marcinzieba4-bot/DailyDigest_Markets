"""Post-hoc scorecard (NOT part of the reports): forward performance of the sector stances in the February specs.
Entry = last close before the report date (the card's close); exit = 5 / 20 sessions later. Excess vs S&P 500
(SXAP proxy EXV5.DE vs STOXX 600)."""
import json, os, glob, sys, collections
F = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prices_2026-01-20_2026-05-01.json')))
SP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'specs')
TK = {'XLK': 'XLK', 'XLC': 'XLC', 'XLF': 'XLF', 'XLE': 'XLE', 'XLI': 'XLI', 'XLY': 'XLY', 'XLP': 'XLP', 'XLV': 'XLV',
      'XLB': 'XLB', 'XLRE': 'XLRE', 'XLU': 'XLU', 'SOXX': 'SOXX', 'SXAP': 'EXV5.DE'}
BENCH = {'EXV5.DE': '^STOXX'}

def fwd(t, d, n):
    rows = F[t]; i = max(k for k, (day, _) in enumerate(rows) if day < d)
    if i + n >= len(rows): return None
    return rows[i + n][1] / rows[i][1] - 1

res = collections.defaultdict(list); table = []
for p in sorted(glob.glob(os.path.join(SP, '2026-02-*.json'))):
    s = json.load(open(p)); d = s['date']
    for x in s['sectors']:
        t = TK[x['key']]; b = BENCH.get(t, '^GSPC')
        for n in (5, 20):
            r, rb = fwd(t, d, n), fwd(b, d, n)
            if r is None or rb is None: continue
            ex = r - rb
            res[(x['stance'], n)].append(ex)
            if n == 20: table.append((d, x['key'], x['stance'], round(ex * 100, 2)))
for (st, n), v in sorted(res.items()):
    hits = sum((e > 0) if st == 'Bullish' else (e < 0) for e in v) if st != 'Mixed' else None
    print(f'{st:8s} {n:2d}s n={len(v):3d} mean excess {sum(v)/len(v)*100:+.2f}%' + (f'  hit {hits}/{len(v)}' if hits is not None else ''))
if '-v' in sys.argv:
    for row in table:
        if row[2] != 'Mixed': print(row)
