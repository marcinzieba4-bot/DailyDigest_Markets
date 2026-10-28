"""dossier.py <dates> — one compact input file per date for the writers: ../work/dossier_<date>.md (git-ignored).

It replaces reading the full digest (about 1,800 lines, ~65k tokens) and many greps: the market card as a table, then about
900 headlines chosen per topic by outlet tier and recency (digest.py's ranking), de-duplicated, with the outlet suffix stripped
from the title, plus two packs that matter for the page — retail attention (Stocktwits / Reddit / Robinhood / retail-flow /
meme / options items from every topic) and earnings reactions (results, guidance, share moves, 14-day window).
Line format: id|MM-DD HH:MM UTC|outlet|headline — the id is what a spec cites as [[nXXXX]]. Anything not shown can still be
found with  python3 -I tools/digest.py <date> --grep "regex" --max 30."""
import io, os, re, sys, contextlib, importlib.util

T = os.path.dirname(os.path.abspath(__file__)); C = os.path.dirname(T)


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(T, name + '.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


dg = load('digest'); sc = load('showcard')
CAPS = {'us_macro': 50, 'us_data': 50, 'europe': 40, 'china': 75, 'japan': 30, 'australia': 30, 'poland_en': 30,
        'poland_pl': 75, 'sectors': 100, 'earnings': 100, 'crypto': 40, 'flows': 40, 'retail': 60, 'geo': 35, 'calendar': 15}
TITLES = {'us_macro': 'US MACRO, FED, TARIFFS, SHUTDOWN', 'us_data': 'US DATA RELEASES', 'europe': 'EUROPE', 'china': 'CHINA',
          'japan': 'JAPAN', 'australia': 'AUSTRALIA', 'poland_en': 'POLAND (English-language)', 'poland_pl': 'POLAND (Polish-language)',
          'sectors': 'SECTORS AND COMPANIES', 'earnings': 'EARNINGS (results window 14 days)', 'crypto': 'CRYPTO',
          'flows': 'FLOWS, LIQUIDITY, CREDIT', 'retail': 'RETAIL ATTENTION (topic)', 'geo': 'GEOPOLITICS', 'calendar': 'CALENDAR / WEEK AHEAD'}
RETAIL = re.compile(r"stocktwits|reddit|wallstreetbets|\bwsb\b|retail (investor|trader|sentiment|inflow|flow|buy|money|crowd|favorite)|"
                    r"meme|robinhood|short squeeze|most active|trending|options (trader|volume|activity|bet)|call options|"
                    r"buy the dip|dip.buy|fintwit|finfluenc|roaring kitty|portnoy|cathie wood|leveraged etf|zero-day", re.I)
REACT = re.compile(r"(shares|stock|stocks)\b.{0,60}(jump|surge|soar|rall|rise|climb|gain|fall|slump|plunge|tumble|sink|drop|slide|"
                   r"sink|tank|pop)|\b(beat|beats|miss|misses|topped|tops|raises|raised|cuts|cut|lifts|lowers|guidance|outlook|forecast)\b|"
                   r"(results|earnings|profit|revenue|sales)\b", re.I)


def clean(x):
    t = x['title'].strip()
    s = (x['src'] or '').strip()
    if s and t.lower().endswith(' - ' + s.lower()):
        t = t[: -(len(s) + 3)].rstrip()
    return t


def line(x):
    p = x['published_at']
    return f"{x['id']}|{p[5:10]} {p[11:16]}|{x['src'][:24]}|{clean(x)}"


def key(x):
    return re.sub(r'[^a-z0-9]', '', clean(x).lower())[:80]


def build(d):
    items = dg.load_feed(d)['items']
    seen, shown, out = set(), set(), []

    def take(sel, cap):
        rows = []
        for x in sel:
            k = key(x)
            if x['id'] in shown or k in seen: continue
            seen.add(k); shown.add(x['id']); rows.append(line(x))
            if len(rows) >= cap: break
        return rows

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        sys.argv = ['showcard', d]; sc.main()
    out.append(f'# DOSSIER {d} — inputs for the {d} briefing (information cutoff {d} 00:00 UTC)\n')
    out.append('Everything below is the only material you may use. Headline lines: id|MM-DD HH:MM UTC|outlet|headline — cite the id as [[nXXXX]].\n'
               'This is a selection (~900 of ~8,000 items). To look for something specific: python3 -I tools/digest.py ' + d + ' --grep "regex" --max 30\n')
    out.append('## 1. MARKET CARD\n' + buf.getvalue())
    n = 2
    for t in CAPS:
        sel = sorted([x for x in items if x['topics'][0] == t], key=dg.rank)
        rows = take(sel, CAPS[t])
        out.append(f'## {n}. {TITLES[t]} ({len(rows)} of {len(sel)})\n' + '\n'.join(rows) + '\n'); n += 1
    # retail pack: direct attention evidence from every topic (Stocktwits / Reddit / broker / retail-flow items first)
    pool = [x for x in items if ('retail' in x['topics'] or RETAIL.search(x['title']) or 'stocktwits' in x['src'].lower())]
    pool.sort(key=lambda x: (0 if re.search('stocktwits|reddit', x['src'], re.I) else 1, dg.rank(x)))
    rows = take(pool, 110)
    out.append(f'## {n}. RETAIL ATTENTION PACK — Stocktwits, Reddit, Robinhood, retail flows, meme / options items from all topics ({len(rows)} more)\n'
               + '\n'.join(rows) + '\n'); n += 1
    pool = sorted([x for x in items if x['cat'] == 'result' and REACT.search(x['title'])], key=dg.rank)
    rows = take(pool, 70)
    out.append(f'## {n}. EARNINGS REACTIONS PACK — results, guidance and share moves in the 14-day window ({len(rows)} more)\n' + '\n'.join(rows) + '\n')
    text = '\n'.join(out)
    os.makedirs(os.path.join(C, 'work'), exist_ok=True)
    fn = os.path.join(C, 'work', f'dossier_{d}.md')
    open(fn, 'w', encoding='utf-8').write(text)
    return fn, len(text), text.count('\n')


if __name__ == '__main__':
    for d in sys.argv[1:]:
        fn, n, ln = build(d)
        print(f'{d}: {fn} — {n:,} chars, {ln} lines (~{n // 3.6:,.0f} tokens)')
