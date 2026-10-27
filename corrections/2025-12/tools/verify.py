"""verify.py <dates> — check ../specs/<date>.json before rendering. Prints FAIL / WARN lines and a PASS summary.

FAIL: wrong structure or labels; a citation id that is not in that date's feed; a number that is neither in the
date's market card, nor in a headline cited in the same paragraph, nor a whitelisted structural number; a
month-day date on or after the report date that no cited headline in the paragraph carries; a data-source tag
"(Yahoo Finance, prior close X)" / "(US Treasury, prior close X)" whose X is not a session date in the card;
hindsight / correction wording; copper or gold-copper used as a growth gauge.
WARN: a number found only in a headline cited elsewhere in the report; calendar language that needs a future-dated
headline; a citation reused many times; length outside the usual range."""
import json, os, re, sys, datetime as dt

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CITE = re.compile(r'\[\[(n\d{4})\]\]')
NUM = re.compile(r'(?<![A-Za-z])\d[\d,]*(?:\.\d+)?')
GEO = ['US', 'EU', 'CN', 'JP', 'AU', 'PL']
SECT = ['XLK', 'XLC', 'XLF', 'XLE', 'XLI', 'XLY', 'XLP', 'XLV', 'XLB', 'XLRE', 'XLU', 'SXAP', 'SOXX']
CN_PARTS = ['Macro Stance', 'PMIs & Activity', 'Credit Impulse', 'Property', 'Fiscal, Policy & Trade', 'Markets & Flows',
            'New / Most Important', 'Playbook ✓']
LABELS = {
    'sector': ['Narrative', 'Reported', 'EPS Upside Watch', '⚡ Breaking Convention'],
    'earnings_pattern': ['Rewarded', 'Punished', 'Pattern', 'Attention into EPS', 'Playbook'],
    'underowned': ['Attention Gap', 'Exposure & Risk', 'Trigger to Watch'],
    'crypto': ['Market Context', 'New / Most Important', 'Playbook'],
    'flows': ['Global Liquidity', 'Rates & Dollar', 'Credit Check', 'Equity & Fund Flows', 'Portfolio Implication'],
    'anticipatory': ['What Is Priced', 'Conditional Expression', 'Risk'],
    'catalysts': ['Catalyst & Thesis', 'Price Hurdle & Risk', 'Trade Expression'],
    'retail_lead': ['Why Retail Is Here', 'What Is Driving It', 'The Social Signal', 'Historical Analog', 'Smart Money View',
                    'When the Narrative Breaks'],
    'retail_small': ['Why Retail Is Here', 'Where It Breaks'],
}
COUNTS = {'underowned': 4, 'anticipatory': 4, 'catalysts': 6, 'retail': 4}
STRUCTURAL = {500, 100, 2000, 600, 50, 40, 225, 200, 300, 20, 30, 14, 35, 24, 2025, 2026, 2027, 1000}
MONTHS = {m: i for i, m in enumerate(['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'], 1)}
MD = re.compile(r'\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|'
                r'Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.? (\d{1,2})\b')
BANNED = re.compile(r'\b(retrospective(ly)?|hindsight|in retrospect|corrected|correction to this|turned out|would later|'
                    r'subsequently|as it happened)\b', re.I)
COPPER = re.compile(r'(gold\s*/\s*copper|copper\s*/\s*gold|oil\s*/\s*copper|copper\s*/\s*oil|dr\.? copper|'
                    r'copper (?:as|is) a (?:gauge|barometer|signal) of (?:global|china|growth))', re.I)
CAL = re.compile(r'\b(upcoming|next week|later this week|this week|due on|scheduled for|set to report|will report|'
                 r'reports? (?:on|after) (?:Monday|Tuesday|Wednesday|Thursday|Friday))\b', re.I)
DATATAG = re.compile(r'\((Yahoo Finance|US Treasury), prior close (\d{4}-\d{2}-\d{2})(?:; (Yahoo Finance|US Treasury), prior close (\d{4}-\d{2}-\d{2}))?\)')


def load_feed(d):
    """../feeds/<date>.json, or the committed gzip copy ../feeds/<date>.json.gz."""
    p = os.path.join(C, 'feeds', f'{d}.json')
    if os.path.exists(p):
        return json.load(open(p, encoding='utf-8'))
    import gzip
    return json.load(gzip.open(p + '.gz', 'rt', encoding='utf-8'))


def fl(s):
    try:
        return round(float(s.replace(',', '')), 6)
    except ValueError:
        return None


def nums_in(s):
    out = set()
    for m in NUM.finditer(s):
        v = fl(m.group(0).rstrip('.,'))
        if v is not None:
            out.add(v)
    return out


def card_numbers(card):
    ok, dates = set(), set()
    def add(v):
        if v is None: return
        v = abs(v); ok.add(round(v, 6))
        for nd in (0, 1, 2):
            ok.add(round(round(v, nd), 6))
    tr = card['treasury']; dates.add(tr['prior_close_date']); dates.add(tr['obs20_earlier_date']); dates.add(tr['prior_5obs_date'])
    for v in list(tr['prior_close_pct'].values()) + list(tr['obs20_earlier_pct'].values()):
        add(fl(v.rstrip('%')))
    for k in ('spread_10y_2y_bps', 'spread_10y_3m_bps', 'spread_30y_10y_bps'):
        add(tr[k])
    for v in list(tr['chg_20obs_bps'].values()) + list(tr['chg_5obs_bps'].values()):
        add(v)
    for t, m in card['markets'].items():
        dates.add(m['session']); dates.add(m['ref_20s_session'])
        for k in ('close', 'ref_20s_close'):
            v = fl(m[k]); add(v)
        for k in ('chg_1s_pct', 'chg_5s_pct', 'chg_20s_pct', 'chg_1s_pts', 'chg_20s_pts'):
            if k in m: add(m[k])
    return ok, dates


def paragraphs(spec):
    """yield (where, label, text) for every paragraph, checking structure on the way."""
    errs = []
    g = spec.get('geo', [])
    if [x.get('key') for x in g] != GEO:
        errs.append(f'geo keys {[x.get("key") for x in g]} != {GEO}')
    for x in g:
        if x.get('stance') not in ('Bullish', 'Bearish', 'Mixed'): errs.append(f'geo {x.get("key")} stance {x.get("stance")}')
        if not x.get('label'): errs.append(f'geo {x.get("key")} has no label')
        labs = [p[0] for p in x['parts']]
        if labs[-1] != 'Playbook ✓': errs.append(f'geo {x["key"]} last part {labs[-1]!r} != "Playbook ✓"')
        if x['key'] == 'CN' and labs != CN_PARTS: errs.append(f'CN parts {labs} != {CN_PARTS}')
        if x['key'] == 'US' and 'Rates & Curve' not in labs: errs.append('US block lacks a "Rates & Curve" part')
        for lab, t in x['parts']:
            yield f'geo:{x["key"]}', lab, t
    s = spec.get('sectors', [])
    if [x.get('key') for x in s] != SECT:
        errs.append(f'sector keys {[x.get("key") for x in s]} != {SECT}')
    for x in s:
        if x.get('stance') not in ('Bullish', 'Bearish', 'Mixed'): errs.append(f'sector {x.get("key")} stance')
        if [p[0] for p in x['parts']] != LABELS['sector']: errs.append(f'sector {x["key"]} labels {[p[0] for p in x["parts"]]}')
        for lab, t in x['parts']:
            yield f'sector:{x["key"]}', lab, t
    for key in ('earnings_pattern', 'crypto', 'flows'):
        b = spec.get(key) or {}
        if not b.get('title'): errs.append(f'{key} has no title')
        if [p[0] for p in b.get('parts', [])] != LABELS[key]: errs.append(f'{key} labels {[p[0] for p in b.get("parts", [])]}')
        for lab, t in b.get('parts', []):
            yield key, lab, t
    if not spec.get('retail_intro'): errs.append('retail_intro missing')
    else: yield 'retail_intro', 'Intro', spec['retail_intro']
    for key, n in COUNTS.items():
        arr = spec.get(key, [])
        if len(arr) != n: errs.append(f'{key}: {len(arr)} items, expected {n}')
        for i, b in enumerate(arr):
            if not b.get('title'): errs.append(f'{key}[{i}] has no title')
            if key == 'catalysts' and b.get('stance') not in ('Bullish', 'Bearish', 'Mixed'): errs.append(f'catalyst {i} stance')
            want = LABELS['retail_lead' if i == 0 else 'retail_small'] if key == 'retail' else LABELS[key]
            if [p[0] for p in b.get('parts', [])] != want: errs.append(f'{key}[{i}] labels {[p[0] for p in b.get("parts", [])]}')
            for lab, t in b.get('parts', []):
                yield f'{key}[{i}]', lab, t
    paragraphs.errs = errs


SECTION_MIN = {'geo:US': 330, 'geo:EU': 280, 'geo:CN': 600, 'geo:JP': 230, 'geo:AU': 230, 'geo:PL': 330,
               'earnings_pattern': 330, 'crypto': 280, 'flows': 450, 'retail[0]': 620}
SECTION_MIN.update({f'sector:{k}': 130 for k in SECT})
SECTION_MIN.update({f'underowned[{i}]': 110 for i in range(4)})
SECTION_MIN.update({f'anticipatory[{i}]': 130 for i in range(4)})
SECTION_MIN.update({f'catalysts[{i}]': 90 for i in range(6)})
SECTION_MIN.update({f'retail[{i}]': 140 for i in (1, 2, 3)})


def verify(d):
    D = dt.date.fromisoformat(d)
    spec = json.load(open(os.path.join(C, 'specs', f'{d}.json')))
    card = json.load(open(os.path.join(C, 'cards', f'{d}.json')))
    items = {x['id']: x for x in load_feed(d)['items']}
    cardnums, carddates = card_numbers(card)
    fails, warns = [], []
    paras = list(paragraphs(spec)); fails += [f'STRUCT {e}' for e in paragraphs.errs]
    allcited = {n for _, _, t in paras for n in CITE.findall(t) if n in items}
    report_title_nums = set().union(*[nums_in(items[n]['title']) for n in allcited]) if allcited else set()
    usage, words, per = {}, 0, {}
    for where, lab, t in paras:
        ids = CITE.findall(t)
        for n in ids:
            if n not in items: fails.append(f'{where} {lab}: citation {n} not in the {d} feed'); continue
            usage[n] = usage.get(n, 0) + 1
        body = CITE.sub(' ', t); words += len(body.split())
        per[where] = per.get(where, 0) + len(body.split())
        tnums = set().union(*[nums_in(items[n]['title']) for n in ids if n in items]) if ids else set()
        ttxt = ' '.join(items[n]['title'] for n in ids if n in items)
        for m in DATATAG.finditer(body):
            for src, dd in ((m.group(1), m.group(2)), (m.group(3), m.group(4))):
                if not src: continue
                if src == 'US Treasury' and dd != card['treasury']['prior_close_date']:
                    fails.append(f'{where} {lab}: Treasury tag date {dd} != card {card["treasury"]["prior_close_date"]}')
                if src == 'Yahoo Finance' and dd not in carddates:
                    fails.append(f'{where} {lab}: Yahoo tag date {dd} is not a session in the card')
        scan = DATATAG.sub(' ', body)
        scan = re.sub(r'\b\d{4}-\d{2}-\d{2}\b', lambda m: ' ' if m.group(0) in carddates else m.group(0), scan)
        for iso in re.findall(r'\b\d{4}-\d{2}-\d{2}\b', scan):
            fails.append(f'{where} {lab}: ISO date {iso} not a card session date')
        scan = re.sub(r'\b\d{4}-\d{2}-\d{2}\b', ' ', scan)
        scan = re.sub(r'\b(10Y|2Y|3M|5Y|30Y|1Y|20Y|7Y|10Y−2Y|10Y-2Y|2s10s|Q[1-4]|H[12]|G7|G20|5G|S&P 500|WIG20|WIG|CSI 300|'
                      r'Nasdaq 100|Nasdaq-100|Russell 2000|STOXX 600|Stoxx 600|Euro Stoxx 50|CAC 40|FTSE 100|Nikkei 225|'
                      r'ASX 200|Hang Seng|DAX 40|A320|737|787|777|F-35|M[1-4]|B200|GB200|H20|H200|Blackwell|3D|4K|'
                      r'COVID-19|Covid-19|24/7|X\d+)\b', ' ', scan)
        for m in MD.finditer(scan):
            mon = MONTHS[m.group(1)[:3].lower()]; day = int(m.group(2))
            try:
                when = min((dt.date(y, mon, day) for y in (D.year - 1, D.year, D.year + 1)), key=lambda c: abs((c - D).days))
            except ValueError:
                continue
            carried = any(re.search(rf'\b{m.group(1)[:3]}\w*\.? 0?{day}\b', items[n]['title'], re.I) for n in ids if n in items)
            if when >= D and not carried:
                fails.append(f'{where} {lab}: date "{m.group(0)}" is on/after the report date and not in a cited headline')
        scan_nums = MD.sub(' ', scan)
        for m in NUM.finditer(scan_nums):
            raw = m.group(0).rstrip('.,'); v = fl(raw)
            if v is None: continue
            if v in tnums or v in cardnums or v in STRUCTURAL or (v == int(v) and (v <= 12 or 1990 <= v <= 2025)):
                continue
            if v in report_title_nums:
                warns.append(f'{where} {lab}: number {raw} only in a headline cited elsewhere'); continue
            fails.append(f'{where} {lab}: number {raw} not traceable (card / cited headline)')
        if BANNED.search(body): fails.append(f'{where} {lab}: hindsight/correction wording "{BANNED.search(body).group(0)}"')
        if COPPER.search(body): fails.append(f'{where} {lab}: copper ratio / growth-gauge wording')
        for m in CAL.finditer(body):
            warns.append(f'{where} {lab}: calendar wording "{m.group(0)}" — needs a dated headline')
        if len(body.split()) > 260: warns.append(f'{where} {lab}: {len(body.split())} words (long)')
    for n, k in usage.items():
        if k > 4: warns.append(f'citation {n} used {k} times')
    if len(usage) < 50: fails.append(f'only {len(usage)} distinct citations (need ≥ 50)')
    if not 8000 <= words <= 12500: warns.append(f'{words} words in total')
    for key, need in SECTION_MIN.items():
        if per.get(key, 0) < need: warns.append(f'{key}: {per.get(key, 0)} words, brief minimum {need}')
    return fails, warns, len(usage), words


if __name__ == '__main__':
    bad = 0
    for d in sys.argv[1:]:
        f, w, n, words = verify(d)
        for x in f: print('FAIL', d, x)
        for x in w: print('WARN', d, x)
        print(f'{d}: {"PASS" if not f else "FAIL"} — {n} sources, {words} words, {len(f)} fail, {len(w)} warn')
        bad += bool(f)
    sys.exit(1 if bad else 0)
