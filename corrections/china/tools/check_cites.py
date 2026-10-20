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
                  r"home sales|ism|sales|reserves|economy|growth|data|consumption|factory|manufactur|services|industrial|fiscal|revenue")
def same(src, xs):
    a, b = norm(src), norm(xs)
    return bool(b) and any(x == b or x in b or b in x for x in {a, ALIAS.get(a, a)})
bad = old = 0
for d in sys.argv[1:]:
    D = dt.date.fromisoformat(d); items = feed_items(d)
    text = html.unescape(re.sub(r'<[^>]+>', ' ', open(os.path.join(C, 'new', f'{d}.html'), encoding='utf-8').read()))
    for m in re.finditer(r'\(([^()\[\]]{2,60}?),\s*\[(\w{3}) (\d{1,2})\]\)', text):
        src, iso = m.group(1).strip(), dt.date(D.year, MON[m.group(2).lower()], int(m.group(3))).isoformat()
        hits = [x for x in items if x['t'] == iso and same(src, x['src'])]
        if not hits:
            bad += 1; print(f'{d} NO MATCH  {src} [{iso}]')
        elif (D - dt.date.fromisoformat(iso)).days > 7 and not any(DATA.search(x['title']) for x in hits):
            old += 1; print(f'{d} >7d NON-DATA? {iso} {src}: ' + ' || '.join(x['title'][:80] for x in hits[:3]))
print(f'-- unmatched citations: {bad}; >7-day citations not obviously data releases: {old}')
