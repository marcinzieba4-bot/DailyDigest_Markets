"""Harvest date-bounded Google News headlines for the China block and the growth-pulse rewrite of archived reports.

Usage: python3 -I fetch_feeds.py 2026-06-25 2026-06-26 ...   (writes ../feeds/<date>.json, skips cached dates)

Windows mirror lambda_function.py: news topics 7 days, monthly-data topics (PMIs, credit, home prices, activity) 35 days.
Google dates items by (roughly) US Eastern date, so a Beijing release at 01:30 UTC carries the PRIOR day and a headline
dated on the report date may have been published after the 17:00 UTC report. Only items dated strictly BEFORE the report
date are kept.
"""
import urllib.request, urllib.parse, xml.etree.ElementTree as ET, json, os, sys, time, random, datetime as dt, email.utils
import concurrent.futures as cf

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'feeds')
H = {'User-Agent': 'Mozilla/5.0'}
W, M = 7, 35
TOPICS = {
    'china_pboc':     [('PBOC', W), ('loan prime rate', W), ('yuan fixing', W), ('China central bank', W)],
    'china_pmi':      [('China PMI', M), ('Caixin PMI', M), ('China manufacturing PMI', M), ('China non-manufacturing PMI', M)],
    'china_credit':   [('China credit data', M), ('China aggregate financing', M), ('China new loans', M),
                       ('China M1 M2', M), ('China credit impulse', M)],
    'china_activity': [('China retail sales', M), ('China industrial output', M), ('China industrial profits', M),
                       ('China CPI', M), ('China PPI', M), ('China GDP', M), ('China fixed-asset investment', M)],
    'china_property': [('China new home prices', M), ('China home prices', W), ('China property investment', M),
                       ('China property sales', W), ('China developer debt', W), ('Vanke', W),
                       ('China local government debt', M), ('China property', W)],
    'china_policy':   [('China stimulus', W), ('China special bonds', W), ('Politburo economy', W),
                       ('State Council China economy', W), ('China fiscal', W)],
    'china_trade':    [('China exports', M), ('China tariffs', W), ('China rare earths', W), ('China trade', W)],
    'china_markets':  [('CSI 300', W), ('Hang Seng', W), ('China bond yields', W), ('yuan dollar', W), ('China stocks', W)],
    'growth_pmi':     [('flash PMI', M), ('ISM manufacturing', M), ('ISM services', M), ('eurozone PMI', M),
                       ('Japan PMI', M), ('Australia PMI', M), ('UK PMI', M), ('global PMI', M), ('Brazil PMI', M)],
    'growth_credit':  [('credit impulse', M), ('bank lending eurozone', M), ('US bank lending', M),
                       ('senior loan officer survey', M), ('credit spreads', W)],
    'growth_housing': [('housing starts', M), ('existing home sales', M), ('new home sales', M), ('pending home sales', M),
                       ('mortgage rates', W), ('Case-Shiller', M), ('house prices Europe', M), ('Australia home prices', M),
                       ('Japan housing', M)],
}

def rss(q):
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=en-US&gl=US&ceid=US:en"
    for attempt in range(4):
        try:
            root = ET.fromstring(urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=25).read())
            out = []
            for it in root.findall('.//item'):
                pd = email.utils.parsedate_to_datetime(it.findtext('pubDate')).astimezone(dt.timezone.utc)
                src = it.find('source')
                out.append({'t': pd.strftime('%Y-%m-%d'), 'src': src.text if src is not None else '',
                            'title': it.findtext('title')})
            return out
        except Exception:
            time.sleep(2 * (attempt + 1) + random.random())
    return None

def one(d):
    fn = os.path.join(OUT, f'{d}.json')
    if os.path.exists(fn):
        return d, 'cached'
    D = dt.date.fromisoformat(d)
    res, fails = {}, []
    for key, qs in TOPICS.items():
        seen, items = set(), []
        for q, win in qs:
            after = (D - dt.timedelta(days=win + 1)).isoformat()
            got = rss(f'{q} after:{after} before:{d}')
            if got is None:
                fails.append(f'{key}:{q}'); continue
            lo = (D - dt.timedelta(days=win)).isoformat()
            for x in got:
                if lo <= x['t'] < d and x['title'] not in seen:
                    seen.add(x['title']); items.append({**x, 'q': q})
            time.sleep(0.3)
        items.sort(key=lambda x: x['t'], reverse=True)
        res[key] = items
    json.dump({'date': d, 'rule': 'items dated strictly before the report date; news 7d, monthly data 35d',
               'fails': fails, 'feeds': res}, open(fn, 'w'), ensure_ascii=False, indent=1)
    return d, f'{sum(len(v) for v in res.values())} items, fails={fails}'

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    with cf.ThreadPoolExecutor(3) as ex:
        for d, msg in ex.map(one, sys.argv[1:]):
            print(d, msg, flush=True)
