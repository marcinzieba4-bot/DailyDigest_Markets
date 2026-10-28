"""apply_edits.py <date> — splice new/<date>.html (if any) over the China block and apply edits/<date>.json ([[old, new], ...])
to the report in corrections/2026-10-19/html. Every old string must occur exactly once; the original is kept in orig/."""
import sys, os, json, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import C, REPORTS, report, china_block
d = sys.argv[1]; path = os.path.join(REPORTS, f'{d}.html')
os.makedirs(os.path.join(C, 'orig'), exist_ok=True)
keep = os.path.join(C, 'orig', f'{d}.html')
if not os.path.exists(keep): shutil.copy(path, keep)                      # pristine pre-China copy, applied from scratch
s = open(keep, encoding='utf-8').read()
np = os.path.join(C, 'new', f'{d}.html')                           # no new/ block: the live-generated block is kept
if os.path.exists(np):
    m = china_block(s); new = open(np, encoding='utf-8').read().strip()
    s = s[:m.start()] + new + s[m.end():]
for old, rep in json.load(open(os.path.join(C, 'edits', f'{d}.json'), encoding='utf-8')):
    n = s.count(old)
    if n != 1: sys.exit(f'{d}: edit not unique ({n}x): {old[:80]}')
    s = s.replace(old, rep)
sp = os.path.join(C, 'sectors', f'{d}.html')                       # earnings-first sector blocks, if written
if os.path.exists(sp):
    from common import SECTOR_RE
    m2 = SECTOR_RE.search(s); assert m2, f'{d}: Sector Deep Dive not found'
    s = s[:m2.start(2)] + '\n\n' + open(sp, encoding='utf-8').read().strip() + '\n\n' + s[m2.end(2):]
pp = os.path.join(C, 'pattern', f'{d}.html')                       # Earnings Pattern section, if written
if os.path.exists(pp):
    from common import SECTOR_RE
    m3 = SECTOR_RE.search(s); assert m3, f'{d}: Sector Deep Dive not found'
    s = (s[:m3.end(2)] + '<hr style="border:none;border-top:2px solid #eee;margin:28px 0">\n\n'
         + open(pp, encoding='utf-8').read().strip() + '\n\n' + s[m3.end(2):])
open(path, 'w', encoding='utf-8').write(s)
print(d, 'applied')
