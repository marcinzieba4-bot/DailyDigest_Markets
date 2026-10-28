"""old_sectors.py <date> — print each sector's ORIGINAL Narrative, New Angle and Breaking Convention text as it stands
after the copper / gold edits (orig/ + edits/<date>.json, without the new sector splice). Source material for condensing
the Narrative and Breaking Convention parts; facts in it come from that day's report and may be kept untagged."""
import sys, os, json, re, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import C, SECTOR_RE
d = sys.argv[1]
s = open(os.path.join(C, 'orig', f'{d}.html'), encoding='utf-8').read()
ep = os.path.join(C, 'edits', f'{d}.json')
if os.path.exists(ep):
    for old, new in json.load(open(ep, encoding='utf-8')):
        if s.count(old) == 1: s = s.replace(old, new)
sec = SECTOR_RE.search(s).group(2)
for b in re.findall(r'<div style="margin-bottom:18px;[^"]*">\s*(<h3.*?)</div>', sec, flags=re.S):
    print('##', re.sub(r'<[^>]+>', '', re.search(r'<h3.*?</h3>', b, flags=re.S).group(0)).replace('&nbsp;', ' '))
    for p in re.findall(r'<p>(.*?)</p>', b, flags=re.S):
        print('  ', html.unescape(re.sub(r'<[^>]+>', '', p)).strip())
    print()
