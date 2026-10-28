"""show_copper.py <date> — print every block-level segment (p / div / li / h* / <br>-separated line) outside the China and
Poland blocks that mentions copper or a copper ratio. Each printed segment is an exact substring of the report."""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import report
s = report(sys.argv[1])
skip = [m.span() for m in re.finditer(r'<div style="margin-bottom:24px;[^"]*">\s*<h3[^>]*>(?:🇨🇳|🇵🇱)[^\n]*\n(?:.*?\n)*?</div>', s)]
cuts = sorted({0, len(s)} | {m.start() for m in re.finditer(r'<(?:p|div|li|h[1-6])\b|<br\s*/?>|\n', s)})
for a, b in zip(cuts, cuts[1:]):
    seg = s[a:b]
    if any(x <= a < y for x, y in skip) or not re.search(r'(?i)copper', seg): continue
    print(f'@{a}', seg.strip(), '\n')
