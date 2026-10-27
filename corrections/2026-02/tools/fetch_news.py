"""fetch_news.py <dates> — harvest date-bounded Google News headlines (with article links) for the February 2026
retrospective briefings. Writes ../feeds/<date>.json and skips dates already cached.

Time rule: an item is kept only if its RSS pubDate is strictly before <date> 00:00 UTC (the report's information
cutoff). Windows mirror lambda_function.py: news 7 days ('news'), monthly releases 35 days ('monthly'), earnings
reactions 14 days ('result'). Google News ANDs every term, so each query is one short topic.
"""
import urllib.request, urllib.parse, xml.etree.ElementTree as ET, json, os, sys, time, random, datetime as dt, email.utils
import concurrent.futures as cf

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'feeds')
H = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
WIN = {'news': 7, 'monthly': 35, 'result': 14}
EN, PL = ('en-US', 'US', 'US:en'), ('pl', 'PL', 'PL:pl')

N, M, R = 'news', 'monthly', 'result'
TOPICS = {
    'us_macro':   [('Federal Reserve', N), ('Fed rate cut', N), ('Powell', N), ('Fed chair nominee', N), ('FOMC minutes', N),
                   ('Fed officials inflation', N), ('Treasury yields', N), ('US economy', N), ('US stocks', N),
                   ('Wall Street stocks', N), ('S&P 500', N), ('Nasdaq', N), ('dollar index', N), ('tariffs', N),
                   ('government shutdown', N), ('Supreme Court tariffs', N)],
    'us_data':    [('ISM manufacturing', M), ('ISM services', M), ('jobs report', M), ('nonfarm payrolls', M),
                   ('jobless claims', N), ('JOLTS job openings', M), ('CPI inflation', M), ('PCE inflation', M),
                   ('retail sales', M), ('consumer sentiment', M), ('consumer confidence', M), ('US GDP', M),
                   ('housing starts', M), ('existing home sales', M), ('new home sales', M), ('mortgage rates', N),
                   ('producer prices', M), ('ADP employment', M)],
    'europe':     [('ECB', N), ('Lagarde', N), ('eurozone economy', N), ('eurozone inflation', M), ('eurozone PMI', M),
                   ('flash PMI', M), ('Germany economy', N), ('German manufacturing', M), ('European stocks', N),
                   ('STOXX 600', N), ('Bank of England', N), ('UK economy', N), ('euro dollar', N)],
    'china':      [('PBOC', N), ('loan prime rate', N), ('yuan', N), ('China economy', N), ('China PMI', M),
                   ('Caixin PMI', M), ('China new loans', M), ('China credit data', M), ('China CPI', M), ('China PPI', M),
                   ('China exports', M), ('China retail sales', M), ('China industrial profits', M),
                   ('China new home prices', M), ('China property', N), ('Vanke', N), ('China stimulus', N),
                   ('China tariffs', N), ('China rare earths', N), ('CSI 300', N), ('Hang Seng', N), ('China stocks', N),
                   ('Lunar New Year spending', N), ('China bond yields', N)],
    'japan':      [('Bank of Japan', N), ('BOJ rate hike', N), ('yen', N), ('Japan economy', N), ('Japan inflation', M),
                   ('Japan GDP', M), ('Nikkei', N), ('JGB yields', N), ('Takaichi', N), ('Japan election', N)],
    'australia':  [('Reserve Bank of Australia', N), ('RBA rate', N), ('Australia inflation', M), ('Australia jobs', M),
                   ('Australia economy', N), ('ASX 200', N), ('Australian dollar', N)],
    'poland_en':  [('Poland economy', N), ('Poland central bank', N), ('zloty', N), ('Polish stocks', N),
                   ('Poland inflation', M), ('Orlen', N), ('PKO BP', N), ('KGHM', N), ('Poland defence', N)],
    'poland_pl':  [('NBP stopy procentowe', N, PL), ('RPP decyzja', N, PL), ('inflacja GUS', M, PL), ('PKB GUS', M, PL),
                   ('sprzedaż detaliczna', M, PL), ('produkcja przemysłowa', M, PL), ('wynagrodzenia GUS', M, PL),
                   ('PMI Polska', M, PL), ('WIG20', N, PL), ('kurs złotego', N, PL), ('obligacje skarbowe', N, PL),
                   ('deficyt budżetu', N, PL), ('Orlen', N, PL), ('PKO BP', N, PL), ('KGHM', N, PL), ('PGE', N, PL),
                   ('Allegro', N, PL), ('Dino Polska', N, PL), ('CD Projekt', N, PL), ('LPP', N, PL), ('WIBOR', N, PL)],
    'sectors':    [('semiconductor stocks', N), ('Nvidia', N), ('TSMC', N), ('ASML', N), ('AI capex', N),
                   ('hyperscaler spending', N), ('software stocks AI', N), ('memory chips prices', N),
                   ('oil prices', N), ('OPEC', N), ('natural gas prices', N), ('bank stocks', N), ('private credit', N),
                   ('European automakers', N), ('Volkswagen', N), ('Stellantis', N), ('BMW Mercedes', N),
                   ('utilities AI power demand', N), ('data center power', N), ('REIT', N), ('homebuilders', N),
                   ('retailers', N), ('consumer staples stocks', N), ('pharma stocks', N), ('drug pricing', N),
                   ('biotech stocks', N), ('defense stocks', N), ('industrial stocks', N), ('airlines', N),
                   ('copper prices', N), ('gold prices', N), ('silver prices', N), ('mining stocks', N),
                   ('media streaming', N), ('advertising market', N), ('chemicals', N)],
    'earnings':   [('earnings beat estimates', R), ('earnings miss estimates', R), ('raises guidance', R),
                   ('cuts guidance', R), ('quarterly results shares', R), ('stock falls despite beat', R),
                   ('shares jump after earnings', R), ('shares fall after earnings', R), ('fourth-quarter results', R),
                   ('profit warning', R), ('earnings preview', N), ('earnings this week', N), ('earnings to watch', N),
                   ('analysts raise estimates', N), ('tech earnings', R), ('bank earnings', R), ('oil company earnings', R),
                   ('retailer earnings', R), ('pharma earnings', R), ('chipmaker earnings', R), ('automaker earnings', R),
                   ('industrial earnings', R), ('utility earnings', R), ('REIT earnings', R), ('media earnings', R),
                   ('food company earnings', R)],
    'crypto':     [('bitcoin', N), ('ethereum', N), ('bitcoin ETF', N), ('stablecoin', N), ('crypto regulation', N),
                   ('crypto market', N), ('Strategy MSTR bitcoin', N), ('Coinbase', N)],
    'flows':      [('fund flows', N), ('emerging markets', N), ('credit spreads', N), ('high yield bonds', N),
                   ('corporate bond issuance', N), ('Fed balance sheet', N), ('repo market', N), ('liquidity', N),
                   ('hedge funds', N), ('dollar', N)],
    'retail':     [('Reddit stocks', N), ('retail investors', N), ('meme stocks', N), ('wallstreetbets', N),
                   ('retail traders', N), ('most active stocks', N), ('stocks to watch', N), ('short squeeze', N),
                   ('options trading retail', N)],
    'geo':        [('Iran', N), ('Ukraine Russia talks', N), ('Middle East', N), ('Venezuela oil', N), ('Greenland', N),
                   ('trade deal', N), ('sanctions', N)],
    'calendar':   [('week ahead markets', N), ('economic calendar', N), ('what to watch markets', N)],
}

def rss(q, loc=EN):
    hl, gl, ceid = loc
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl={hl}&gl={gl}&ceid={ceid}"
    for attempt in range(5):
        try:
            root = ET.fromstring(urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=25).read())
            out = []
            for it in root.findall('.//item'):
                pd = email.utils.parsedate_to_datetime(it.findtext('pubDate')).astimezone(dt.timezone.utc)
                src = it.find('source')
                out.append({'published_at': pd.isoformat(), 'src': (src.text if src is not None else '') or '',
                            'title': it.findtext('title') or '', 'url': it.findtext('link') or ''})
            return out
        except Exception:
            time.sleep(2 * (attempt + 1) + random.random())
    return None

def one(d):
    fn = os.path.join(OUT, f'{d}.json')
    if os.path.exists(fn):
        return d, 'cached'
    D = dt.date.fromisoformat(d)
    cutoff = dt.datetime(D.year, D.month, D.day, tzinfo=dt.timezone.utc)
    jobs = [(topic, q[0], q[1], q[2] if len(q) > 2 else EN) for topic, qs in TOPICS.items() for q in qs]
    items, seen, fails = [], {}, []
    for topic, q, cat, loc in jobs:
        win = WIN[cat]
        after = (D - dt.timedelta(days=win + 1)).isoformat()
        got = rss(f'{q} after:{after} before:{d}', loc)
        if got is None:
            fails.append(f'{topic}:{q}'); continue
        lo = cutoff - dt.timedelta(days=win)
        for x in got:
            p = dt.datetime.fromisoformat(x['published_at'])
            if not (lo <= p < cutoff) or not x['title']:
                continue
            key = x['title'].strip().lower()
            if key in seen:
                it = items[seen[key]]
                if topic not in it['topics']: it['topics'].append(topic)
                if WIN[cat] < WIN[it['cat']]: it['cat'] = cat          # keep the strictest window that matched
                continue
            seen[key] = len(items)
            items.append({**x, 'cat': cat, 'topics': [topic], 'q': q, 'lang': loc[0]})
        time.sleep(0.25 + random.random() * 0.2)
    items.sort(key=lambda x: (x['topics'][0], x['published_at']), reverse=False)
    for i, x in enumerate(items, 1):
        x['id'] = f'n{i:04d}'
    json.dump({'date': d, 'cutoff_utc': cutoff.isoformat(),
               'rule': 'RSS pubDate strictly before the cutoff; news 7d, monthly releases 35d, earnings reactions 14d',
               'fails': fails, 'items': items}, open(fn, 'w'), ensure_ascii=False, indent=1)
    return d, f'{len(items)} items, {len(fails)} failed queries'

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    with cf.ThreadPoolExecutor(int(os.environ.get('THREADS', '4'))) as ex:
        for d, msg in ex.map(one, sys.argv[1:]):
            print(d, msg, flush=True)
