#!/usr/bin/env python3
"""verify_cn.py <date> — checks new/<date>.html (wide China block) against the date-bounded feed and that day's report."""
import sys, os, re, html, collections, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import C, report, china_block, totext, nums, feed_items
d = sys.argv[1]; D = dt.date.fromisoformat(d)
try: new = open(os.path.join(C, 'new', f'{d}.html'), encoding='utf-8').read().strip()
except FileNotFoundError: print(f'== {d}: FAIL new/{d}.html missing'); sys.exit(1)
old = open(os.path.join(C, 'old', f'{d}.html'), encoding='utf-8').read()
rep = report(d); m = china_block(rep)
rest = rep[:m.start()] + rep[m.end():]                       # the report outside the China block
fails, warns = [], []
opener = re.match(r'<div style="[^"]*">', old).group(0)
if not new.startswith(opener): fails.append('must start with the old <div> opener')
if not new.endswith('</div>') or new.count('<div') != 1 or new.count('</div>') != 1: fails.append('exactly one <div>…</div>')
if new.count('<h3') != 1 or '🇨🇳' not in new: fails.append('exactly one <h3> with 🇨🇳')
tags = collections.Counter(t.lower() for t in re.findall(r'<(/?\w+)', new))
for t in tags:
    if t.lstrip('/') not in ('div', 'h3', 'span', 'p', 'strong', 'em', 'br'): fails.append('disallowed tag ' + t)
for t in ('p', 'strong', 'em', 'span', 'h3'):
    if tags.get(t, 0) != tags.get('/' + t, 0): fails.append(f'unbalanced <{t}>')
if re.search(r'<(p|strong|em)\s+[^>]', new): fails.append('attributes on p/strong/em')
sm = re.search(r'<span style="font-size:13px;font-weight:normal;color:(#[0-9a-f]{6})">(\w+)</span>', new)
if not sm or (sm.group(2), sm.group(1)) not in (('Bullish', '#2d7a2d'), ('Mixed', '#b07d00'), ('Bearish', '#c0392b')):
    fails.append('stance span missing / bad colour pair')
text = totext(new)
words = len(re.findall(r"[A-Za-z][A-Za-z'’\-]*", re.sub(r'\[[^\]]{1,12}\]', ' ', text)))
if not 450 <= words <= 900: fails.append(f'{words} prose words, need 450-850 (cap 900)')
for lab in ('Macro Stance', 'PMIs & Activity', 'Credit Impulse', 'Property', 'Fiscal, Policy & Trade', 'Markets & Flows',
            'New / Most Important', 'Playbook', 'Divergence'):
    if lab not in text: fails.append('missing label: ' + lab)
low = text.lower()
for w in ('corrected', 'retroactiv', 'rewritten', 'expanded section', 'hindsight', 'in retrospect', 'as it turned out', 'would later'):
    if w in low: fails.append('meta/hindsight wording: ' + w)
if re.search(r'(?i)gold\s*/\s*copper|oil\s*/\s*copper|copper\s*/\s*gold', text): fails.append('copper ratio used')
if re.search(r'(?i)copper', text) and not re.search(r'(?i)copper[^.]*(AI|data[- ]cent|grid|electrif)', text):
    fails.append('copper mentioned outside an AI / grid framing')
# dates: every [Mon DD] tag and written date must be before the report date and within 35 days
MON = {m: i for i, m in enumerate(['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'], 1)}
for mm in re.finditer(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})\b', text):
    try: dd = dt.date(D.year, MON[mm.group(1)[:3].lower()], int(mm.group(2)))
    except ValueError: continue
    if dd >= D: fails.append(f'date not before report date: {mm.group(0)}')
    elif (D - dd).days > 36: warns.append(f'date older than the 35-day window: {mm.group(0)}')
# every tagged headline date must exist in the eligible feed
items = feed_items(d)
fdates = {x['t'] for x in items}
for mm in re.finditer(r'\[(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d{1,2})\]', text):
    iso = dt.date(D.year, MON[mm.group(1).lower()], int(mm.group(2))).isoformat()
    if iso not in fdates: warns.append(f'tag {mm.group(0)} matches no eligible headline date')
allowed = set()
for x in items: allowed |= nums(x['title'])
allowed |= nums(totext(rep))
allowed |= {str(i) for i in range(0, 32)} | {'50', '100', '2008', '2015', '2020', '2021', '2022', '2023', '2024', '2025', '2026', '2027'}
unknown = sorted(nums(text) - allowed, key=lambda x: (len(x), x))
if unknown: warns.append('numbers not in eligible feed / report: ' + ', '.join(unknown))
print(f"== {d}: {'PASS' if not fails else 'FAIL'} ({words} words)")
for f in fails: print('  FAIL:', f)
for w in warns: print('  WARN:', w)
sys.exit(1 if fails else 0)
