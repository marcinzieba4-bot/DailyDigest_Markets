"""check_cites.py <dates> — every "(Source, [Mon DD])" citation in new/<date>.html must match a headline in that date's own
feed with the same date and source; tags older than 7 days are listed with the matched headline so they can be checked
as monthly data releases."""
import sys, os, re, json, html, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import C, feed_items
MON = {m: i for i, m in enumerate(['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'], 1)}
norm = lambda s: re.sub(r'[^a-z0-9]', '', re.sub(r'(?i)^www\.|\.com$|\.co\.uk$|\.org$', '', s.strip().lower()))
ALIAS = {'scmp': 'southchinamorningpost', 'ap': 'apnews', 'ft': 'financialtimes', 'nyt': 'thenewyorktimes', 'wsj': 'wsj',
         'guardian': 'theguardian', 'economist': 'theeconomist', 'nikkei': 'nikkeiasia', 'chinadaily': 'chinadaily', 'ifr': 'internationalfinancingreview', 'biggofinance': 'financebiggo', 'biggo': 'financebiggo'}
DATA = re.compile(r"(?i)pmi|cpi|ppi|inflation|deflation|retail sales|output|profit|loans|lending|credit|financing|tsf|\bm1\b|\bm2\b|gdp|"
                  r"home prices|house prices|price|property investment|real estate|investment|exports|imports|trade|surplus|housing starts|"
                  r"home sales|ism|sales|reserves|economy|growth|data|consumption|factory|manufactur|services|industrial|fiscal|revenue|"
                  r"earnings|beat|miss|guidance|outlook|forecast|quarter|results|shares|stock")
def same(src, xs):
    a, b = norm(src), norm(xs)
    return bool(b) and any(x == b or x in b or b in x for x in {a, ALIAS.get(a, a)})
STOP = set(('the a an and or of to in on for as by with at from its it is was are be after but their his her this that than '
             'into over up down more most new estimates earnings beat beats shares stock says said china chinese us').split())
def words(t):
    out = set()
    for w in re.findall(r"[a-z0-9$%.']+", t.lower().replace(',', '')):
        w = w.strip(".'")
        if w in STOP or (len(w) < 3 and not re.search(r'\d', w)): continue
        out.add(w[:5] if not re.search(r'\d', w) else re.sub(r'[^0-9.]', '', w))
    return out
CONTENT = '--content' in sys.argv          # also flag citations whose claim shares few words with the cited headline
sys.argv = [a for a in sys.argv if a != '--content']
weak = 0
bad = old = 0
for d in sys.argv[1:]:
    D = dt.date.fromisoformat(d); items = feed_items(d)
    srcs = [os.path.join(C, 'new', f'{d}.html'), os.path.join(C, 'sectors', f'{d}.html'), os.path.join(C, 'pattern', f'{d}.html')]
    text = ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', open(f, encoding='utf-8').read())) for f in srcs if os.path.exists(f))
    for m in re.finditer(r'\(([^()\[\]]{2,60}?),\s*\[(\w{3}) (\d{1,2})\]\)', text):
        src, iso = m.group(1).strip(), dt.date(D.year, MON[m.group(2).lower()], int(m.group(3))).isoformat()
        hits = [x for x in items if x['t'] == iso and same(src, x['src'])]
        if hits and CONTENT:
            clause = re.split(r'(?<=[.;:])\s|\)\s|—', text[max(0, m.start() - 220):m.start()])[-1]
            cw = words(clause); sc = max(len(cw & words(x['title'])) / max(1, len(cw)) for x in hits)
            if sc < 0.2:
                weak += 1; print(f'{d} WEAK {sc:.2f} {src} [{iso}] | {clause[-110:].strip()!r}')
        if not hits:
            bad += 1; print(f'{d} NO MATCH  {src} [{iso}]')
        elif (D - dt.date.fromisoformat(iso)).days > 7 and not any(DATA.search(x['title']) for x in hits):
            old += 1; print(f'{d} >7d NON-DATA? {iso} {src}: ' + ' || '.join(x['title'][:80] for x in hits[:3]))
print(f'-- unmatched citations: {bad}; >7-day citations not obviously data releases: {old}' + (f'; weak content matches: {weak}' if CONTENT else ''))
