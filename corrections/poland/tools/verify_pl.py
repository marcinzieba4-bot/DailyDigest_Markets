#!/usr/bin/env python3
"""verify_pl.py <date> — checks pl/new/<date>.html against the feed, card and old block."""
import sys, re, json, html, collections, datetime as dt
W = '/tmp/claude-0/-home-user/01233cf7-f758-5bad-b280-d38226412ca9/scratchpad/work/pl'
d = sys.argv[1]
D = dt.date.fromisoformat(d)
try:
    new = open(f'{W}/new/{d}.html', encoding='utf-8').read()
except FileNotFoundError:
    print(f'== {d}: FAIL\n  FAIL: pl/new/{d}.html not written'); sys.exit(1)
old = open(f'{W}/old/{d}.html', encoding='utf-8').read()
feed = json.load(open(f'{W}/feeds/{d}.json'))
card = json.load(open(f'{W}/cards/{d}.json'))
fails, warns = [], []

# 1. structure
s = new.strip()
opener = re.match(r'<div style="[^"]*">', old).group(0)
if not s.startswith(opener): fails.append('block must start with the old <div ...> opener: ' + opener)
if not s.endswith('</div>'): fails.append('block must end with </div>')
if s.count('<div') != 1 or s.count('</div>') != 1: fails.append('exactly one <div> allowed')
if s.count('<h3') != 1 or '🇵🇱' not in s: fails.append('exactly one <h3> with 🇵🇱 required')
tags = collections.Counter(t.lower() for t in re.findall(r'<(/?\w+)', s))
for t in list(tags):
    if t.lstrip('/') not in ('div', 'h3', 'span', 'p', 'strong', 'em', 'br'): fails.append('disallowed tag <' + t + '>')
for t in ('p', 'strong', 'em', 'span', 'h3'):
    if tags.get(t, 0) != tags.get('/' + t, 0): fails.append(f'unbalanced <{t}>')
if re.search(r'<(p|strong|em)\s+[^>]', s): fails.append('no attributes allowed on <p>/<strong>/<em>')
m = re.search(r'<span style="font-size:13px;font-weight:normal;color:(#[0-9a-f]{6})">(\w+)</span>', s)
if not m: fails.append('stance span missing or malformed')
elif (m.group(2), m.group(1)) not in (('Bullish', '#2d7a2d'), ('Mixed', '#b07d00'), ('Bearish', '#c0392b')):
    fails.append(f'stance/colour pair not allowed: {m.group(2)} {m.group(1)}')

# 2. text, labels, length
text = html.unescape(re.sub(r'<[^>]+>', ' ', s))
text = re.sub(r'\s+', ' ', text)
_prose = re.sub(r'\[[^\]]{1,12}\]', ' ', text)                       # drop [Mon DD] tags
words = len(re.findall(r"[A-Za-zÀ-ž][A-Za-zÀ-ž'’\-]*", _prose))        # alphabetic words only; numbers/tickers not counted
if not 550 <= words <= 1000: fails.append(f'body length {words} prose words, need 550-900 (hard cap 1000)')
for label in ('Macro Stance', 'Markets', 'Fiscal', 'Corporate', 'Geopolitics', 'New / Most Important', 'Playbook', 'Divergence'):
    if label not in text: fails.append('missing section label: ' + label)
for w in ('corrected', 'retroactiv', 'rewritten', 'expanded section', 'hindsight', 'in retrospect', 'as it turned out', 'would later', 'later that'):
    if w in text.lower(): fails.append('forbidden meta/hindsight wording: ' + w)

# 3. dates mentioned must not be after the report date
MON = {m: i for i, m in enumerate(['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'], 1)}
for mm in re.finditer(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})\b', text):
    mo = MON[mm.group(1)[:3].lower()]; day = int(mm.group(2))
    try: dd = dt.date(D.year, mo, day)
    except ValueError: continue
    if dd > D: fails.append(f'date after report date: {mm.group(0)}')
for mm in re.finditer(r'\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\b', text):
    mo = MON[mm.group(2)[:3].lower()]; day = int(mm.group(1))
    try: dd = dt.date(D.year, mo, day)
    except ValueError: continue
    if dd > D: fails.append(f'date after report date: {mm.group(0)}')

# 4. numbers must come from feed titles, card or old block
def nums(t):
    t = re.sub(r'(\d),(\d)', r'\1.\2', t)          # Polish decimal comma
    t = re.sub(r'(\d)[  ](\d{3})', r'\1\2', t)     # thousands space
    return set(re.findall(r'\d+(?:\.\d+)?', t))
allowed = set()
for items in feed['feeds'].values():
    for it in items: allowed |= nums(it['title'])
allowed |= nums(html.unescape(re.sub(r'<[^>]+>', ' ', old)))
def walk(o):
    global allowed
    if isinstance(o, dict): [walk(v) for v in o.values()]
    elif isinstance(o, list): [walk(v) for v in o]
    elif isinstance(o, (int, float)):
        allowed.add(str(o)); allowed.add(str(abs(o)))
        if isinstance(o, float):
            for k in (0, 1, 2, 3, 4): allowed.add(f'{abs(o):.{k}f}')
    elif isinstance(o, str): allowed |= nums(o)
walk(card)
allowed |= {str(i) for i in range(0, 32)} | {'2024', '2025', '2026', '1990', '2008', '2020', '2022', '2023', '100', '50', '1000', '20'}
used = nums(re.sub(r'\d{1,3}(?:,\d{3})+', lambda m: m.group(0).replace(',', ''), text))
unknown = sorted(used - allowed, key=lambda x: (len(x), x))
if unknown: warns.append('numbers not found in feed/card/old block: ' + ', '.join(unknown))

print(f"== {d}: {'PASS' if not fails else 'FAIL'}  ({words} words)")
for f in fails: print('  FAIL:', f)
for w in warns: print('  WARN:', w)
sys.exit(1 if fails else 0)
