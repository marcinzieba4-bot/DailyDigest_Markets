"""verify.py <dates> — check ../specs/<date>.json before rendering. Prints FAIL / WARN lines and a PASS summary.

FAIL: wrong structure or labels; a citation id that is not in that date's feed; a number that is neither in the
date's market card, nor in a headline cited in the same paragraph, nor a whitelisted structural number; a
month-day date on or after the report date that no cited headline in the paragraph carries; a data-source tag
"(Yahoo Finance, prior close X)" / "(US Treasury, prior close X)" whose X is not a session date in the card;
hindsight / correction wording; copper or gold-copper used as a growth gauge; narration about the inputs ("the writer",
"the card", "not a reported fact", "the feed carries no …"), calibrated on the August 2026 pages where such wording is
absent (feed mentions are capped); a malformed retail title; length or per-block ranges outside the July contract; citation reuse above four.
The verifier is an automated gate; global card-number membership does not establish instrument, session, horizon, unit,
split context or claim meaning. Every financial claim still needs independent own-date review.
WARN: calendar language requiring a dated preview; unusually long paragraphs; repeated sentences. Finalization requires explicit evidence-bound review of every warning."""
import json, os, re, sys, datetime as dt
from pathlib import Path

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATES = [dt.date(2024, 7, day).isoformat() for day in range(1, 32)
         if dt.date(2024, 7, day).weekday() < 5]
NONRETAIL_KEYS = {'date', 'geo', 'sectors', 'earnings_pattern', 'underowned', 'crypto', 'flows', 'anticipatory', 'catalysts'}
RETAIL_KEYS = {'date', 'retail_intro', 'retail'}
FULL_KEYS = NONRETAIL_KEYS | RETAIL_KEYS
WINDOW_DAYS = {'news': 7, 'result': 14, 'monthly': 35}
CITE = re.compile(r'\[\[(n\d{4,6})\]\]')
NUM = re.compile(r'(?<![A-Za-z])\d[\d,]*(?:\.\d+)?')
GEO = ['US', 'EU', 'CN', 'JP', 'AU', 'PL']
SECT = ['XLK', 'XLC', 'XLF', 'XLE', 'XLI', 'XLY', 'XLP', 'XLV', 'XLB', 'XLRE', 'XLU', 'SXAP', 'SOXX']
CN_PARTS = ['Macro Stance', 'PMIs & Activity', 'Credit Impulse', 'Property', 'Fiscal, Policy & Trade', 'Markets & Flows',
            'New / Most Important', 'Playbook ✓']
PL_PARTS = ['Macro Stance', 'Markets', 'Fiscal & Politics', 'Corporate & Sectors', 'Geopolitics & Security',
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
STRUCTURAL = {2024}
MONTHS = {m: i for i, m in enumerate(['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'], 1)}
MD = re.compile(r'\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|'
                r'Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.? (\d{1,2})\b')
BANNED = re.compile(r'\b(retrospective(ly)?|hindsight|in retrospect|correction to this|turned out|would later|'
                    r'as it happened)\b', re.I)
COPPER = re.compile(r'(gold\s*/\s*copper|copper\s*/\s*gold|oil\s*/\s*copper|copper\s*/\s*oil|dr\.? copper|'
                    r'copper (?:as|is) a (?:gauge|barometer|signal) of (?:global|china|growth))', re.I)
META = re.compile(r"\b(the writer|writer(?:'|’)s|not a reported fact|the (?:market )?card|market card|"
                  r"(?:feed|feeds|headlines?) (?:has|have|shows?|contains?|carries) no|"
                  r"this reconstruction|information cutoff)\b", re.I)
FEED = re.compile(r"\b(the feed|feed carries|in the feed|the feeds|our sources)\b", re.I)
FX_PAIR = r'(?:USD|EUR|GBP|AUD|NZD|JPY|CNY|CNH|PLN|CHF|CAD)\s*/\s*(?:USD|EUR|GBP|AUD|NZD|JPY|CNY|CNH|PLN|CHF|CAD)'
FX = re.compile(r'\b'+FX_PAIR+r'\s*(?:pair\s*)?(?:(?:closed|stood|finished|ended|was|at|traded|quoted|rose|fell|gained|lost|advanced|declined|changed)\s*(?:at|by|to)?\s*)?[+−-]?\d|\b[A-Z]{3,6}=X\b', re.I)
CAL = re.compile(r'\b(upcoming|next week|later this week|this week|due on|scheduled for|set to report|will report|'
                 r'reports? (?:on|after) (?:Monday|Tuesday|Wednesday|Thursday|Friday))\b', re.I)
DATATAG = re.compile(r'\((Yahoo Finance|US Treasury), prior (?:close|completed daily close) (\d{4}-\d{2}-\d{2})(?:; (Yahoo Finance|US Treasury), prior (?:close|completed daily close) (\d{4}-\d{2}-\d{2}))?\)')


def validate_date(d):
    if d not in DATES:
        raise ValueError('SCOPE: expected a July 2024 weekday, including exchange holidays: '+str(d))
    return dt.date.fromisoformat(d)


def load_feed(d):
    """Read the frozen gzip first; reject a conflicting loose source copy."""
    import gzip
    p = Path(C)/'feeds'/f'{d}.json'
    frozen = Path(str(p)+'.gz')
    if frozen.exists():
        feed = json.loads(gzip.decompress(frozen.read_bytes()))
        if p.exists() and json.loads(p.read_text()) != feed:
            raise ValueError('Conflicting loose and frozen own-date feeds: '+d)
        if feed.get('date')!=d: raise ValueError('Own-date feed identity mismatch: '+d)
        return feed
    feed=json.loads(p.read_text())
    if feed.get('date')!=d: raise ValueError('Own-date feed identity mismatch: '+d)
    return feed


def load_exclusions(d, feed):
    p = Path(C)/'exclusions'/f'{d}.json'
    if not p.is_file():
        raise ValueError('Missing own-date semantic/timing exclusions record: '+d)
    value = json.loads(p.read_text())
    if value.get('date') != d or not isinstance(value.get('exclusions'), list):
        raise ValueError('Wrong date or malformed source exclusions record: '+d)
    ids = [row['id'] for row in value['exclusions']]
    if len(ids) != len(set(ids)) or not set(ids) <= {row['id'] for row in feed['items']}:
        raise ValueError('Duplicate or foreign source exclusions: '+d)
    if value.get('feed_sha256'):
        import hashlib
        p = Path(C)/'feeds'/f'{d}.json.gz'
        if value['feed_sha256'] != hashlib.sha256(p.read_bytes()).hexdigest():
            raise ValueError('Stale source exclusions record: '+d)
    return set(ids)


def effective_window_days(item):
    # A curator may narrow a broad retrieval category after semantic screening.
    # Without that explicit field, own-date exclusions and independent review
    # enforce company-versus-macro meaning; no company-name guessing is used.
    days = WINDOW_DAYS.get(item.get('cat'))
    narrowed = item.get('semantic_window_days')
    if narrowed is not None:
        if type(narrowed) is not int or narrowed not in WINDOW_DAYS.values():
            raise ValueError('Invalid semantic window for '+str(item.get('id')))
        days = min(days, narrowed) if days else narrowed
    return days


def fl(s):
    try:
        return round(float(s.replace(',', '')), 6)
    except (ValueError, TypeError, AttributeError):
        return None


def nums_in(s):
    out = set()
    for m in NUM.finditer(s):
        raw = m.group(0).rstrip('.,')
        v = fl(raw)
        if v is not None:
            out.add(v)
        if re.fullmatch(r'\d+,\d{1,2}', raw):                  # Polish headlines write decimals with a comma: "4,00", "2,8"
            v2 = fl(raw.replace(',', '.'))
            if v2 is not None:
                out.add(v2)
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
        if t.endswith('=X'): continue
        dates.add(m['session'])
        for key in ('ref_1s_session', 'ref_5s_session', 'ref_20s_session'):
            if m.get(key) is not None: dates.add(m[key])
        for k in ('close', 'ref_20s_close'):
            v = fl(m[k]); add(v)
        for k in ('chg_1s_pct', 'chg_5s_pct', 'chg_20s_pct', 'chg_1s_pts', 'chg_20s_pts'):
            if k in m: add(m[k])
    return ok, dates


def paragraphs(spec, include_retail=True, retail_only=False):
    """Yield validated prose without crashing on an incomplete author draft."""
    errs = []
    def block(value, where, labels, stance=False, title=False, policy_label=False):
        if not isinstance(value, dict):
            errs.append(where+' is not a block object'); return []
        if stance and value.get('stance') not in ('Bullish', 'Bearish', 'Mixed'):
            errs.append(where+' has an invalid stance')
        if title and not isinstance(value.get('title'), str): errs.append(where+' needs a title')
        if title and not value.get('title', '').strip(): errs.append(where+' has an empty title')
        if policy_label and not value.get('label'): errs.append(where+' needs a policy label')
        pairs = value.get('parts', [])
        if not isinstance(pairs, list) or any(not isinstance(p, list) or len(p)!=2 or not all(isinstance(x,str) for x in p) for p in pairs):
            errs.append(where+' parts must be ordered [label, text] string pairs'); return []
        actual = [p[0] for p in pairs]
        choices = labels if labels and isinstance(labels[0], list) else [labels]
        if actual not in choices: errs.append(where+' labels '+repr(actual)+' != '+repr(labels))
        if any(not p[1].strip() for p in pairs): errs.append(where+' has empty prose')
        return [(where, label, text) for label, text in pairs]
    if not retail_only:
        geo = spec.get('geo', [])
        if not isinstance(geo, list): geo=[]; errs.append('geo must be an array')
        if [x.get('key') if isinstance(x,dict) else None for x in geo] != GEO: errs.append('geo keys/order differ from '+repr(GEO))
        geo_labels = {
            'US':['Macro Stance','Rates & Curve','New / Most Important','Playbook ✓'],
            'EU':[['Macro Stance','Credit & Inflation','New / Most Important','Playbook ✓'],['Macro Stance','Activity & Inflation','New / Most Important','Playbook ✓']],
            'CN':CN_PARTS,'JP':['Macro Stance','Activity & Currency','Playbook ✓'],
            'AU':['Macro Stance','Demand & Financing','Playbook ✓'],'PL':PL_PARTS}
        for value in geo:
            key = value.get('key') if isinstance(value,dict) else None
            yield from block(value,'geo:'+str(key),geo_labels.get(key,[]),stance=True,policy_label=True)
            if key in {'CN','PL'} and isinstance(value,dict):
                body = next((p[1] for p in value.get('parts',[]) if isinstance(p,list) and len(p)==2 and p[0]=='Playbook ✓'),'')
                if '⚠ Divergence:' not in body or not body.split('⚠ Divergence:',1)[1].strip(): errs.append(str(key)+' Playbook needs a concluding ⚠ Divergence: assessment')
        sectors = spec.get('sectors', [])
        if not isinstance(sectors,list): sectors=[]; errs.append('sectors must be an array')
        if [x.get('key') if isinstance(x,dict) else None for x in sectors] != SECT: errs.append('sector keys/order differ from '+repr(SECT))
        for value in sectors:
            yield from block(value,'sector:'+str(value.get('key') if isinstance(value,dict) else None),LABELS['sector'],stance=True)
        for key in ('earnings_pattern','crypto','flows'):
            yield from block(spec.get(key),key,LABELS[key],title=True)
    if include_retail:
        intro = spec.get('retail_intro')
        if not isinstance(intro,str) or not intro.strip(): errs.append('retail_intro missing or empty')
        else: yield 'retail_intro','Intro',intro
    for key,n in COUNTS.items():
        if key=='retail' and not include_retail or key!='retail' and retail_only: continue
        arr=spec.get(key,[])
        if not isinstance(arr,list): arr=[]; errs.append(key+' must be an array')
        if len(arr)!=n: errs.append(f'{key}: {len(arr)} items, expected {n}')
        for i,value in enumerate(arr):
            labels=LABELS['retail_lead' if i==0 else 'retail_small'] if key=='retail' else LABELS[key]
            yield from block(value,f'{key}[{i}]',labels,stance=key=='catalysts',title=True)
    paragraphs.errs=errs


def block_ranges(spec, include_retail=True, retail_only=False):
    """Exact body-word ranges, excluding headings/labels and citation markers."""
    rows=[]
    def add(section,name,value,bounds):
        if not isinstance(value,dict): return
        pairs=value.get('parts',[])
        words=sum(len(CITE.sub(' ',p[1]).split()) for p in pairs if isinstance(p,list) and len(p)==2 and isinstance(p[1],str))
        low,high=bounds
        rows.append(dict(section=section,block=name,words=words,minimum=low,maximum=high,in_range=low<=words<=high))
    if not retail_only:
        bounds={'US':(400,500),'EU':(250,350),'CN':(800,950),'JP':(270,350),'AU':(200,300),'PL':(850,1050)}
        for value in spec.get('geo',[]):
            if isinstance(value,dict) and value.get('key') in bounds:add('geo',value['key'],value,bounds[value['key']])
        for value in spec.get('sectors',[]):
            if isinstance(value,dict):add('sectors',value.get('key'),value,(150,200))
        for section,bound in [('earnings_pattern',(350,420)),('crypto',(290,360)),('flows',(600,750))]:add(section,section,spec.get(section),bound)
        for section,bound in [('underowned',(110,150)),('anticipatory',(140,190)),('catalysts',(100,140))]:
            for i,value in enumerate(spec.get(section,[])):add(section,str(i+1),value,bound)
    if include_retail:
        for i,value in enumerate(spec.get('retail',[])):add('retail',str(i+1),value,(650,850) if i==0 else (150,220))
    return rows


def verify(d, nonretail=False, spec_override=None, retail_only=False):
    try: D = validate_date(d)
    except ValueError as exc: return [str(exc)], [], 0, 0
    if nonretail and retail_only: return ['Choose nonretail or retail validation'], [], 0, 0
    spec_dir = 'nonretail_drafts' if nonretail else 'specs'
    if retail_only: spec_dir='retail_drafts'
    spec = spec_override if spec_override is not None else json.load(open(os.path.join(C, spec_dir, f'{d}.json')))
    card = json.load(open(os.path.join(C, 'cards', f'{d}.json')))
    feed = load_feed(d)
    items = {x['id']: x for x in feed['items']}
    cardnums, carddates = card_numbers(card)
    fails, warns = [], []
    cutoff = dt.datetime.fromisoformat(d).replace(tzinfo=dt.timezone.utc)
    wanted = RETAIL_KEYS if retail_only else NONRETAIL_KEYS if nonretail else FULL_KEYS
    if set(spec) != wanted: fails.append('STRUCT top-level keys differ: missing '+repr(sorted(wanted-set(spec)))+'; extra '+repr(sorted(set(spec)-wanted)))
    if feed.get('date') != d: fails.append('SCOPE: feed date mismatch')
    if len(items) != len(feed['items']): fails.append('EVIDENCE duplicate own-date source IDs')
    def strings(node):
        if isinstance(node,str): yield node
        elif isinstance(node,list):
            for value in node: yield from strings(value)
        elif isinstance(node,dict):
            for value in node.values(): yield from strings(value)
    for value in strings(spec):
        for token in re.findall(r'\[\[([^\]]+)\]\]', value):
            if not re.fullmatch(r'n\d{4,6}',token) or token not in items:
                fails.append('CITATION unresolved/missing token [['+token+']]')
    if spec.get('date') != d:
        fails.append('SCOPE: spec date mismatch')
    if card.get('report_date') != d or card.get('cutoff_utc') != d+'T00:00:00Z':
        fails.append('SCOPE: market card identity/cutoff mismatch')
    for item in items.values():
        pub = dt.datetime.fromisoformat(item['published_at'].replace('Z','+00:00'))
        days = effective_window_days(item)
        if pub.tzinfo is None or days is None or not cutoff-dt.timedelta(days=days) <= pub < cutoff:
            fails.append('EVIDENCE cutoff/window violation: '+item['id'])
    for ticker, market in card['markets'].items():
        reference_dates=[market.get(key) for key in ('ref_1s_session','ref_5s_session','ref_20s_session')]
        if market['session'] >= d or any(value is not None and value >= d for value in reference_dates):
            fails.append('MARKET session violation: '+ticker)
        if market['ref_20s_session'] is None and not market.get('history_limitation'):
            fails.append('MARKET reference missing without explicit history limitation: '+ticker)
    if card['treasury']['prior_close_date'] >= d:
        fails.append('TREASURY session violation')
    paras = list(paragraphs(spec, include_retail=not nonretail, retail_only=retail_only)); fails += [f'STRUCT {e}' for e in paragraphs.errs]
    allcited = {n for _, _, t in paras for n in CITE.findall(t) if n in items}
    try:
        excluded=load_exclusions(d,feed)
        if allcited & excluded: fails.append('EVIDENCE: known premature/stale/ambiguous source used: '+repr(sorted(allcited & excluded)))
    except (ValueError,KeyError,TypeError) as exc:
        fails.append('EVIDENCE: '+str(exc))
    report_title_nums = set().union(*[nums_in(items[n]['title']) for n in allcited]) if allcited else set()
    usage, words, per = {}, 0, {}
    feed_hits = [0]; sentences = {}
    for where, lab, t in paras:
        for token in re.findall(r'\[\[([^\]]+)\]\]', t):
            if not re.fullmatch(r'n\d{4,6}', token):
                fails.append(f'{where} {lab}: unresolved noncanonical citation marker [[{token}]]')
        ids = CITE.findall(t)
        for n in ids:
            if n not in items: fails.append(f'{where} {lab}: citation {n} not in the {d} feed'); continue
            usage[n] = usage.get(n, 0) + 1
        body = CITE.sub(' ', t); words += len(body.split())
        per[where] = per.get(where, 0) + len(body.split())
        for sn in re.split(r'(?<=[.!?])\s+', DATATAG.sub('', body)):
            k = re.sub(r'[^a-z0-9 ]', '', sn.lower()).strip()
            if len(k.split()) >= 9: sentences.setdefault(k, []).append(where)
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
            if iso not in ttxt: fails.append(f'{where} {lab}: ISO date {iso} not a card session or locally cited headline date')
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
        scan_nums = re.sub(r'\b(?:1|5|20)[- ](?:session|observation)s?\b', ' ', scan_nums, flags=re.I)
        for m in NUM.finditer(scan_nums):
            raw = m.group(0).rstrip('.,'); v = fl(raw)
            if v is None: continue
            if v in tnums or v in cardnums or v in STRUCTURAL:
                continue
            if v in report_title_nums:
                fails.append(f'{where} {lab}: number {raw} only in a headline cited elsewhere; same-paragraph support required'); continue
            fails.append(f'{where} {lab}: number {raw} not traceable (card / cited headline)')
        mm = META.search(body)
        if mm: fails.append(f'{where} {lab}: narration about the inputs "{mm.group(0)}" — write it as an ordinary report')
        feed_hits[0] += len(FEED.findall(body))
        if BANNED.search(body): fails.append(f'{where} {lab}: hindsight/correction wording "{BANNED.search(body).group(0)}"')
        if COPPER.search(body): fails.append(f'{where} {lab}: copper ratio / growth-gauge wording')
        if FX.search(body): fails.append(f'{where} {lab}: forbidden numeric spot-FX mark or =X instrument')
        for m in CAL.finditer(body):
            warns.append(f'{where} {lab}: calendar wording "{m.group(0)}" — needs a dated headline')
        if len(body.split()) > 260: warns.append(f'{where} {lab}: {len(body.split())} words (long)')
    for n, k in usage.items():
        if k > 4: fails.append(f'citation {n} used {k} times (maximum 4)')
    if not retail_only and len(usage) < 50: fails.append(f'only {len(usage)} distinct citations (need ≥ 50)')
    minimum,maximum=(1200,1350) if retail_only else (8500,9200) if nonretail else (9500,11000)
    if not minimum<=words<=maximum: fails.append(f'{words} body words; required range {minimum}–{maximum}')
    for row in block_ranges(spec,include_retail=not nonretail,retail_only=retail_only):
        if not row['in_range']: fails.append(f"RANGE {row['section']} {row['block']}: {row['words']} words; required {row['minimum']}–{row['maximum']}")
    nr_words=sum(row['words'] for row in block_ranges(spec,include_retail=False)) if not retail_only else 0
    if not retail_only and not 8500<=nr_words<=9200: fails.append(f'NONRETAIL {nr_words} words; required 8500–9200')
    if not nonretail:
        retail_words=per.get('retail_intro',0)+sum(per.get(f'retail[{i}]',0) for i in range(4))
        if not 1200<=retail_words<=1350: fails.append(f'RETAIL {retail_words} words including intro; required 1200–1350')
    if feed_hits[0]: fails.append(f'Input/source narration appears {feed_hits[0]} times')
    for k, w in sentences.items():
        if len(w) > 1: warns.append(f'repeated sentence in {sorted(set(w))}: "{k[:80]}…"')
    for i,x in enumerate(spec.get('retail',[])):
        title=x.get('title','')
        match=re.fullmatch(r'(.+?) / ([A-Z0-9^][A-Z0-9^.=/-]*) — (.+)',title)
        if not match: fails.append(f'retail[{i}] title needs Name / TICKER — the hook')
        elif len(match.group(3).split())>8 or any(q in match.group(3) for q in ('"','“','”')): fails.append(f'retail[{i}] hook exceeds eight words or contains quotation marks')
    return fails, warns, len(usage), words


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dates',nargs='*')
    mode=parser.add_mutually_exclusive_group();mode.add_argument('--nonretail',action='store_true');mode.add_argument('--retail',action='store_true')
    parser.add_argument('--counts',action='store_true',help='Print exact own-date body-word counts and required ranges')
    args=parser.parse_args();bad=0
    for d in args.dates or DATES:
        try: f,w,n,words=verify(d,nonretail=args.nonretail,retail_only=args.retail)
        except (OSError,ValueError,KeyError,TypeError) as exc: f,w,n,words=[str(exc)],[],0,0
        if args.counts and d in DATES:
            folder='retail_drafts' if args.retail else 'nonretail_drafts' if args.nonretail else 'specs'
            path=Path(C)/folder/(d+'.json')
            if path.is_file():
                for row in block_ranges(json.loads(path.read_text()),include_retail=not args.nonretail,retail_only=args.retail):
                    print('COUNT',d,row['section'],row['block'],row['words'],f"required {row['minimum']}–{row['maximum']}")
        for x in f:print('FAIL',d,x)
        for x in w:print('WARN',d,x)
        print(f'{d}: {"PASS" if not f else "FAIL"} — {n} sources, {words} words, {len(f)} fail, {len(w)} warn')
        bad+=bool(f)
    sys.exit(1 if bad else 0)
