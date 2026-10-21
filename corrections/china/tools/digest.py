"""Print a relevance-filtered, de-duplicated union of the harvested feeds for a set of dates (reading aid only)."""
import json, re, sys, os
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'feeds')
CN = re.compile(r"(?i)china|chinese|beijing|yuan|renminbi|\brmb\b|\bcny\b|pboc|people's bank|caixin|\bnbs\b|vanke|evergrande|country garden|hang seng|csi 300|shanghai|shenzhen|hong kong|politburo|state council|ndrc|xi jinping|li qiang|lgfv|guangzhou")
DATA = {
 'growth_pmi': re.compile(r"(?i)\bpmi\b|\bism\b|purchasing managers|factory activity|services activity|business activity|manufacturing (activity|sector)"),
 'growth_credit': re.compile(r"(?i)credit impulse|bank lending|loan growth|lending survey|loan officer|credit spreads?|loan demand|credit growth|money supply|\bm2\b"),
 'growth_housing': re.compile(r"(?i)housing starts|home sales|house prices|home prices|mortgage|case-shiller|building permits|homebuilder|housing market|property prices|dwelling"),
}
JUNK = re.compile(r"(?i)statista|historical chart|guru ?focus|tradingeconomics|investing\.com.*(chart|forecast)|\bpdf\b|wikipedia|youtube")
earn = '--earn' in sys.argv
dates = [a for a in sys.argv[1:] if not a.startswith('--')]; keys = None; seen = {}
if earn: D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'feeds_earn')
for d in dates:
    f = json.load(open(os.path.join(D, f'{d}.json')))
    for k, items in f['feeds'].items():
        for x in items:
            t = x['title']
            if JUNK.search(t + ' ' + x['src']): continue
            if k.startswith('china') and not CN.search(t): continue
            if k in DATA and not DATA[k].search(t): continue
            key = (k, t)
            if key not in seen: seen[key] = x
by = {}
for (k, t), x in seen.items(): by.setdefault(k, []).append(x)
for k in by:
    print(f'\n## {k} ({len(by[k])})')
    for x in sorted(by[k], key=lambda x: x['t']):
        print(f"{x['t'][5:]} | {x['title'][:150]}")
