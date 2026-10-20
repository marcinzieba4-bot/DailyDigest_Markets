"""apply_edits.py <date> — splice new/<date>.html over the China block and apply edits/<date>.json ([[old, new], ...])
to the report in corrections/2026-10-19/html. Every old string must occur exactly once; the original is kept in orig/."""
import sys, os, json, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import C, REPORTS, report, china_block
d = sys.argv[1]; path = os.path.join(REPORTS, f'{d}.html')
os.makedirs(os.path.join(C, 'orig'), exist_ok=True)
keep = os.path.join(C, 'orig', f'{d}.html')
if not os.path.exists(keep): shutil.copy(path, keep)                      # pristine pre-China copy, applied from scratch
s = open(keep, encoding='utf-8').read()
m = china_block(s); new = open(os.path.join(C, 'new', f'{d}.html'), encoding='utf-8').read().strip()
s = s[:m.start()] + new + s[m.end():]
for old, rep in json.load(open(os.path.join(C, 'edits', f'{d}.json'), encoding='utf-8')):
    n = s.count(old)
    if n != 1: sys.exit(f'{d}: edit not unique ({n}x): {old[:80]}')
    s = s.replace(old, rep)
open(path, 'w', encoding='utf-8').write(s)
print(d, 'applied')
