#!/usr/bin/env python3
"""verify_pattern.py <date> — checks pattern/<date>.html (Earnings Pattern section) against the two-week earnings feeds
and the original report: exact heading, one block, five labels, ~200-400 words, tags before D and within 14 days,
numbers traceable, no Polish market references, copper rules."""
import sys, os, re, collections, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import C, totext, nums, feed_items, PATTERN_H2
d = sys.argv[1]; D = dt.date.fromisoformat(d)
new = open(os.path.join(C, 'pattern', f'{d}.html'), encoding='utf-8').read().strip()
orig = open(os.path.join(C, 'orig', f'{d}.html'), encoding='utf-8').read()
fails, warns = [], []
if not new.startswith(PATTERN_H2): fails.append('must start with the exact Earnings Pattern <h2>')
if new.count('<div') != 1 or new.count('</div>') != 1 or not new.endswith('</div>'): fails.append('exactly one <div> block after the <h2>')
tags = collections.Counter(t.lower() for t in re.findall(r'<(/?\w+)', new))
for t in tags:
    if t.lstrip('/') not in ('div', 'h2', 'p', 'strong', 'em', 'br', 'span'): fails.append('disallowed tag ' + t)
for t in ('p', 'strong', 'div', 'h2'):
    if tags.get(t, 0) != tags.get('/' + t, 0): fails.append(f'unbalanced <{t}>')
text = totext(new)
for lab in ('Rewarded:', 'Punished:', 'Pattern:', 'Attention into EPS:', 'Playbook:'):
    if text.count(lab) != 1: fails.append(f'label {lab} x{text.count(lab)}')
words = len(re.findall(r"[A-Za-z][A-Za-z'’\-]*", re.sub(r'\[[^\]]{1,12}\]', ' ', text)))
if words < 180: warns.append(f'{words} words (aim ~250-350)')
if words > 430: warns.append(f'{words} words (aim ~250-350, keep it quick)')
if re.search(r'Poland|Polish|Warsaw|\bGPW\b|\bWIG|KGHM|Orlen|\bPKO\b|Pekao|\bPZU\b|Allegro|\bXTB\b|zloty', text): fails.append('Polish reference')
if re.search(r'(?i)(gold|oil)\s*/\s*copper|copper\s*/\s*(gold|oil)', text): fails.append('copper ratio')
for w in ('corrected', 'retroactiv', 'rewritten', 'in hindsight', 'as it turned out'):
    if w in text.lower(): fails.append('meta wording: ' + w)
MON = {m: i for i, m in enumerate(['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'], 1)}
for mm in re.finditer(r'\[(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d{1,2})\]', text):
    dd = dt.date(D.year, MON[mm.group(1).lower()], int(mm.group(2)))
    if dd >= D: fails.append('tag not before report date: ' + mm.group(0))
    elif (D - dd).days > 14: fails.append('tag older than the 14-day earnings window: ' + mm.group(0))
allowed = set()
for x in feed_items(d): allowed |= nums(x['title'])
allowed |= nums(totext(orig)) | {str(i) for i in range(0, 32)} | {'50', '100', '2025', '2026', '2027'}
unk = sorted(nums(text) - allowed, key=lambda x: (len(x), x))
if unk: warns.append('numbers not in eligible feeds / original report: ' + ', '.join(unk))
print(f"== {d}: {'PASS' if not fails else 'FAIL'} pattern ({words} words)")
for f in fails: print('  FAIL:', f)
for w in warns: print('  WARN:', w)
sys.exit(1 if fails else 0)
