"""extract_old.py <dates> — save the current China block of each report to old/<date>.html (reference copy)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import C, report, china_block
for d in sys.argv[1:]:
    m = china_block(report(d)); assert m, d
    open(os.path.join(C, 'old', f'{d}.html'), 'w', encoding='utf-8').write(m.group(0) + '\n')
    print(d, len(m.group(0)), 'chars')
