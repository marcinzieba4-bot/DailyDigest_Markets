"""show_copper.py <date> — print every paragraph / model line outside the China and Poland blocks that mentions copper or a copper ratio."""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import report
s = report(sys.argv[1])
skip = [m.span() for m in re.finditer(r'<div style="margin-bottom:24px;[^"]*">\s*<h3[^>]*>(?:🇨🇳|🇵🇱)[^\n]*\n(?:.*?\n)*?</div>', s)]
for m in re.finditer(r'<(p|li|h4)[^>]*>.*?</\1>|^[^<\n]*(?:copper|Copper)[^\n]*$', s, flags=re.S | re.M):
    if any(a <= m.start() < b for a, b in skip): continue
    if re.search(r'(?i)copper', m.group(0)):
        print(f'@{m.start()}', m.group(0).strip(), '\n')
