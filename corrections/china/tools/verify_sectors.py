#!/usr/bin/env python3
"""verify_sectors.py <date> — checks sectors/<date>.html (earnings-first Sector Deep Dive) against the original report
and the eligible feeds: 13 blocks with the original <h3> lines, three labels each, short, no Polish market references,
copper only as an AI / grid asset, numbers traceable, date tags before D and within 7 days (earnings are news)."""
import sys, os, re, collections, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import C, totext, nums, feed_items, SECTOR_RE
d = sys.argv[1]; D = dt.date.fromisoformat(d)
new = open(os.path.join(C, 'sectors', f'{d}.html'), encoding='utf-8').read().strip()
orig = open(os.path.join(C, 'orig', f'{d}.html'), encoding='utf-8').read()
old = SECTOR_RE.search(orig).group(2)
fails, warns = [], []
oh3 = re.findall(r'<h3[^>]*>.*?</h3>', old); nh3 = re.findall(r'<h3[^>]*>.*?</h3>', new)
if len(nh3) != 13: fails.append(f'{len(nh3)} sector blocks, need 13')
for o in oh3:
    if o not in nh3: fails.append('original sector heading missing/changed: ' + re.sub('<[^>]+>', '', o)[:60])
blocks = re.findall(r'<div style="margin-bottom:18px;[^"]*">\s*(<h3.*?)</div>', new, flags=re.S)
if len(blocks) != 13: fails.append(f'{len(blocks)} sector <div> blocks, need 13')
tags = collections.Counter(t.lower() for t in re.findall(r'<(/?\w+)', new))
for t in tags:
    if t.lstrip('/') not in ('div', 'h3', 'span', 'p', 'strong', 'em', 'br', 'code'): fails.append('disallowed tag ' + t)
for t in ('p', 'strong', 'div', 'span', 'h3'):
    if tags.get(t, 0) != tags.get('/' + t, 0): fails.append(f'unbalanced <{t}>')
for b in blocks:
    name = re.sub('<[^>]+>', '', re.search(r'<h3.*?</h3>', b, flags=re.S).group(0))[:30]
    t = totext(b)
    for lab in ('Narrative:', 'Reported:', 'EPS Upside Watch:', 'Breaking Convention:'):
        if t.count(lab) != 1: fails.append(f'{name}: label {lab} x{t.count(lab)}')
    w = len(re.findall(r"[A-Za-z][A-Za-z'’\-]*", re.sub(r'\[[^\]]{1,12}\]', ' ', t)))
    if w > 185: warns.append(f'{name}: {w} words (keep it short, ~100-160)')
    if 'Take:' in t: fails.append(f'{name}: old Take label — fold it into Narrative')
text = totext(new)
if re.search(r'Poland|Polish|Warsaw|\bGPW\b|\bWIG|KGHM|Orlen|\bPKO\b|Pekao|\bPZU\b|Allegro|\bXTB\b|zloty', text):
    fails.append('Polish market reference in sectors')
if re.search(r'(?i)(gold|oil)\s*/\s*copper|copper\s*/\s*(gold|oil)', text): fails.append('copper ratio')
for sent in re.split(r'(?<=[.!?])\s+', text):
    if re.search(r'(?i)copper', sent) and not re.search(r'(?i)\bAI\b|data[- ]cent|grid|electrif', sent):
        warns.append('copper without AI / grid framing: ' + sent[:120])
for w in ('corrected', 'retroactiv', 'rewritten', 'in hindsight', 'as it turned out'):
    if w in text.lower(): fails.append('meta wording: ' + w)
MON = {m: i for i, m in enumerate(['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'], 1)}
for mm in re.finditer(r'\[(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d{1,2})\]', text):
    dd = dt.date(D.year, MON[mm.group(1).lower()], int(mm.group(2)))
    if dd >= D: fails.append('tag not before report date: ' + mm.group(0))
    elif (D - dd).days > 35: warns.append('tag older than 35 days: ' + mm.group(0))
allowed = set()
for x in feed_items(d): allowed |= nums(x['title'])
allowed |= nums(totext(orig)) | {str(i) for i in range(0, 32)} | {'50', '100', '2020', '2022', '2023', '2024', '2025', '2026', '2027'}
unk = sorted(nums(text) - allowed, key=lambda x: (len(x), x))
if unk: warns.append('numbers not in eligible feeds / original report: ' + ', '.join(unk))
words = len(re.findall(r"[A-Za-z][A-Za-z'’\-]*", re.sub(r'\[[^\]]{1,12}\]', ' ', text)))
print(f"== {d}: {'PASS' if not fails else 'FAIL'} sectors ({words} words)")
for f in fails: print('  FAIL:', f)
for w in warns: print('  WARN:', w)
sys.exit(1 if fails else 0)
