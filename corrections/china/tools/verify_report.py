"""verify_report.py <date> — checks the edited report: no copper ratios, copper never used as a growth / China gauge,
numbers and [Mon DD] tags in the changed text traceable to the eligible feed or the original report."""
import sys, os, re, difflib, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import C, report, totext, nums, feed_items
d = sys.argv[1]; D = dt.date.fromisoformat(d)
s = report(d); orig = open(os.path.join(C, 'orig', f'{d}.html'), encoding='utf-8').read()
t, to = totext(s), totext(orig)
fails, warns = [], []
for m in re.finditer(r'(?i)(gold|oil)\s*/\s*copper|copper\s*/\s*(gold|oil)|gold-copper|copper-gold', t):
    fails.append('copper ratio remains: ' + t[max(0, m.start()-60):m.end()+40])
for sent in re.split(r'(?<=[.!?])\s+', t):
    if re.search(r'(?i)copper', sent) and re.search(r'(?i)china|chinese|demand|growth|industrial|risk appetite|fear|recession|terms[- ]of[- ]trade', sent) \
       and not re.search(r'(?i)\bAI\b|data[- ]cent|grid|electrif|KGHM|not a (china|growth)', sent):
        warns.append('copper as growth gauge? ' + sent[:220])
# changed text only
sm = difflib.SequenceMatcher(None, to, t, autojunk=False)
added = ' '.join(t[j1:j2] for op, i1, i2, j1, j2 in sm.get_opcodes() if op in ('replace', 'insert'))
allowed = set()
for x in feed_items(d): allowed |= nums(x['title'])
allowed |= nums(to) | {str(i) for i in range(0, 32)} | {'50', '100', '2020', '2022', '2023', '2024', '2025', '2026', '2009', '2001'}
unk = sorted(nums(added) - allowed, key=lambda x: (len(x), x))
if unk: warns.append('new numbers not in eligible feed / original: ' + ', '.join(unk))
MON = {m: i for i, m in enumerate(['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'], 1)}
for mm in re.finditer(r'\[(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d{1,2})\]', added):
    if dt.date(D.year, MON[mm.group(1).lower()], int(mm.group(2))) >= D: fails.append('tag not before report date: ' + mm.group(0))
print(f"== {d}: {'PASS' if not fails else 'FAIL'}  (copper mentions left: {len(re.findall('(?i)copper', t))}, was {len(re.findall('(?i)copper', to))})")
for f in fails: print('  FAIL:', f)
for w in warns: print('  WARN:', w)
sys.exit(1 if fails else 0)
